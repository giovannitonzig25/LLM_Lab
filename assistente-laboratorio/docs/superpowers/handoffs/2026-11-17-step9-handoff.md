# Handoff — Lezione 6, Step 9 (2026-11-17)

Documento per avviare lo Step 9 in una nuova sessione Claude Code. Va letto per intero, insieme a `CLAUDE.md`, prima di qualsiasi altra azione.

> **Lo Step 9 non è iniziato.** Non ci sono brainstorming, specifica, piano né codice. Si segue il **workflow rapido** (§5): brainstorming → specifica → piano → implementazione, con l'approvazione dell'utente su specifica, piano, commit, merge e push.

## 1. Stato del progetto (verificato alla scrittura)

- **Repository:** `repo-lab-llm`, progetto in `assistente-laboratorio/`. Le altre cartelle sono altre lezioni: non leggerle per copiarne il codice e non modificarle.
- **Ramo:** `dev`, allineato a `origin/dev` su `d368c97` (merge dello Step 8, pushato il 2026-11-17). Nessun ramo di lavoro aperto. `main` invariato.
- **Sopra `d368c97`:** il solo commit di questo handoff, se l'utente ne autorizza il commit.
- **Test:** **800 verdi** su `dev` (`.\.venv\Scripts\python.exe -m pytest -q`, circa 1 minuto).
- **Non tracciati:** `../LLM_Lez_6.pdf` (materiale del corso, **mai** in Git); `data/` e `.env` sono ignorati.
- **Servizi:** tutti spenti. Container `postgres` fermato (volume `dati-postgres` conservato, contiene le chat di prova 4 e 6); si riavvia con `docker compose up -d postgres`.
- **Step completati della Lezione 6** (specifiche e piani in `docs/superpowers/`, prove in `prove_reali/PROVE.md`):
  - Step 1 Router di ambito: merge `8f7f9b8`;
  - Step 2 Revisore: merge `086228c`;
  - Step 3 Riassunto della cronologia: merge `c975c41`;
  - Step 4 Resource MCP, preferenze: merge `60cfb1e`;
  - Step 5 Prompt MCP, comandi `/prompts` e `/prompt`: merge `d1e8561`;
  - Step 6 Agente come servizio HTTP: merge `5a6a688`;
  - Step 7 Back-end, API e salvataggio delle chat: merge `3f1f1d7`;
  - **Step 8 Front-end, interfaccia di chat:** merge `d368c97` (senza review, su decisione dell'utente). Specifica `specs/2026-11-17-frontend-chat-design.md`, piano `plans/2026-11-17-frontend-chat.md`, contratto `specs/2026-11-17-openapi-backend.json`, prove F1–F4 riuscite dal browser.

## 2. Obiettivo dello Step 9: da confermare sulla slide

Lo Step 9 riguarda l'**architettura Docker Compose definitiva**. L'architettura finale del corso è:

```
Front-end → Back-end → Agente HTTP → LangGraph → LM Studio (host)
              │              └──▶ server MCP
              └──▶ PostgreSQL
```

**Il testo della slide «Step 9» non è stato letto** (negli Step 4–8 il testo l'ha fornito l'utente; si trova in `../LLM_Lez_6.pdf`).

**Prima azione:** chiedere all'utente il testo della slide «Step 9» (descrizione, obiettivo, cosa realizzare, evidenze richieste) e riportarlo nella specifica. Realizzare solo quanto chiede la slide.

## 3. Architettura attuale rilevante (su `d368c97`)

```
browser ──▶ servizio_frontend (8004) ──/api──▶ servizio_backend (8003) ──▶ servizio_agente (8002) ──▶ LM Studio (host)
                                                    │                          ├──▶ server MCP (8001)
                                                    └──▶ PostgreSQL            └──▶ servizi HTTP (8000)
CLI (terminale) ──────────────────────────────────────────────────────────────▶ servizio_agente (8002)
```

**In Compose oggi (`compose.yaml`, un solo `Dockerfile` `python:3.13-slim`, utente non root, `COPY src` e `prove_reali`):**

| Servizio | Stato | Note |
|---|---|---|
| `server-mcp` | in Compose | porta `127.0.0.1:8001`, volume `dati-note`, `./data` in sola lettura su `/preferenze`, healthcheck con discovery MCP vera |
| `servizi-http` | in Compose | porta `127.0.0.1:8000`, healthcheck su `/salute` |
| `agente` | in Compose | porta `127.0.0.1:8002`, `env_file: .env`, URL interni (`LM_STUDIO_DOCKER_URL`, `MCP_DOCKER_URL`, `SERVIZI_DOCKER_URL`), `depends_on` con `service_started` (avvio ridotto), healthcheck su `/openapi.json`. **Mai avviato davvero** (Step 6: solo `docker compose config`) |
| `assistente` | in Compose | CLI interattiva, `AGENTE_URL=http://agente:8002`, dipende da `agente` healthy |
| `postgres` | in Compose | `postgres:17.6`, `env_file: .env`, volume `dati-postgres`, porta `127.0.0.1:5433` (la 5432 dell'host è occupata), healthcheck `pg_isready` |
| `servizio_backend` | **solo locale** | `python -m assistente.servizio_backend` |
| `servizio_frontend` | **solo locale** | `python -m assistente.servizio_frontend` |

**Configurazione dei due servizi da portare in Compose:**
- **Back-end:** `DATABASE_URL` obbligatoria (in locale `postgresql://…@127.0.0.1:5433/chat`; dentro la rete Compose servirebbe `postgres:5432`), `AGENTE_URL` (predefinito `http://localhost:8002`), `BACKEND_HOST` (`127.0.0.1`: in container va `0.0.0.0`), `BACKEND_PORT` (`8003`). **All'avvio esce con codice 1** se manca `DATABASE_URL` o il database non risponde: in Compose conta la condizione su `postgres` (healthy) o una politica di riavvio.
- **Front-end:** `BACKEND_URL` (predefinito `http://127.0.0.1:8003`; in Compose l'indirizzo interno del back-end), `FRONTEND_HOST` (in container `0.0.0.0`), `FRONTEND_PORT` (`8004`). I file statici stanno in `src/assistente/servizio_frontend/static/`, quindi sono già copiati da `COPY src`. La pagina usa solo percorsi relativi `/api/...`: nessun indirizzo da cambiare nel browser.
- **Credenziali:** solo in `.env` (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`), esempio senza segreti in `.env.example`. Mai credenziali in `compose.yaml`.
- **Latenza:** un turno richiede da 1 a 3 minuti e oltre (fino a 223 s nelle prove dello Step 8): nessun timeout breve in back-end, front-end o healthcheck che ne dipenda.

## 4. Punti da decidere probabilmente nel brainstorming (solo se la slide li richiede)

Da trattare come domande, non come decisioni già prese:

- **Quali servizi entrano e come si chiamano** (per esempio `backend` e `frontend`), e quali porte restano pubblicate sull'host: con l'architettura finale basterebbe esporre il front-end; gli altri potrebbero restare solo nella rete interna. Attenzione a non rompere l'avvio locale né la CLI.
- **`DATABASE_URL` dentro Compose:** variabile dedicata (sul modello di `MCP_DOCKER_URL`) oppure composta da `POSTGRES_*`; scegliere la soluzione più semplice senza credenziali in chiaro nel file Compose.
- **Ordine di avvio e salute:** `depends_on` con `service_healthy` per `postgres` e per l'agente, healthcheck di back-end e front-end; preservare l'avvio ridotto dell'agente (MCP e servizi HTTP con `service_started`).
- **Servizio `assistente` (CLI):** resta com'è o cambia ruolo; non rimuoverlo senza accordo.
- **Evidenze:** probabilmente l'intero percorso browser → front-end → back-end → agente → LM Studio dentro Compose, persistenza dopo `docker compose down` / `up` (senza `-v`), comportamento con un servizio spento. Da prendere dalla slide.
- **Test:** la suite resta senza Docker, rete né modello; per Compose bastano `docker compose config` e le prove reali una volta.

## 5. Modo di lavorare: workflow rapido (direttiva dell'utente dal 2026-11-17)

**Quattro fasi Superpowers, e solo quelle:**
1. **Brainstorming:** requisiti della slide; solo le decisioni davvero necessarie, **una domanda alla volta** con una proposta concreta; la soluzione più semplice compatibile con il progetto; niente microdecisioni o casi limite.
2. **Specifica:** sintetica, con le decisioni approvate, in `docs/superpowers/specs/`. **Niente** builder check, review indipendenti o esperimenti.
3. **Piano:** pochi task concreti in `docs/superpowers/plans/`; **nessun** task dedicato solo a test, benchmark, spike o review. Attendere l'approvazione.
4. **Implementazione:** dopo l'approvazione del piano, ramo `feat/<nome>` da `dev`; solo i task approvati, in linea nella sessione principale. TDD non obbligatorio; la suite esistente resta verde; verifica limitata a un **controllo funzionale essenziale** (e alle evidenze minime della slide), una volta, con esiti in `prove_reali/PROVE.md`. Un errore concreto si corregge senza nuovo brainstorming.

Negli Step 6, 7 e 8 il merge è avvenuto senza review per decisione dell'utente: chiedere di nuovo al momento del merge.

**Prove dal browser (lezione dello Step 8):** dare all'utente passi espliciti (indirizzo esatto, frasi da scrivere, che cosa controllare) e **verificare sempre l'esito nei log** (accessi del front-end, `turno:` dell'agente) prima di registrarlo: al primo giro dello Step 8 l'esito comunicato non trovava riscontro nei log. Per le note usare frasi come «Aggiungi una nota personale con il testo: …» ed «Elimina la mia nota personale «…»»: «Aggiungi una nota: comprare il latte» è stata rifiutata dal Router.

## 6. Vincoli (da `CLAUDE.md`, invariati)

- Solo tecnologie concordate: FastAPI, FastMCP (solo Streamable HTTP), LangGraph, LM Studio sull'host (**mai containerizzato**), PostgreSQL con `psycopg`, front-end HTML/CSS/JS semplice; niente RAG, workflow, cloud o framework non concordati; dipendenze, immagini o strumenti nuovi solo con accordo.
- Da preservare: back-end come unico punto di contatto del front-end e suo contratto; front-end che chiama solo `/api/...` inoltrato al back-end; agente HTTP senza stato e suo contratto (`/chat`, `/stato`, `/prompts`); Router, Revisore e Riassunto con il loro fail-open; `Sessione` immutabile; conferma di `elimina_nota` raccolta dall'utente (CLI e front-end), indipendente dal modello; CLI con `/prompts` e `/prompt`; avvio ridotto senza servizi; avvio locale senza Docker.
- Git: `dev` → `feat/<nome>` → approvazione esplicita → `git merge --no-ff` su `dev` → suite verde → eliminazione del ramo; Conventional Commits in italiano; mai `main`; push solo su richiesta; mai `.env`, `data/`, PDF, cache o credenziali in Git.
- Nessuna operazione Git e nessuna modifica a `CLAUDE.md` senza autorizzazione esplicita. Comandi documentati anche per PowerShell. Dopo ogni modifica a `src/`: `docker compose build`.

## 7. Limitazioni note (non riaprire senza motivo)

- **Step 8:** falso rifiuto del Router su «Aggiungi una nota: comprare il latte»; turni con `elimina_nota` da 183 a 223 s; su Windows `.venv\Scripts\python.exe` avvia un processo figlio (per fermare un servizio avviato in background fermare anche il figlio); LM Studio o database spenti visti dal browser, layout stretto e tema scuro non provati.
- **Step 7:** porta 5432 occupata sull'host (Compose usa 5433); con `localhost` ogni connessione di psycopg attende ~5 s (si usa `127.0.0.1`); database che cade durante l'uso verificato solo con test simulati; titolo della chat non modificabile.
- **Step 6:** prima richiesta di cancellazione lenta (192 s); servizio `agente` in Compose mai avviato (solo `docker compose config`).
- **Step 5:** `riassumi_conversazione` omette il turno compresso; R7 Docker non eseguita; ogni riga con `/` è un comando.
- **Step 1–4:** falsi rifiuti di Router e Revisore; Router lento (40–80 s); «Come mi chiamo?» rifiutato dopo la compressione; testi fissi in italiano.

## 8. Prossima azione

1. Leggere questo handoff e `CLAUDE.md`. Verificare con una sola esecuzione `git status`, `git log -2` (atteso `d368c97` in cima, oppure il commit di questo handoff sopra `d368c97`) e la suite (800 verdi). Se qualcosa non corrisponde, fermarsi e dirlo.
2. Chiedere all'utente il testo della slide «Step 9» (§2).
3. Brainstorming rapido (§5) sui punti del §4 richiesti dalla slide; poi specifica e piano da sottoporre; solo dopo l'approvazione del piano, ramo `feat/<nome>` da `dev` e implementazione.
