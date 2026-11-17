# Step 8 — Front-end di chat: piano di implementazione

> Esecuzione in linea nella sessione principale (workflow rapido), ramo `feat/frontend-chat` da `dev`. Nessun commit, merge o push senza autorizzazione esplicita dell'utente.

**Obiettivo:** una pagina web di chat che parla solo con il back-end dello Step 7, tramite un piccolo servizio FastAPI che la serve e inoltra `/api/...` a `BACKEND_URL`.

**Architettura:** `servizio_frontend` (porta 8004) = `StaticFiles` + inoltro generico con `httpx`. Pagina in HTML, CSS e JavaScript semplice con percorsi relativi `/api/...`. Back-end invariato.

**Tecnologie:** FastAPI, uvicorn, httpx (già in `requirements.txt`); nessuna dipendenza nuova.

**Specifica:** `docs/superpowers/specs/2026-11-17-frontend-chat-design.md`.

## Vincoli globali

- Il front-end chiama solo il back-end; percorsi e JSON solo dal documento OpenAPI esportato.
- Il back-end (`servizio_backend/`, `archivio`) non si modifica.
- Timeout verso il back-end: `httpx.Timeout(10.0, read=None)`; nessun timeout nella pagina.
- Nessun indirizzo nel codice della pagina; `BACKEND_URL` predefinito `http://127.0.0.1:8003`, `FRONTEND_HOST` `127.0.0.1`, `FRONTEND_PORT` `8004`.
- Conferma di `elimina_nota` data solo dall'utente nella pagina.
- Nessun Docker Compose per il front-end (Step 9).

## Punti da tenere d'occhio

1. Turno di 1–3 minuti: l'inoltro non deve scadere (lettura senza limite).
2. Back-end spento: 503 `{"errore": ...}` dal front-end, non un 500.
3. Risposta 204 di `DELETE`: inoltrata senza corpo.
4. Errori senza `errore` (422 con `detail`, risposta non JSON): la pagina mostra un testo generico con il codice HTTP.
5. Doppio invio durante l'attesa: campo e pulsante disattivati finché la risposta non arriva.

---

### Task 1: servizio `servizio_frontend` con inoltro al back-end

**File:**
- Crea: `src/assistente/servizio_frontend/__init__.py`, `app.py`, `__main__.py`, `static/index.html` (segnaposto, completato nel Task 2)
- Crea: `docs/superpowers/specs/2026-11-17-openapi-backend.json` (esportato da `crea_app(None, None).openapi()` del back-end, `indent=2`)
- Modifica: `.env.example` (sezione «Front-end (Step 8)» con le tre variabili commentate)
- Test: `tests/test_servizio_frontend.py`

**Interfacce:**
- Produce: `crea_app(backend: httpx.Client) -> FastAPI` in `assistente.servizio_frontend.app`; `GET /` → `static/index.html`; `/static` montato su `static/`; `api_route("/api/{percorso:path}", methods=["GET", "POST", "DELETE"])`.
- `__main__.main() -> int`: legge `BACKEND_URL`, `FRONTEND_HOST`, `FRONTEND_PORT`, crea `httpx.Client(base_url=BACKEND_URL, timeout=httpx.Timeout(10.0, read=None))`, avvia uvicorn. Logging come `servizio_backend/__main__.py`.

- [ ] **Passo 1: test** in `tests/test_servizio_frontend.py`:
  - `test_pagina_servita`: `GET /` → 200, `text/html`; `GET /static/index.html` → 200.
  - `test_inoltro_al_backend_vero`: front-end con `backend = TestClient(crea_app_backend(ArchivioMemoria(), agente_finto(...)))`; `POST /api/chat` → 201 con `titolo == "Nuova chat"`; `GET /api/chat` → elenco con quell'`id`; `DELETE /api/chat/{id}` → 204 e corpo vuoto; `GET /api/chat/{id}` → 404 con `{"errore": f"Chat {id} non trovata"}`.
  - `test_inoltro_corpo_e_codice`: back-end finto (`httpx.MockTransport`) che registra la richiesta e risponde 502 `{"errore": "Errore dell'agente: x"}`; `POST /api/chat/3/messaggi` con `{"testo": "ciao", "conferme": []}` → il finto riceve `POST /chat/3/messaggi` con lo stesso JSON; il front-end restituisce 502 e lo stesso corpo.
  - `test_backend_non_raggiungibile`: MockTransport che solleva `httpx.ConnectError` → 503, `"errore"` contiene `"Back-end non raggiungibile"`.
- [ ] **Passo 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_servizio_frontend.py -v` → falliscono (modulo assente).
- [ ] **Passo 3: implementare** `app.py` e `__main__.py`. L'inoltro è una route `async` che legge il corpo con `await request.body()` e chiama il client sincrono in `run_in_threadpool(backend.request, metodo, "/" + percorso, params=..., content=corpo, headers={"content-type": ...} se presente)`, così un turno lungo non blocca le altre richieste; restituisce `Response(risposta.content, risposta.status_code, media_type=content-type della risposta)`. `httpx.TransportError` → `JSONResponse(503, {"errore": f"Back-end non raggiungibile su {backend.base_url}"})`.
  Esportare l'OpenAPI del back-end nel file JSON indicato; aggiornare `.env.example`.
- [ ] **Passo 4:** test del file → verdi; suite completa `.\.venv\Scripts\python.exe -m pytest -q` → 796 + nuovi, tutti verdi.

### Task 2: pagina di chat

**File:**
- Modifica: `src/assistente/servizio_frontend/static/index.html`
- Crea: `src/assistente/servizio_frontend/static/app.js`, `static/stile.css`

**Interfacce:**
- Consuma: `/api/chat` (GET, POST), `/api/chat/{id}` (GET, DELETE), `/api/chat/{id}/messaggi` (POST `{testo, conferme}` → `{risposta, strumenti_usati, conferme_richieste}`), formati dal file OpenAPI del Task 1.

- [ ] **Passo 1: struttura e stile** — layout della specifica (§ Interfaccia): colonna con «Nuova chat» ed elenco, area messaggi, riquadro errori chiudibile, campo + «Invia», finestra di conferma (`<dialog>`). Responsive essenziale (colonna sopra su schermi stretti).
- [ ] **Passo 2: `app.js`** — una funzione `chiama(metodo, percorso, corpo)` che restituisce il JSON o lancia un errore con il testo di `errore` (altrimenti «Errore HTTP <codice>»; errore di rete: «Front-end non raggiungibile»). Sopra: carica elenco, apri chat, nuova chat, elimina (con `confirm`), invia. Invio: mostra subito la domanda, disattiva campo e pulsante, indicatore «L'assistente sta rispondendo…»; se `conferme_richieste` non è vuota apre il `<dialog>` con strumento e argomenti, «Conferma» ripete la stessa domanda con `conferme`, «Annulla» non invia nulla; a risposta arrivata rilegge chat ed elenco e mostra `strumenti_usati` sotto l'ultima risposta; in errore rimette la domanda nel campo. Testi inseriti con `textContent` (mai `innerHTML` con dati del modello).
- [ ] **Passo 3: controllo funzionale** — `docker compose up -d postgres`; avvio di server MCP, servizi HTTP, agente, back-end e `python -m assistente.servizio_frontend`; su `http://127.0.0.1:8004` creare una chat, fare una domanda, eliminarla. Suite completa verde.

### Task 3: documentazione ed evidenze

**File:**
- Modifica: `README.md` (sezione «Front-end delle chat (Step 8)»: variabili, avvio PowerShell, uso, diagnosi: back-end spento → 503)
- Modifica: `CLAUDE.md` (regola «Confini» approvata nella specifica; riga `servizio_frontend/` e comando di avvio in «Struttura e comandi» solo dopo approvazione del testo)
- Modifica: `prove_reali/PROVE.md` (sezione Step 8: F1–F4 con data, comandi ed esito)

- [ ] **Passo 1:** README e `CLAUDE.md` (sottoporre all'utente il testo della riga di struttura prima di scriverla).
- [ ] **Passo 2: evidenze, una volta ciascuna, dal browser:**
  - F1 conversazione completa con uso di uno strumento (per esempio «Che ore sono a Tokyo?» → `orologio`);
  - F2 chat creata dall'interfaccia presente dopo il riavvio di front-end, back-end e container `postgres` (senza `-v`);
  - F3 agente spento: errore 503 mostrato, l'interfaccia resta utilizzabile (elenco e lettura funzionano);
  - F4 ciclo di conferma di `elimina_nota`: finestra mostrata, «Annulla» non salva, «Conferma» elimina.
  Esiti in `prove_reali/PROVE.md`, con quanto resta da provare.
- [ ] **Passo 3:** suite completa verde; `git status` e diff da mostrare all'utente; commit solo su sua autorizzazione (Conventional Commits in italiano, per esempio `feat(frontend): ...`, `docs: ...`).
