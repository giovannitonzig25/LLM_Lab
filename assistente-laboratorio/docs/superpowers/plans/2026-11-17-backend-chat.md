# Back-end delle chat (Step 7) — piano di implementazione

> **Esecuzione:** in linea nella sessione principale (`superpowers:executing-plans`), workflow rapido di `CLAUDE.md`: TDD non obbligatorio, nessuna review indipendente, commit/merge/push solo con autorizzazione esplicita.

**Obiettivo:** back-end FastAPI (porta 8003) che gestisce le chat, le salva in PostgreSQL e inoltra le domande all'agente HTTP dello Step 6.

**Architettura:** `archivio.py` (solo SQL, `psycopg`) + `servizio_backend/` (`crea_app(archivio, agente)` con API e logica delle chat; `__main__` con configurazione e uvicorn). L'agente resta invariato: il back-end gli passa e ne conserva `cronologia` e `riassunto` senza interpretarli.

**Tecnologie:** FastAPI, httpx, `psycopg[binary]` 3.2.x (unica dipendenza nuova), PostgreSQL in Docker.

**Specifica:** `docs/superpowers/specs/2026-11-17-backend-chat-design.md`

## Vincoli globali

- Nessuna modifica a `servizio_agente/`, `agente.py`, `grafo.py`, `terminale.py`; suite esistente (784) verde.
- Errori nel formato `{"errore": ...}`; in caso di errore non si salva nulla.
- Credenziali solo in `.env`; `.env.example` senza segreti. Comandi documentati per PowerShell.
- Non anticipare Step 8 (front-end) e Step 9 (servizio back-end in Compose).
- Ramo `feat/backend-chat` da `dev`; nessun commit senza autorizzazione.

## Punti da tenere d'occhio

1. Seconda domanda nella stessa chat: l'agente deve ricevere la cronologia salvata dopo la prima (test in Task 2).
2. Conferma richiesta: nulla salvato; ripetendo con `conferme` si salva una sola volta (test in Task 2).
3. Agente spento o in errore: chat invariata (test in Task 2).
4. Chat inesistente su leggi/invia/elimina: 404 (test in Task 2).
5. Titolo: solo la prima domanda lo imposta (test in Task 2).

---

### Task 1: Archivio PostgreSQL, dipendenza e servizio `postgres`

**File:**
- Crea: `src/assistente/archivio.py`
- Modifica: `requirements.txt` (aggiunge `psycopg[binary]==<ultima 3.2.x>`), `compose.yaml` (servizio `postgres` + volume `dati-postgres`), `.env.example`

**Interfacce prodotte** (in `archivio.py`):
- `class ChatNonTrovata(Exception)`, `class ErroreDatabase(Exception)`
- `TITOLO_INIZIALE = "Nuova chat"`, `LUNGHEZZA_TITOLO = 50`
- `class ArchivioPostgres(database_url: str)` con:
  - `prepara() -> None`: `CREATE TABLE IF NOT EXISTS` di `chat` e `messaggi` come da specifica.
  - `crea_chat() -> dict` → `{id, titolo, creata_il}`
  - `elenca_chat() -> list[dict]` → `[{id, titolo, ultimo_messaggio_il}]`, ordinate per `aggiornata_il` decrescente; `ultimo_messaggio_il` = `max(messaggi.creato_il)` o `None`.
  - `leggi_chat(id: int) -> dict` → `{id, titolo, messaggi: [{ruolo, testo, creato_il}]}` ordinati per `creato_il, id`.
  - `stato_agente(id: int) -> tuple[list[dict], str]` → `(cronologia, riassunto)`.
  - `aggiungi_scambio(id: int, domanda: str, risposta: str, cronologia: list[dict], riassunto: str) -> None`: una transazione; inserisce i due messaggi (`utente`, `assistente`), aggiorna `cronologia` (con `Jsonb`), `riassunto`, `aggiornata_il = now()`; se la chat non aveva messaggi, `titolo = domanda.strip()[:LUNGHEZZA_TITOLO]`.
  - `elimina_chat(id: int) -> None`
  - leggi/stato/aggiungi/elimina sollevano `ChatNonTrovata` se l'id non esiste; ogni `psycopg.OperationalError` diventa `ErroreDatabase`.
- Una connessione per operazione: `with psycopg.connect(self.database_url, row_factory=dict_row) as conn`.

**Compose:** servizio `postgres`, `image: postgres:17.6` (versione fissata), `environment` `POSTGRES_USER/PASSWORD/DB` da `.env`, `volumes: dati-postgres:/var/lib/postgresql/data`, `ports: "127.0.0.1:5432:5432"`, healthcheck `pg_isready`. Nessun altro servizio modificato.

**`.env.example`:** `POSTGRES_USER=assistente`, `POSTGRES_PASSWORD=cambiami`, `POSTGRES_DB=chat`, `DATABASE_URL=postgresql://assistente:cambiami@localhost:5432/chat`, `#BACKEND_HOST=127.0.0.1`, `#BACKEND_PORT=8003`.

- [ ] Installare la dipendenza nel `.venv` e fissarne la versione in `requirements.txt`.
- [ ] Scrivere `archivio.py` e aggiornare `compose.yaml` e `.env.example`.
- [ ] Verifica: `docker compose config` valido; `docker compose up -d postgres`; da Python `ArchivioPostgres(url).prepara()` e un giro `crea_chat` → `aggiungi_scambio` → `leggi_chat` → `elimina_chat` senza errori.

### Task 2: Servizio back-end e test con l'agente simulato

**File:**
- Crea: `src/assistente/servizio_backend/__init__.py`, `app.py`, `__main__.py`
- Crea: `tests/archivio_memoria.py` (`ArchivioMemoria`, stesse firme ed eccezioni di `ArchivioPostgres`, `prepara()` vuoto), `tests/test_servizio_backend.py`

**Interfacce:**
- Usa da Task 1: `ArchivioPostgres`, `ChatNonTrovata`, `ErroreDatabase`.
- Produce: `crea_app(archivio, agente: httpx.Client) -> FastAPI` in `servizio_backend/app.py`; `agente` ha `base_url` impostato.

**API** (modelli Pydantic con `responses` OpenAPI per 404/502/503): `POST /chat` (201), `GET /chat`, `GET /chat/{id}`, `POST /chat/{id}/messaggi` body `{testo: str (min 1), conferme: list[{strumento, argomenti}] = []}` → `{risposta, strumenti_usati, conferme_richieste}`, `DELETE /chat/{id}` (204).

**Invio:** `stato_agente(id)` → `agente.post("/chat", json={messaggio, cronologia, riassunto, conferme})`. Esiti:
- `httpx.TransportError` → 503 `"Agente non raggiungibile su {base_url}"`;
- risposta 503 → 503 con il campo `errore` dell'agente;
- altra risposta non 200 → 502 `"Errore dell'agente: {errore o status}"`;
- 200 con `conferme_richieste` non vuoto → restituito, nulla salvato;
- 200 altrimenti → `aggiungi_scambio(...)` con `cronologia` e `riassunto` della risposta, poi restituito.
- `ChatNonTrovata` → 404 `"Chat {id} non trovata"`; `ErroreDatabase` → 503 `"Database non raggiungibile"` (exception handler).

**`__main__`:** `DATABASE_URL` obbligatoria (assente → messaggio e codice 1); `AGENTE_URL` (predefinito `http://localhost:8002`); `BACKEND_HOST`/`BACKEND_PORT` (predefiniti `127.0.0.1`/`8003`); `archivio.prepara()` e `ErroreDatabase` → messaggio e codice 1; `httpx.Client(base_url=AGENTE_URL, timeout=httpx.Timeout(10.0, read=None))`; `uvicorn.run`.

**Test** (agente = `TestClient` dell'app vera dell'agente con `grafo_con` simulato come in `tests/test_servizio_agente.py`; agente spento = `httpx.Client(transport=httpx.MockTransport(...solleva ConnectError...), base_url=...)`):
- `test_crea_elenca_leggi_elimina`: 201 con id; elenco con titolo «Nuova chat» e `ultimo_messaggio_il` null; lettura vuota; delete 204; poi 404.
- `test_messaggio_salvato_e_titolo`: invio → risposta del modello simulato; lettura con `[utente, assistente]` in ordine; titolo = prima domanda; seconda domanda non cambia il titolo.
- `test_seconda_domanda_riceve_la_cronologia`: il modello simulato riceve alla seconda chiamata anche la prima domanda.
- `test_conferma_non_salva_poi_salva`: strumento distruttivo simulato (come `cancella` in `test_servizio_agente.py`); prima richiesta → `conferme_richieste` non vuoto, chat vuota; ripetizione con `conferme` → un solo scambio salvato.
- `test_agente_spento_503`: 503 con «Agente non raggiungibile», chat invariata.
- `test_agente_in_errore_502`: agente `MockTransport` che risponde 502 → 502, chat invariata.
- `test_chat_inesistente_404` su GET, POST messaggi, DELETE.
- `test_database_spento_503`: archivio che solleva `ErroreDatabase` → 503.
- `test_openapi_elenca_i_percorsi`: `/openapi.json` contiene `/chat`, `/chat/{id}`, `/chat/{id}/messaggi`.

- [ ] Scrivere `ArchivioMemoria` e il servizio.
- [ ] Scrivere i test e farli passare: `.\.venv\Scripts\python.exe -m pytest tests/test_servizio_backend.py -v`.
- [ ] Suite completa verde: `.\.venv\Scripts\python.exe -m pytest -q` (784 + nuovi).

### Task 3: Prova reale e documentazione

**File:** `prove_reali/PROVE.md`, `README.md`; `CLAUDE.md` solo con autorizzazione esplicita.

- [ ] Prova reale una volta (PostgreSQL in Docker, agente e LM Studio accesi), esiti in `PROVE.md`:
  - B1 `/docs` del back-end consultabile;
  - B2 crea chat, invia un messaggio, risposta salvata e rilevabile con `GET /chat/{id}`;
  - B3 riavvio del back-end (e di `postgres`): chat e messaggi ancora presenti;
  - B4 agente spento: 503 «Agente non raggiungibile…», chat invariata.
- [ ] README: variabili (`DATABASE_URL`, `POSTGRES_*`, `BACKEND_*`), avvio di `postgres` e del back-end, tabella API ed errori, solo comandi verificati.
- [ ] Proporre il testo per `CLAUDE.md` (regola di persistenza, moduli `archivio` e `servizio_backend/`, porta 8003) e applicarlo dopo approvazione.
- [ ] Riepilogo all'utente: cosa è stato eseguito, esiti, cosa resta da provare; commit e merge solo su autorizzazione.
