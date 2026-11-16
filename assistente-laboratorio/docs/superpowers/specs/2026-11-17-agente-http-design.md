# Step 6 — L'agente come servizio HTTP (specifica)

Data: 2026-11-17. Lezione 6, Step 6 (slide a pagina 13 di `LLM_Lez_6.pdf`, testo fornito dall'utente).

## 1. Requisiti della slide

> Finora l'agente era un'applicazione da terminale. Per servire un'interfaccia web deve esporre un'API: riceve la conversazione e restituisce la risposta.
>
> **Obiettivo:** lo stesso grafo risponde sia dalla CLI sia alle chiamate HTTP, senza duplicare la logica.

Cosa realizzare:
1. Separare il modulo dell'agente dall'interfaccia: la CLI diventa un client dell'API.
2. Endpoint che riceve messaggio e cronologia e restituisce risposta e strumenti usati.
3. Endpoint di stato: agente, server MCP e modello raggiungibili.
4. Agente senza stato: cronologia ed eventuale riassunto arrivano dal chiamante e tornano aggiornati.

Evidenze richieste:
- chiamata HTTP con una domanda che usa un tool: risposta e traccia nei log;
- modello o strumenti non disponibili: codice e messaggio di errore comprensibili;
- test dell'API con il grafo simulato; documentazione OpenAPI consultabile.

**Fuori ambito:** back-end, API delle chat e persistenza (Step 7), front-end (Step 8), Compose definitivo (Step 9).

## 2. Cosa non cambia

Grafo (`grafo.py`), Router, Revisore e Riassunto con il loro fail-open, preferenze lette all'avvio dalla resource MCP, strumenti locali, HTTP e MCP (discovery invariata), `comandi.py` (scomposizione, controllo degli argomenti, conversione dei messaggi del prompt), `Sessione` immutabile. Nessuna dipendenza nuova: `fastapi`, `uvicorn`, `httpx` sono già presenti; la serializzazione dei messaggi usa `langchain_core`.

## 3. Architettura

```
CLI (terminale) ──HTTP──▶ servizio agente (FastAPI, porta 8002) ──▶ grafo ──▶ LM Studio
   Sessione locale            senza stato                       └──▶ server MCP, servizi HTTP
```

- **Modulo `agente`** (nuovo, `src/assistente/agente.py`): contiene ciò che oggi sta in `terminale.py` e non riguarda l'interfaccia. Cioè costruzione del grafo dalla configurazione (oggi in `terminale.main`), `Sessione`, `esegui_turno` / `esegui_turno_messaggi`, `limite_ricorsione`, messaggi di limite e di errore del server. Unica logica del turno, usata dal servizio HTTP.
- **Servizio `servizio_agente/`** (nuovo pacchetto, come `servizi_http/`): `app.py` con `crea_app(...)` che riceve grafo e dipendenze (iniettabili nei test), `__main__.py` con l'avvio `uvicorn` (`AGENTE_HOST`, predefinito `127.0.0.1`; `AGENTE_PORT`, predefinito `8002`). All'avvio legge la configurazione e costruisce il grafo come oggi la CLI, avvio ridotto compreso. Un errore di configurazione stampa il messaggio e termina con codice 1.
- **CLI (`terminale.py`)**: non costruisce più il grafo e non legge la configurazione del modello. Legge solo `AGENTE_URL` (predefinito `http://localhost:8002`), conserva la `Sessione` e chiama l'API con `httpx`. La modalità con il grafo in-process sparisce.

## 4. API

Documentazione OpenAPI automatica di FastAPI su `/docs` (e `/openapi.json`).

### 4.1 `POST /chat`

Richiesta:
```json
{
  "messaggio": "Che ore sono a Tokyo?",
  "messaggi": null,
  "cronologia": [ /* messaggi serializzati */ ],
  "riassunto": "",
  "conferme": [ {"strumento": "elimina_nota", "argomenti": {"id": 3}} ]
}
```
- Esattamente uno tra `messaggio` (testo di una domanda) e `messaggi` (lista di `{ruolo, testo}` di un prompt MCP, convertita con `comandi.converti_messaggi`); altrimenti **422**.
- `cronologia`: messaggi LangChain serializzati con `messages_to_dict` e ricostruiti con `messages_from_dict` (chiamate agli strumenti e `ToolMessage` restano intatti). Predefinita vuota; `riassunto` predefinito `""`; `conferme` predefinita vuota.

Risposta **200**:
```json
{
  "risposta": "...",
  "cronologia": [ /* aggiornata, eventualmente compressa dal Riassunto */ ],
  "riassunto": "...",
  "strumenti_usati": [ {"nome": "orologio", "argomenti": {"timezone": "Asia/Tokyo"}} ],
  "conferme_richieste": [ {"strumento": "elimina_nota", "argomenti": {"id": 3}} ]
}
```
- `strumenti_usati`: chiamate a strumenti (`tool_calls` degli `AIMessage`) prodotte in questo turno.
- Limite di passaggi raggiunto: 200 con l'attuale `MESSAGGIO_LIMITE`, cronologia e riassunto restituiti invariati.

### 4.2 Conferma degli strumenti distruttivi (decisione approvata)

- Uno strumento con `destructiveHint` viene eseguito solo se nome e argomenti coincidono esattamente con un elemento di `conferme` della richiesta.
- Altrimenti non viene eseguito: il modello riceve come oggi `Errore: cancellazione non confermata dall'utente` e la coppia `{strumento, argomenti}` finisce in `conferme_richieste`.
- La CLI mostra la richiesta e chiede `s/N` all'utente. Con «sì» ripete **lo stesso turno** (stessa cronologia, stesso riassunto, stessa domanda o stessi messaggi) con quella conferma e mostra la nuova risposta. Con «no» mostra la risposta già ricevuta e tiene la cronologia aggiornata.
- Se al nuovo giro il modello cambia gli argomenti, la conferma viene chiesta di nuovo: niente si cancella senza conferma esplicita dell'utente, raccolta dall'applicazione.
- La validazione degli argomenti prima della conferma (`mcp_client`) resta invariata. Le conferme valgono per la sola richiesta (nessuno stato nel servizio).

### 4.3 `GET /prompts` e `POST /prompts/{nome}` (decisione approvata)

- `GET /prompts`: elenco dei prompt MCP (`nome`, `descrizione`, argomenti con nome, descrizione, obbligatorietà), da `mcp_client.elenca_prompt`.
- `POST /prompts/{nome}` con corpo `{"argomenti": {...}}`: messaggi del prompt come lista di `{ruolo, testo}`, da `mcp_client.ottieni_prompt`.
- Server MCP non raggiungibile o errore MCP: **503** con messaggio chiaro.
- La CLI passa a `comandi.esegui_comando` due funzioni `elenca` e `ottieni` che chiamano questi endpoint e ricostruiscono gli stessi tipi di oggi (`PromptMcp`, coppie `(ruolo, testo)`); `comandi.py` non cambia.

### 4.4 `GET /stato`

```json
{"agente": "ok", "mcp": "ok", "modello": "ok"}
```
- `mcp`: raggiungibile se la lista degli strumenti MCP risponde entro il timeout (stesso controllo di `verifica_mcp`).
- `modello`: raggiungibile se `GET {LM_STUDIO_BASE_URL}/models` risponde ed elenca `LM_STUDIO_MODEL`.
- **200** se tutto è raggiungibile, **503** altrimenti, con il motivo nel campo del componente (per esempio `"mcp": "non raggiungibile: ..."`).

## 5. Errori (decisione approvata)

| Situazione | Codice | Corpo |
|---|---|---|
| LM Studio non raggiungibile (connessione, timeout) | 503 | `{"errore": ...}` col testo di `ERRORE_SERVER` |
| Altri errori del modello (`openai.OpenAIError`) | 502 | `{"errore": ...}` |
| Richiesta malformata | 422 | validazione FastAPI |
| MCP spento, endpoint dei prompt | 503 | `{"errore": ...}` |
| MCP spento, `/stato` | 503 | campo `mcp` col motivo |
| Strumento che fallisce in un turno | 200 | come oggi: `Errore:` al modello, fail-open |
| Limite di passaggi | 200 | `MESSAGGIO_LIMITE` |

- Il servizio parte anche senza MCP (avvio ridotto, avviso nel log) e senza il servizio HTTP.
- La cronologia in caso di errore non cambia: il chiamante tiene la propria.
- **CLI:** mostra il messaggio d'errore ricevuto e conserva la `Sessione` precedente. Se l'agente non risponde (connessione rifiutata) stampa `Agente non raggiungibile su <AGENTE_URL>` e termina con codice 1.

## 6. Log (traccia)

Nel servizio dell'agente, livello INFO su stderr: una riga per ogni strumento eseguito (nome e argomenti), una riga per turno con l'esito (risposta, limite o errore) e la durata. Le righe già presenti (Router, Revisore, Riassunto, conferme) restano.

## 7. Avvio e configurazione

- Locale: quattro finestre PowerShell, con `$env:PYTHONPATH = "src"`: server MCP (8001), servizi HTTP (8000), **agente** `.\.venv\Scripts\python.exe -m assistente.servizio_agente` (8002), CLI `.\.venv\Scripts\python.exe -m assistente.terminale`.
- `.env.example`: aggiunte `AGENTE_URL` (CLI) e `AGENTE_HOST` / `AGENTE_PORT` (servizio), commentate con i predefiniti.
- Compose: nuovo servizio `agente` (stessa immagine, comando `python -m assistente.servizio_agente`, `AGENTE_HOST=0.0.0.0`, variabili di modello, MCP e servizi HTTP spostate qui, dipende da `server-mcp` e `servizi-http`). Il servizio `assistente` esegue la CLI con `AGENTE_URL=http://agente:8002` e dipende da `agente`. Nessun'altra riorganizzazione (Step 9).

## 8. Verifiche

- Test dell'API con FastAPI `TestClient` e un grafo simulato (nessun modello né rete): domanda semplice con cronologia e riassunto che tornano aggiornati, `strumenti_usati`, conferma richiesta e poi eseguita, 422, 503 del modello, `/stato`, prompt con MCP spento. I test esistenti di `terminale` si adattano allo spostamento del codice in `agente`; la suite resta verde.
- Controllo funzionale essenziale, a mano con LM Studio: una domanda che usa un tool via `curl`/`Invoke-RestMethod` (risposta e traccia nel log), LM Studio spento (503), MCP spento (`/stato` 503), `/docs` consultabile, una breve conversazione dalla CLI. Esiti in `prove_reali/PROVE.md`.
- README aggiornato con avvio, endpoint e diagnosi.

## 9. Scelte lasciate a chi implementa

Nomi interni delle funzioni e dei modelli Pydantic; come passare le conferme della richiesta allo strumento MCP già creato all'avvio (per esempio una `contextvars.ContextVar` impostata dal gestore della richiesta), purché non resti stato tra le richieste e la conferma riceva nome e argomenti dello strumento.
