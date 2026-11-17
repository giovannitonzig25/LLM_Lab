# Step 7 — Back-end: API e salvataggio delle chat (specifica)

Data: 2026-11-17. Fonte: slide «Step 7», `LLM_Lez_6.pdf` p. 14. Decisioni approvate nel brainstorming (1–5).

## Obiettivo (slide)

«Il back-end è l'unico punto di contatto del front-end. Gestisce le chat, le salva in PostgreSQL e inoltra le domande all'agente.» Le conversazioni restano disponibili dopo il riavvio e il front-end non conosce l'agente.

Evidenze richieste: OpenAPI consultabile; agente non raggiungibile con errore chiaro e documentato; test con l'agente simulato; chat ancora presenti dopo il riavvio.

**Non obiettivi:** front-end (Step 8), Compose definitivo (Step 9), modifiche all'agente HTTP o alla CLI, `/prompts` e `/stato` nel back-end, migrazioni, pool di connessioni.

## Architettura

```
(futuro front-end) ──HTTP──▶ servizio_backend (FastAPI, 8003) ──HTTP──▶ servizio_agente (8002, invariato)
                                   └──▶ PostgreSQL (chat, messaggi)
```

Moduli nuovi in `src/assistente/`:
- `archivio.py`: `ArchivioPostgres(database_url)`, solo accesso al database (SQL a mano, `psycopg`); crea lo schema con `CREATE TABLE IF NOT EXISTS`. Una connessione per operazione.
- `servizio_backend/`: `app.py` con `crea_app(archivio, client_agente)` (API e gestione delle chat), `__main__.py` (configurazione da ambiente, avvio uvicorn su porta 8003).

Il back-end non contiene logica LangGraph: conserva e rimanda all'agente `cronologia` e `riassunto` senza interpretarli.

## Database (decisione 1)

```
chat(id SERIAL PK, titolo TEXT, creata_il TIMESTAMPTZ, aggiornata_il TIMESTAMPTZ,
     riassunto TEXT DEFAULT '', cronologia JSONB DEFAULT '[]')
messaggi(id SERIAL PK, chat_id INT REFERENCES chat ON DELETE CASCADE,
         ruolo TEXT CHECK (ruolo IN ('utente','assistente')), testo TEXT, creato_il TIMESTAMPTZ)
```

- `messaggi`: ciò che l'utente vede, in ordine cronologico.
- `chat.cronologia` / `chat.riassunto`: stato dell'agente, salvato così come lo restituisce `POST /chat` dell'agente.
- Titolo: «Nuova chat» alla creazione; al primo messaggio diventa i primi ~50 caratteri della domanda.

## Dipendenza nuova (decisione 2)

`psycopg[binary]` 3.2.x, versione fissata in `requirements.txt`. Nessun ORM. JSONB con `psycopg.types.json.Jsonb`.

## API (decisione 4)

| Operazione | Richiesta | Risposta |
|---|---|---|
| Crea | `POST /chat` | 201 `{id, titolo, creata_il}` |
| Elenca | `GET /chat` | `[{id, titolo, ultimo_messaggio_il}]`, dalla più recente |
| Leggi | `GET /chat/{id}` | `{id, titolo, messaggi: [{ruolo, testo, creato_il}]}` |
| Invia | `POST /chat/{id}/messaggi` `{testo, conferme}` | `{risposta, strumenti_usati, conferme_richieste}` |
| Elimina | `DELETE /chat/{id}` | 204 |

- 404 `{"errore": ...}` se la chat non esiste; 422 per richieste malformate. `ultimo_messaggio_il` è `null` per una chat senza messaggi (ordinata per `aggiornata_il`).
- `cronologia` e `riassunto` non compaiono mai nelle API.
- **Invio:** il back-end legge cronologia e riassunto della chat, chiama `POST {AGENTE_URL}/chat` `{messaggio, cronologia, riassunto, conferme}`; se la risposta è valida e `conferme_richieste` è vuoto, salva in un'unica transazione domanda, risposta, nuova cronologia e riassunto (scostamento motivato dall'ordine letterale della slide: niente domande orfane o duplicate dopo un errore).
- **Conferma di `elimina_nota`:** se `conferme_richieste` non è vuoto, il back-end non salva nulla e lo restituisce; il chiamante, dopo aver chiesto all'utente, rimanda la stessa domanda con `conferme`.

## Errori (decisione 5)

Formato `{"errore": ...}`; in nessun caso di errore si salva qualcosa.

| Caso | Risposta |
|---|---|
| Agente irraggiungibile (connessione, timeout di connessione) | 503 «Agente non raggiungibile su `<AGENTE_URL>`» |
| Agente risponde 503 (modello spento) | 503 con il messaggio dell'agente |
| Agente risponde 502 o altro errore | 502 «Errore dell'agente: …» |
| Database irraggiungibile durante l'uso | 503 «Database non raggiungibile» |
| Database irraggiungibile all'avvio | uscita con codice 1 e messaggio chiaro |

Timeout verso l'agente come la CLI: `httpx.Timeout(10.0, read=None)`. Documentati nelle `responses` OpenAPI e nel README.

## Configurazione e avvio (decisione 5)

- Variabili: `AGENTE_URL` (esistente), `DATABASE_URL` (nuova); in `.env.example` anche `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` con valori d'esempio senza segreti.
- Compose: solo il nuovo servizio `postgres` (immagine ufficiale con versione fissata, volume con nome, porta `127.0.0.1:5432`, credenziali da `.env`). Servizio del back-end in Compose rimandato allo Step 9.
- Avvio locale: `.\.venv\Scripts\python.exe -m assistente.servizio_backend`.

## Test e verifiche (decisione 3)

- Test automatici senza rete né database: `crea_app` con un `ArchivioMemoria` (in `tests/`) e un `httpx.Client` verso l'app vera dell'agente servita da `TestClient` con grafo simulato; agente spento simulato con `httpx.MockTransport` che solleva `ConnectError`. L'SQL non è coperto dalla suite (rischio accettato).
- Prova reale una sola volta, esiti in `prove_reali/PROVE.md`: PostgreSQL in Docker, `/docs` consultabile, crea chat e invia un messaggio, riavvio del back-end, chat ancora presente; agente spento → 503.
- Suite esistente (784) verde.

## Documentazione e regole

- README: configurazione, avvio, API ed errori del back-end.
- `CLAUDE.md`, solo dopo approvazione esplicita a implementazione conclusa: «Nessuna persistenza» vale per la CLI e per l'agente (senza stato); le chat del back-end sono salvate in PostgreSQL; SQLite resta solo per le note. Aggiunta di `archivio` e `servizio_backend/` alla struttura.
