# Step 9 — Docker Compose definitivo: piano di implementazione

> Esecuzione in linea nella sessione principale (workflow rapido). Passi con checkbox (`- [ ]`).

**Obiettivo:** `docker compose up -d` avvia front-end, back-end, agente e PostgreSQL (più i due servizi interni degli strumenti); l'applicazione si usa dal browser su `http://127.0.0.1:8004`.

**Architettura:** si modifica solo l'infrastruttura (`compose.yaml`, due Dockerfile nuovi) e la documentazione. Nessuna modifica a `src/` né ai test.

**Tecnologie:** Docker Compose, `python:3.13-slim`, `postgres:17.6` (già in uso).

**Specifica:** `docs/superpowers/specs/2026-11-17-compose-definitivo-design.md`

## Vincoli globali

- Nessuna dipendenza, immagine o strumento nuovo; nessuna credenziale in `compose.yaml` (solo riferimenti `${POSTGRES_*}`).
- Mai `docker compose down -v`: il volume `dati-postgres` contiene le chat di prova.
- Nessun timeout nuovo; avvio ridotto dell'agente (`service_started` verso `server-mcp` e `servizi-http`) invariato.
- Ramo `feat/compose-definitivo` da `dev`; commit, merge e modifiche a `CLAUDE.md` solo con autorizzazione esplicita.

## Punti di attenzione

- Porte 8000/8001/8002 non più pubblicate: i comandi del README che le usano dall'host in Docker vanno corretti.
- `docker compose run --rm assistente` deve continuare a funzionare con il profilo `cli`.
- Il `DATABASE_URL` locale di `.env` (127.0.0.1:5433) non deve arrivare al back-end in container: lo sovrascrive `environment`.

---

### Task 1: Dockerfile di back-end e front-end e `compose.yaml`

**File:**
- Crea: `Dockerfile.backend`, `Dockerfile.frontend`
- Modifica: `compose.yaml`

- [ ] **Passo 1:** creare il ramo `feat/compose-definitivo` da `dev`.
- [ ] **Passo 2:** `Dockerfile.backend` e `Dockerfile.frontend`, sul modello del `Dockerfile` attuale: `python:3.13-slim`, stesse `ENV`, `requirements.txt`, solo `COPY src ./src`, utente non root `app` (uid 1000), `CMD ["python", "-m", "assistente.servizio_backend"]` e `CMD ["python", "-m", "assistente.servizio_frontend"]`.
- [ ] **Passo 3:** in `compose.yaml`:
  - togliere `ports` da `server-mcp`, `servizi-http` e `agente`;
  - `assistente`: aggiungere `profiles: ["cli"]`;
  - nuovo `backend`: `build` con `dockerfile: Dockerfile.backend`, `env_file: .env`, `environment` con `DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}`, `AGENTE_URL: http://agente:8002`, `BACKEND_HOST: 0.0.0.0`, `BACKEND_PORT: "8003"`; `depends_on`: `postgres` `service_healthy`, `agente` `service_started`; nessuna porta;
  - nuovo `frontend`: `build` con `dockerfile: Dockerfile.frontend`, `environment` con `BACKEND_URL: http://backend:8003`, `FRONTEND_HOST: 0.0.0.0`, `FRONTEND_PORT: "8004"`; `depends_on`: `backend` `service_started`; `ports: ["127.0.0.1:8004:8004"]`;
  - aggiornare il commento di `postgres` («il back-end per ora si avvia in locale»).
- [ ] **Passo 4:** verificare `docker compose config --quiet` (esito 0) e `docker compose config --services` (senza profilo: `server-mcp`, `servizi-http`, `agente`, `postgres`, `backend`, `frontend`).
- [ ] **Passo 5:** suite: `.\.venv\Scripts\python.exe -m pytest -q` → 800 passed.
- [ ] **Passo 6 (con autorizzazione):** commit `build(compose): back-end, front-end e agente in container, solo il front-end esposto`.

### Task 2: avvio reale, evidenze della slide e documentazione

**File:**
- Modifica: `README.md` (sezione «Avvio con Docker Compose» e diagnosi delle porte), `prove_reali/PROVE.md`, `.env.example` (solo un commento su `DATABASE_URL` in Compose)

- [ ] **Passo 1 (C1):** LM Studio attivo sull'host; `docker compose build`, `docker compose up -d`, `docker compose ps` → sei servizi attivi (`postgres` e `agente` healthy); `curl.exe -s -m 3 http://127.0.0.1:8002/stato` fallisce (agente non esposto); `http://127.0.0.1:8004` risponde.
- [ ] **Passo 2 (C2):** passi espliciti all'utente per il browser (indirizzo, nuova chat, frase «Che ore sono adesso a Tokyo?», cosa controllare); verificare nei log `docker compose logs frontend backend agente` la richiesta e l'uso dello strumento (`orologio`) prima di registrare l'esito.
- [ ] **Passo 3 (C3):** `docker compose down` (senza `-v`), `docker compose up -d`; dal browser la chat di C2 e le chat di prova precedenti sono ancora presenti (verifica anche con `GET /api/chat` via `curl.exe`).
- [ ] **Passo 4:** controllo essenziale `docker compose run --rm assistente` (una domanda, poi uscita).
- [ ] **Passo 5:** README: comando unico `docker compose up -d` e indirizzo del browser, tabella dei servizi e delle porte, CLI con profilo (`docker compose run --rm assistente`), `docker compose logs agente`, `docker compose down` (le chat restano) e `down -v` (le cancella), scostamento stdio dichiarato; correggere i comandi che usavano dall'host le porte 8000/8001/8002 in Docker; solo comandi verificati. `PROVE.md`: esiti C1–C3 e controllo CLI, con data e limiti osservati.
- [ ] **Passo 6:** suite di nuovo verde (800 passed).
- [ ] **Passo 7 (con autorizzazione):** commit `docs: specifica, piano, README e prove reali dello Step 9`; aggiornamento dei comandi Docker in `CLAUDE.md` solo se approvato.
