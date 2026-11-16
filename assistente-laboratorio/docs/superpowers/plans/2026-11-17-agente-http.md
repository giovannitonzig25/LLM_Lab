# Step 6 — Agente come servizio HTTP: piano

> Esecuzione in linea (workflow rapido, `CLAUDE.md`): task in ordine, controllo funzionale essenziale, nessuna review o fase di test separata. Commit e merge solo con autorizzazione esplicita dell'utente.

**Obiettivo:** lo stesso grafo risponde alle chiamate HTTP; la CLI diventa un client dell'API.

**Architettura:** la logica del turno passa da `terminale.py` a un nuovo modulo `agente.py`; un nuovo pacchetto `servizio_agente/` (FastAPI, porta 8002) la espone senza stato; la CLI chiama l'API con `httpx`.

**Tecnologie:** FastAPI, uvicorn, httpx, LangGraph, `langchain_core.messages` (`messages_to_dict` / `messages_from_dict`). Nessuna dipendenza nuova.

**Specifica:** `docs/superpowers/specs/2026-11-17-agente-http-design.md`.

**Ramo:** `feat/agente-http` da `dev`.

## Vincoli globali

- Grafo, Router, Revisore, Riassunto (fail-open), preferenze, strumenti e `comandi.py` invariati.
- Agente senza stato: nessuna cronologia conservata nel servizio tra le richieste; le conferme valgono per la sola richiesta.
- Nessuno strumento con `destructiveHint` eseguito senza una conferma `{strumento, argomenti}` identica nella richiesta.
- Codici: 503 modello irraggiungibile o MCP spento (prompt, `/stato`), 502 altri errori del modello, 422 richiesta malformata, 200 per limite di passaggi e strumenti in errore.
- Suite esistente verde alla fine di ogni task (`.\.venv\Scripts\python.exe -m pytest -q`).

---

### Task 1: modulo `agente` (logica del turno separata dall'interfaccia)

**File:**
- Crea: `src/assistente/agente.py`
- Modifica: `src/assistente/terminale.py` (rimozione di quanto spostato), `src/assistente/mcp_client.py` (firma della conferma)
- Modifica i test che importano da `terminale` le parti spostate: `test_limite.py`, `test_revisore.py`, `test_riassunto.py`, `test_router.py`, `test_terminale.py`, `test_mcp_client.py`

**Interfacce prodotte:**
- Spostati da `terminale` senza cambiare comportamento: `Sessione`, `esegui_turno`, `esegui_turno_messaggi`, `limite_ricorsione`, `MESSAGGIO_LIMITE`, `ERRORE_SERVER`, `AVVISO_RISPOSTA_VUOTA`, costanti `PASSAGGI_*`.
- `class ErroreModello(Exception)` con attributo `codice: int` (503 per `openai.APIConnectionError`, che comprende il timeout; 502 per gli altri `openai.OpenAIError`) e messaggio col testo di `ERRORE_SERVER`.
- `@dataclass(frozen=True) class EsitoTurno`: `sessione: Sessione`, `risposta: str`, `strumenti_usati: tuple[dict, ...]` (`{"nome", "argomenti"}`), `conferme_richieste: tuple[dict, ...]` (`{"strumento", "argomenti"}`), `limite: bool`.
- `esegui_turno_api(grafo, sessione, nuovi, max_passaggi, *, max_revisioni, conferme=()) -> EsitoTurno`: solleva `ErroreModello`; limite di passaggi → `EsitoTurno` con la sessione ricevuta e `MESSAGGIO_LIMITE`. `strumenti_usati` si ricava dai `tool_calls` degli `AIMessage` dopo `esito["inizio_turno"]`. `esegui_turno_messaggi` resta, come involucro che converte `ErroreModello` nel testo di oggi.
- Conferme per richiesta: `ContextVar` in `agente` con le conferme ricevute e la lista di quelle richieste; `conferma_da_richiesta(nome: str, argomenti: dict) -> bool` è vera solo se `{"strumento": nome, "argomenti": argomenti}` è tra le conferme, altrimenti la registra tra le richieste e restituisce `False`.
- `mcp_client.StrumentoMcp.chiedi_conferma` diventa `Callable[[str, dict], bool]` (nome, argomenti); invariati validazione prima della conferma e testo `Errore: cancellazione non confermata dall'utente`.
- `costruisci_agente(config: Config) -> tuple[grafo, list[str]]`: quello che oggi fa `terminale.main` (componi_strumenti con `chiedi_conferma=conferma_da_richiesta`, preferenze, modelli, `costruisci_grafo`), restituisce il grafo e gli avvisi dell'avvio ridotto.

- [ ] Creare `agente.py` e spostarvi il codice; aggiornare gli import dei test.
- [ ] Aggiungere `ErroreModello`, `EsitoTurno`, `esegui_turno_api`, le conferme per richiesta e `costruisci_agente`; adattare `mcp_client` e i suoi test alla nuova firma.
- [ ] Test in `tests/test_agente.py` con `ModelloSimulato` di `tests/finti.py`: `strumenti_usati` contiene l'orologio chiamato nel turno; strumento distruttivo senza conferma → non eseguito e presente in `conferme_richieste`; con la conferma identica → eseguito; `APIConnectionError` → `ErroreModello.codice == 503`.
- [ ] Suite completa verde.

### Task 2: servizio HTTP dell'agente

**File:**
- Crea: `src/assistente/servizio_agente/__init__.py`, `app.py`, `__main__.py`
- Test: `tests/test_servizio_agente.py`

**Interfacce:**
- Consuma: `esegui_turno_api`, `Sessione`, `ErroreModello`, `costruisci_agente` (Task 1); `comandi.converti_messaggi`; `mcp_client.elenca_prompt`, `ottieni_prompt`, `ErroreMcp`, `scopri_strumenti`.
- Produce: `crea_app(grafo, *, max_passaggi: int, max_revisioni: int, elenca, ottieni, stato_mcp, stato_modello) -> FastAPI`. `elenca() -> tuple[PromptMcp, ...]`, `ottieni(nome, argomenti) -> list[tuple[str, str]]`, `stato_mcp() -> str` e `stato_modello() -> str` restituiscono `"ok"` o il motivo (tutte iniettabili nei test).
- Endpoint e formati JSON esattamente come in specifica §4: `POST /chat`, `GET /prompts`, `POST /prompts/{nome}`, `GET /stato`; errori `{"errore": "..."}`.
- `__main__.py`: `carica_config` (errore → messaggio su stderr, codice 1), `costruisci_agente`, avvisi nel log, `uvicorn.run` su `AGENTE_HOST` (predefinito `127.0.0.1`) e `AGENTE_PORT` (predefinito `8002`). `stato_modello`: `GET {base_url}/models` con `httpx` e `LM_STUDIO_MODEL` tra gli id; `stato_mcp`: `scopri_strumenti` entro `mcp_timeout`.
- Log INFO `assistente.servizio_agente`: a fine turno `turno: esito=<risposta|limite|errore> strumenti=<nomi> durata=<s>`; la riga per ogni strumento c'è già nel grafo.

- [ ] Scrivere `app.py` con i modelli Pydantic delle richieste e risposte; `messaggio`/`messaggi` mutuamente esclusivi (422).
- [ ] Scrivere `__main__.py`.
- [ ] Test con `fastapi.testclient.TestClient` e grafo costruito con i modelli simulati: chat semplice con cronologia e riassunto restituiti e riusabili nella richiesta successiva; `strumenti_usati`; ciclo conferma richiesta → conferma inviata → strumento eseguito; `messaggio` e `messaggi` insieme → 422; modello che solleva `APIConnectionError` → 503 con `errore`; `/stato` con MCP `"non raggiungibile: ..."` → 503; `/prompts` con `elenca` che solleva `ErroreMcp` → 503; `/openapi.json` → 200.
- [ ] Suite completa verde.

### Task 3: la CLI come client dell'API

**File:**
- Modifica: `src/assistente/terminale.py`
- Modifica: `tests/test_terminale.py`, `tests/test_limite.py`, `tests/test_riassunto.py` (parti che usano `esegui_chat` o `terminale.main`)

**Interfacce:**
- Consuma: l'API del Task 2; `Sessione` (Task 1); `comandi.esegui_comando`; `PromptMcp`, `ArgomentoPrompt`.
- Produce: `class ClientAgente` costruito su un `httpx.Client` (`base_url=AGENTE_URL`), con `chat(sessione, *, messaggio=None, messaggi=None, conferme=()) -> RispostaChat` (sessione aggiornata, risposta, conferme richieste; per 502/503 solleva `ErroreAgente` col messaggio ricevuto), `elenca_prompt() -> tuple[PromptMcp, ...]` e `ottieni_prompt(nome, argomenti) -> list[tuple[str, str]]` (per 503 sollevano `ErroreMcp` col messaggio ricevuto, così `comandi` mostra il testo di oggi).
- `esegui_chat(client: ClientAgente, leggi, scrivi, *, chiedi_conferma=chiedi_conferma)`: stesso ciclo di oggi (esci, righe vuote, comandi `/`, EOF e Ctrl+C). Se arrivano `conferme_richieste`, per ognuna `chiedi_conferma("Confermi: <strumento> <argomenti>?")`; se l'utente conferma, ripete il turno con la sessione **precedente** e le stesse domanda/messaggi più le conferme; altrimenti stampa la risposta ricevuta. Su `ErroreAgente` stampa il messaggio e conserva la sessione.
- `main()`: `AGENTE_URL` (predefinito `http://localhost:8002`); `GET /stato` iniziale: connessione rifiutata → `Agente non raggiungibile su <AGENTE_URL>` su stderr e codice 1; 503 → avviso su stderr con il dettaglio e si prosegue.

- [ ] Riscrivere `terminale.py` come client.
- [ ] Adattare i test che usavano `esegui_chat(grafo, ...)`: un aiuto nei test crea `crea_app` sul grafo simulato e un `ClientAgente` su `TestClient`, così gli scenari esistenti (cronologia, errori, limite, prompt, conferma di `elimina_nota` col server MCP reale) passano attraverso l'API. I test di `terminale.main` sulla costruzione del grafo passano a `costruisci_agente`.
- [ ] Suite completa verde.

### Task 4: configurazione, Compose, documentazione e controllo funzionale

**File:**
- Modifica: `.env.example`, `compose.yaml`, `README.md`, `prove_reali/PROVE.md`

- [ ] `.env.example`: `AGENTE_URL`, `AGENTE_HOST`, `AGENTE_PORT` commentate con i predefiniti.
- [ ] `compose.yaml`: servizio `agente` (comando `python -m assistente.servizio_agente`, `env_file: .env`, `AGENTE_HOST: 0.0.0.0`, porta `127.0.0.1:8002:8002`, variabili di LM Studio, MCP e servizi HTTP spostate da `assistente`, `depends_on` `server-mcp` e `servizi-http` con `service_started`). `assistente` con `AGENTE_URL: http://agente:8002` e `depends_on: agente`.
- [ ] README: quattro finestre PowerShell, endpoint con un esempio `Invoke-RestMethod`, `/docs`, diagnosi (503, `/stato`).
- [ ] Controllo funzionale essenziale con LM Studio, una volta: domanda con tool via `Invoke-RestMethod` (risposta e traccia nel log), LM Studio spento (503), MCP spento (`/stato` 503), `/docs`, breve conversazione dalla CLI con una conferma di `elimina_nota`. Esiti in `PROVE.md`; ciò che non si esegue (per esempio Compose) resta indicato come da provare.
