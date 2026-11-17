# Handoff — Lezione 6, Step 7 (2026-11-17)

Documento per avviare lo Step 7 in una nuova sessione Claude Code. Va letto per intero, insieme a `CLAUDE.md`, prima di qualsiasi altra azione.

> **Lo Step 7 non è iniziato.** Non ci sono brainstorming, specifica, piano né codice. Si segue il **workflow rapido** (§5): brainstorming → specifica → piano → implementazione, con l'approvazione dell'utente su specifica, piano, commit, merge e push.

## 1. Stato del progetto (verificato alla scrittura)

- **Repository:** `repo-lab-llm`, progetto in `assistente-laboratorio/`. Le altre cartelle sono altre lezioni: non leggerle per copiarne il codice e non modificarle.
- **Ramo:** `dev`, allineato a `origin/dev` su `5a6a688` (merge dello Step 6, pushato il 2026-11-17). Nessun ramo di lavoro aperto. `main` invariato.
- **Sopra `5a6a688`:** il solo commit di questo handoff, se l'utente ne autorizza il commit.
- **Test:** **784 verdi** su `dev` (`.\.venv\Scripts\python.exe -m pytest -q`, circa 1–1,5 minuti).
- **Non tracciati:** `../LLM_Lez_6.pdf` (materiale del corso, **mai** in Git); `data/` è ignorata (`note.db`, `preferenze.json`).
- **Step completati della Lezione 6** (specifiche e piani in `docs/superpowers/`, prove in `prove_reali/PROVE.md`):
  - Step 1 Router di ambito: merge `8f7f9b8`;
  - Step 2 Revisore: merge `086228c`;
  - Step 3 Riassunto della cronologia: merge `c975c41`;
  - Step 4 Resource MCP, preferenze: merge `60cfb1e`;
  - Step 5 Prompt MCP, comandi `/prompts` e `/prompt`: merge `d1e8561`;
  - **Step 6 Agente come servizio HTTP:** merge `5a6a688` (senza review, su decisione dell'utente). Specifica `specs/2026-11-17-agente-http-design.md`, piano `plans/2026-11-17-agente-http.md`, prove H1–H5 riuscite.

## 2. Obiettivo dello Step 7: da confermare sulla slide

Secondo quanto indicato dall'utente all'avvio dello Step 6, lo Step 7 riguarda **back-end, API delle chat e persistenza**. L'architettura finale mostrata dalla slide che precede lo Step 6 è:

```
Front-end → Back-end → Agente → LM Studio
              │           └──▶ server MCP
              └──▶ PostgreSQL
```

**Il testo della slide «Step 7» non è stato letto** (il PDF non si apre con gli strumenti disponibili: negli Step 4–6 il testo l'ha fornito l'utente).

**Prima azione:** chiedere all'utente il testo della slide «Step 7» (descrizione, obiettivo, cosa realizzare, evidenze richieste) e riportarlo nella specifica. **Non anticipare** Step 8 (front-end) e Step 9 (Compose definitivo).

## 3. Architettura attuale rilevante (su `5a6a688`)

```
CLI (terminale, AGENTE_URL) ──HTTP──▶ servizio_agente (FastAPI, 8002, senza stato)
  Sessione in memoria                    └─ agente.esegui_turno_api → grafo → LM Studio
                                                                        ├─▶ server MCP (8001)
                                                                        └─▶ servizi HTTP (8000)
```

- **Grafo** invariato dallo Step 4: `riassunto → router → (agente ⇄ strumenti → revisore) | rifiuto`.
- **`agente.py`:** `Sessione` (messaggi + riassunto, immutabile), `esegui_turno_api(...) -> EsitoTurno`, `ErroreModello` (503/502), conferme per richiesta via `ContextVar`, `costruisci_agente(config)`.
- **API dell'agente** (`servizio_agente/app.py`, contratto che un back-end userebbe):
  - `POST /chat` `{messaggio | messaggi, cronologia, riassunto, conferme}` → `{risposta, cronologia, riassunto, strumenti_usati, conferme_richieste}`; `cronologia` = messaggi LangChain serializzati con `messages_to_dict` (lossless: chiamate agli strumenti e `ToolMessage` compresi).
  - `GET /stato` → `{agente, mcp, modello}`, 200 o 503.
  - `GET /prompts`, `POST /prompts/{nome}` → prompt MCP; 503 se MCP è spento.
  - Errori `{"errore": ...}`: 503 modello irraggiungibile, 502 altri errori del modello, 422 richiesta malformata.
- **Conferma degli strumenti distruttivi:** l'agente non esegue `elimina_nota` senza una conferma `{strumento, argomenti}` identica nella richiesta; altrimenti la restituisce in `conferme_richieste` e il chiamante, dopo aver chiesto all'utente, ripete **lo stesso turno** (stessa cronologia e riassunto) con `conferme`. Un back-end tra CLI/front-end e agente dovrà far passare questo ciclo.
- **CLI** (`terminale.py`): `ClientAgente` (httpx) con `chat`, `elenca_prompt`, `ottieni_prompt`, `stato`; `esegui_chat(client, leggi, scrivi, chiedi=...)`; `main(crea_http=httpx.Client)`. Tiene la `Sessione` in memoria: **oggi nessuna persistenza della conversazione**.
- **Test:** `tests/cli_su_api.py` fa girare la CLI sull'API vera servita da `TestClient` con grafo simulato; `tests/test_servizio_agente.py` copre l'API.
- **Compose:** servizi `server-mcp`, `servizi-http`, `agente` (healthcheck su `/openapi.json`, porta `127.0.0.1:8002`), `assistente` (CLI, `AGENTE_URL=http://agente:8002`, dipende da `agente` `service_healthy`). LM Studio sull'host.

## 4. Punti da decidere probabilmente nel brainstorming (solo se la slide li richiede)

Da trattare come domande, non come decisioni già prese:

- **Persistenza:** `CLAUDE.md` dice «Nessuna persistenza» per la cronologia della conversazione e consente SQLite solo per le note. Salvare le chat cambia questa regola: serve l'accordo esplicito dell'utente e poi l'aggiornamento di `CLAUDE.md` (con autorizzazione).
- **PostgreSQL e dipendenze:** un driver o un ORM (per esempio `psycopg`, SQLAlchemy) sono **dipendenze nuove**: vanno concordate e fissate di versione. PostgreSQL andrebbe in Compose come servizio; non anticipare la riorganizzazione definitiva dello Step 9.
- **Ruolo della CLI:** se resta client dell'agente o diventa client del back-end.
- **Cosa si salva:** la `cronologia` serializzata e il `riassunto` restituiti da `/chat` sono già il formato completo da conservare e rimandare all'agente.
- **Ciclo di conferma** attraverso il back-end (vedi §3).

## 5. Modo di lavorare: workflow rapido (direttiva dell'utente dal 2026-11-17)

**Quattro fasi Superpowers, e solo quelle:**
1. **Brainstorming:** requisiti della slide; solo le decisioni davvero necessarie, **una domanda alla volta** con una proposta concreta; la soluzione più semplice compatibile con il progetto; niente microdecisioni o casi limite.
2. **Specifica:** sintetica, con le decisioni approvate, in `docs/superpowers/specs/`. **Niente** builder check, review indipendenti o esperimenti.
3. **Piano:** pochi task concreti in `docs/superpowers/plans/`; **nessun** task dedicato solo a test, benchmark, spike o review. Attendere l'approvazione.
4. **Implementazione:** dopo l'approvazione del piano, ramo `feat/<nome>` da `dev`; solo i task approvati. TDD non obbligatorio; la suite esistente resta verde; verifica limitata a un **controllo funzionale essenziale** (e alle evidenze minime della slide), una volta, con esiti in `prove_reali/PROVE.md`. Un errore concreto si corregge senza nuovo brainstorming.

Nello Step 6 l'esecuzione è stata fatta in linea nella sessione principale e il merge è avvenuto senza review per decisione dell'utente: chiedere di nuovo al momento del merge.

## 6. Vincoli (da `CLAUDE.md`, invariati)

- Solo tecnologie concordate: FastAPI, FastMCP (solo Streamable HTTP), LangGraph, LM Studio sull'host; niente RAG, workflow, cloud o framework non concordati; dipendenze nuove solo con accordo.
- Da preservare: Router, Revisore e Riassunto con il loro fail-open; un solo `SystemMessage` temporaneo; `Sessione` immutabile; agente senza stato; avvio ridotto senza servizi; preferenze all'avvio; comandi `/prompts` e `/prompt`; conferma di `elimina_nota` raccolta dall'utente, indipendente dal modello.
- Git: `dev` → `feat/<nome>` → approvazione esplicita → `git merge --no-ff` su `dev` → suite verde → eliminazione del ramo; Conventional Commits in italiano; mai `main`; push solo su richiesta; mai `.env`, `data/`, PDF, cache o credenziali in Git (anche quelle di PostgreSQL vanno in `.env`, con un esempio senza segreti in `.env.example`).
- Nessuna operazione Git e nessuna modifica a `CLAUDE.md` senza autorizzazione esplicita. Comandi documentati anche per PowerShell.

## 7. Limitazioni note (non riaprire senza motivo)

- **Step 6:** prima richiesta di cancellazione lenta (192 s: il Revisore respinge la risposta «non confermata» prima che il chiamante possa chiedere la conferma); Docker Compose del nuovo servizio `agente` **mai avviato** (solo `docker compose config`).
- **Step 5:** `riassumi_conversazione` omette il turno compresso; R7 Docker non eseguita; ogni riga con `/` è un comando.
- **Step 1–4:** falsi rifiuti di Router e Revisore; Router lento (40–80 s); «Come mi chiamo?» rifiutato dopo la compressione; testi fissi in italiano.

## 8. Prossima azione

1. Leggere questo handoff e `CLAUDE.md`. Verificare con una sola esecuzione `git status`, `git log -2` (atteso `5a6a688` in cima, oppure il commit di questo handoff sopra `5a6a688`) e la suite (784 verdi). Se qualcosa non corrisponde, fermarsi e dirlo.
2. Chiedere all'utente il testo della slide «Step 7» (§2).
3. Brainstorming rapido (§5), poi specifica e piano da sottoporre; solo dopo l'approvazione del piano, ramo `feat/<nome>` da `dev` e implementazione.
