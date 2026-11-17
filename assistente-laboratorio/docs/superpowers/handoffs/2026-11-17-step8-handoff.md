# Handoff — Lezione 6, Step 8 (2026-11-17)

Documento per avviare lo Step 8 in una nuova sessione Claude Code. Va letto per intero, insieme a `CLAUDE.md`, prima di qualsiasi altra azione.

> **Lo Step 8 non è iniziato.** Non ci sono brainstorming, specifica, piano né codice. Si segue il **workflow rapido** (§5): brainstorming → specifica → piano → implementazione, con l'approvazione dell'utente su specifica, piano, commit, merge e push.

## 1. Stato del progetto (verificato alla scrittura)

- **Repository:** `repo-lab-llm`, progetto in `assistente-laboratorio/`. Le altre cartelle sono altre lezioni: non leggerle per copiarne il codice e non modificarle.
- **Ramo:** `dev`, allineato a `origin/dev` su `3f1f1d7` (merge dello Step 7, pushato il 2026-11-17). Nessun ramo di lavoro aperto. `main` invariato.
- **Sopra `3f1f1d7`:** il solo commit di questo handoff, se l'utente ne autorizza il commit.
- **Test:** **796 verdi** su `dev` (`.\.venv\Scripts\python.exe -m pytest -q`, circa 1–2 minuti).
- **Non tracciati:** `../LLM_Lez_6.pdf` (materiale del corso, **mai** in Git); `data/` e `.env` sono ignorati.
- **Step completati della Lezione 6** (specifiche e piani in `docs/superpowers/`, prove in `prove_reali/PROVE.md`):
  - Step 1 Router di ambito: merge `8f7f9b8`;
  - Step 2 Revisore: merge `086228c`;
  - Step 3 Riassunto della cronologia: merge `c975c41`;
  - Step 4 Resource MCP, preferenze: merge `60cfb1e`;
  - Step 5 Prompt MCP, comandi `/prompts` e `/prompt`: merge `d1e8561`;
  - Step 6 Agente come servizio HTTP: merge `5a6a688`;
  - **Step 7 Back-end, API e salvataggio delle chat:** merge `3f1f1d7` (senza review, su decisione dell'utente). Specifica `specs/2026-11-17-backend-chat-design.md`, piano `plans/2026-11-17-backend-chat.md`, prove B1–B4 riuscite.

## 2. Obiettivo dello Step 8: da confermare sulla slide

Lo Step 8 riguarda il **front-end**. L'architettura finale del corso è:

```
Front-end → Back-end → Agente HTTP → LangGraph → LM Studio
              │              └──▶ server MCP
              └──▶ PostgreSQL
```

La slide dello Step 7 dice che il back-end è **l'unico punto di contatto del front-end** e che **il front-end non conosce l'agente**.

**Il testo della slide «Step 8» non è stato letto** (negli Step 4–7 il testo l'ha fornito l'utente).

**Prima azione:** chiedere all'utente il testo della slide «Step 8» (descrizione, obiettivo, cosa realizzare, evidenze richieste) e riportarlo nella specifica. **Non anticipare** lo Step 9 (architettura Docker Compose definitiva).

## 3. Architettura attuale rilevante (su `3f1f1d7`)

```
CLI (terminale) ──HTTP──▶ servizio_agente (8002, senza stato) ──▶ grafo → LM Studio, MCP (8001), servizi HTTP (8000)
                                ▲
servizio_backend (8003) ────────┘
  └──▶ PostgreSQL (Docker, 127.0.0.1:5433)
```

- **API del back-end** (`src/assistente/servizio_backend/app.py`, contratto che il front-end userebbe; OpenAPI su `http://localhost:8003/docs`):
  - `POST /chat` → 201 `{id, titolo, creata_il}` (titolo «Nuova chat», poi i primi 50 caratteri della prima domanda);
  - `GET /chat` → `[{id, titolo, ultimo_messaggio_il}]`, dalla più recente (`null` senza messaggi);
  - `GET /chat/{id}` → `{id, titolo, messaggi: [{ruolo: "utente"|"assistente", testo, creato_il}]}`;
  - `POST /chat/{id}/messaggi` `{testo, conferme}` → `{risposta, strumenti_usati, conferme_richieste}`;
  - `DELETE /chat/{id}` → 204.
  - Errori `{"errore": ...}`: 404 chat inesistente; 503 agente non raggiungibile, LM Studio spento o database non raggiungibile; 502 altro errore dell'agente; 422 richiesta malformata (anche `testo` vuoto). In caso di errore nulla è salvato.
- **Ciclo di conferma di `elimina_nota`:** se `conferme_richieste` non è vuota il back-end non salva nulla; il chiamante deve chiedere all'utente e ripetere **la stessa domanda** con `"conferme": <conferme_richieste>`. Un front-end deve far passare questo ciclo (oggi lo fa solo la CLI, verso l'agente).
- **Il back-end non ha CORS** e ascolta su `127.0.0.1:8003`. Un front-end servito da un'altra origine (porta diversa) nel browser ne avrebbe bisogno: da decidere solo se la slide porta a quel caso.
- **Latenza:** un turno richiede da circa 1 a 3 minuti (Router, agente, Revisore con `google/gemma-4-e2b`): il front-end deve reggere attese lunghe senza timeout brevi.
- **Avvio attuale per provare il back-end:** `docker compose up -d postgres`; poi, con le variabili di `.env` e `$env:PYTHONPATH = "src"`, server MCP, servizi HTTP, agente e `python -m assistente.servizio_backend` (vedi README «Back-end delle chat»). Il back-end **non è ancora in Compose** (Step 9).

## 4. Punti da decidere probabilmente nel brainstorming (solo se la slide li richiede)

Da trattare come domande, non come decisioni già prese:

- **Regola «Niente interfacce grafiche» di `CLAUDE.md`:** un front-end web (o grafico) la cambia. Serve l'accordo esplicito dell'utente e poi l'aggiornamento di `CLAUDE.md` (con autorizzazione), come per la regola di persistenza nello Step 7.
- **Tecnologia del front-end:** per esempio pagine servite da FastAPI con HTML/JS semplice, oppure un framework. Ogni dipendenza o strumento nuovo (librerie JS, Node, template engine) va proposto, motivato e concordato; preferire la soluzione più semplice compatibile con il progetto.
- **Dove gira e come raggiunge il back-end:** stesso processo/origine del back-end o servizio separato (CORS); non anticipare la composizione Docker dello Step 9.
- **Funzioni minime:** quelle delle cinque operazioni del back-end (elenco, nuova chat, lettura, invio, eliminazione) e la conferma di `elimina_nota`; restano fuori i prompt MCP, a meno che la slide li chieda.
- **Test:** la suite resta senza rete né browser; per il front-end valutare il minimo ragionevole (per esempio che le pagine vengano servite), il resto con il controllo funzionale reale.

## 5. Modo di lavorare: workflow rapido (direttiva dell'utente dal 2026-11-17)

**Quattro fasi Superpowers, e solo quelle:**
1. **Brainstorming:** requisiti della slide; solo le decisioni davvero necessarie, **una domanda alla volta** con una proposta concreta; la soluzione più semplice compatibile con il progetto; niente microdecisioni o casi limite.
2. **Specifica:** sintetica, con le decisioni approvate, in `docs/superpowers/specs/`. **Niente** builder check, review indipendenti o esperimenti.
3. **Piano:** pochi task concreti in `docs/superpowers/plans/`; **nessun** task dedicato solo a test, benchmark, spike o review. Attendere l'approvazione.
4. **Implementazione:** dopo l'approvazione del piano, ramo `feat/<nome>` da `dev`; solo i task approvati, in linea nella sessione principale. TDD non obbligatorio; la suite esistente resta verde; verifica limitata a un **controllo funzionale essenziale** (e alle evidenze minime della slide), una volta, con esiti in `prove_reali/PROVE.md`. Un errore concreto si corregge senza nuovo brainstorming.

Negli Step 6 e 7 il merge è avvenuto senza review per decisione dell'utente: chiedere di nuovo al momento del merge.

## 6. Vincoli (da `CLAUDE.md`, invariati)

- Solo tecnologie concordate: FastAPI, FastMCP (solo Streamable HTTP), LangGraph, LM Studio sull'host, PostgreSQL con `psycopg`; niente RAG, workflow, cloud o framework non concordati; dipendenze nuove solo con accordo.
- Da preservare: back-end come unico punto di contatto del front-end e suo contratto; agente HTTP senza stato e suo contratto (`/chat`, `/stato`, `/prompts`); Router, Revisore e Riassunto con il loro fail-open; `Sessione` immutabile; conferma di `elimina_nota` raccolta dall'utente, indipendente dal modello; CLI con `/prompts` e `/prompt`; avvio ridotto senza servizi.
- Git: `dev` → `feat/<nome>` → approvazione esplicita → `git merge --no-ff` su `dev` → suite verde → eliminazione del ramo; Conventional Commits in italiano; mai `main`; push solo su richiesta; mai `.env`, `data/`, PDF, cache o credenziali in Git.
- Nessuna operazione Git e nessuna modifica a `CLAUDE.md` senza autorizzazione esplicita. Comandi documentati anche per PowerShell.

## 7. Limitazioni note (non riaprire senza motivo)

- **Step 7:** porta 5432 occupata sull'host da un PostgreSQL di Windows (Compose usa 5433); con `localhost` ogni connessione di psycopg attende ~5 s (si usa `127.0.0.1`); ciclo di conferma e database che cade durante l'uso verificati solo con test simulati; titolo della chat non modificabile.
- **Step 6:** prima richiesta di cancellazione lenta (192 s); servizio `agente` in Compose mai avviato (solo `docker compose config`).
- **Step 5:** `riassumi_conversazione` omette il turno compresso; R7 Docker non eseguita; ogni riga con `/` è un comando.
- **Step 1–4:** falsi rifiuti di Router e Revisore; Router lento (40–80 s); «Come mi chiamo?» rifiutato dopo la compressione; testi fissi in italiano.

## 8. Prossima azione

1. Leggere questo handoff e `CLAUDE.md`. Verificare con una sola esecuzione `git status`, `git log -2` (atteso `3f1f1d7` in cima, oppure il commit di questo handoff sopra `3f1f1d7`) e la suite (796 verdi). Se qualcosa non corrisponde, fermarsi e dirlo.
2. Chiedere all'utente il testo della slide «Step 8» (§2).
3. Brainstorming rapido (§5), partendo dalla regola «Niente interfacce grafiche» (§4); poi specifica e piano da sottoporre; solo dopo l'approvazione del piano, ramo `feat/<nome>` da `dev` e implementazione.
