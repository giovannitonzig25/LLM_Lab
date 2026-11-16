# Handoff — Lezione 6, Step 6 (2026-11-17)

Documento per avviare lo Step 6 in una nuova sessione Claude Code. Va letto per intero prima di qualsiasi altra azione.

> **Lo Step 6 non è iniziato.** Non ci sono brainstorming, specifica, piano né codice. Si segue il **workflow rapido** del §5: brainstorming → specifica → piano → implementazione, con l'approvazione dell'utente su specifica, piano e merge.

## 1. Stato del progetto (verificato alla scrittura)

- **Repository:** `repo-lab-llm`, progetto in `assistente-laboratorio/`. Le altre cartelle sono altre lezioni: non leggerle per copiarne il codice e non modificarle.
- **Ramo:** `dev`, allineato a `origin/dev` dopo il push dello Step 5 (`d1e8561`). Nessun ramo di lavoro aperto. `main` invariato.
- **Sopra `d1e8561`:** il solo commit di questo handoff, se l'utente ne autorizza il commit.
- **Test:** **770 verdi** su `dev` (`.\.venv\Scripts\python.exe -m pytest -q`, circa 1–2 minuti).
- **Non tracciati:** `../LLM_Lez_6.pdf` (materiale del corso, **mai** in Git); `data/preferenze.json` (ignorato).
- **`.env` dell'utente:** `AMBITO_AGENTE` esteso nello Step 5 con «; spiegazioni introduttive di concetti informatici, come i protocolli usati dagli assistenti.» (uguale a `.env.example`).
- **Step completati della Lezione 6** (specifiche e piani in `docs/superpowers/`, prove in `prove_reali/PROVE.md`):
  - Step 1 Router di ambito: merge `8f7f9b8`;
  - Step 2 Revisore: merge `086228c`;
  - Step 3 Riassunto della cronologia: merge `c975c41`;
  - Step 4 Resource MCP, preferenze: merge `60cfb1e`;
  - **Step 5 Prompt MCP, comandi `/prompts` e `/prompt`:** merge `d1e8561`. Specifica `specs/2026-11-16-prompt-mcp-design.md`, piano `plans/2026-11-16-prompt-mcp.md`.
- **`CLAUDE.md`:** aggiornato con il modulo `comandi` (commit `8472a48`) e con il workflow rapido (commit di questo handoff). Si modifica solo con autorizzazione esplicita.

## 2. Obiettivo dello Step 6: da confermare sulla slide

**Il testo della slide «Step 6» non è stato letto.** Il PDF non si apre con gli strumenti disponibili (mancano `pdftoppm` e `pypdf`, testo codificato nei font): negli Step 4 e 5 il testo l'ha fornito l'utente.

Secondo gli handoff precedenti gli step successivi della Lezione 6 riguardano, nell'ordine da confermare: **agente come servizio HTTP**, back-end con salvataggio delle chat, front-end, Compose per componente. **Non** si sa quale sia lo Step 6.

**Prima azione:** chiedere all'utente il testo della slide «Step 6» (requisiti, evidenze richieste, vincoli) e riportarlo nella specifica. Non anticipare gli step successivi.

## 3. Architettura attuale rilevante (su `d1e8561`)

```
Avvio (terminale.main)
  config → componi_strumenti: discovery MCP → carica_preferenze (resource) → orologio con il fuso
         → crea_modello(bind_tools: solo strumenti) → costruisci_grafo(..., preferenze)
         → esegui_chat(..., elenca=elenca_prompt, ottieni=ottieni_prompt)

Riga dell'utente
  "esci" → fine;  "/..." → comandi.esegui_comando (/prompts, /prompt) → eventuale turno con i messaggi del prompt
  altrimenti → esegui_turno → grafo

Turno (grafo invariato dallo Step 4)
START → riassunto → router ─┬─ conversazione → modello ─┬─ tool_calls → strumenti → modello
                            │                           ├─ risposta vuota → END
                            │                           └─ risposta → revisore ─┬─ fine
                            │                                                   └─ correzione → modello
                            └─ fuori_ambito → rifiuto → END
```

- **Terminale** (`terminale.py`): `esegui_turno(grafo, sessione, domanda, ...)` delega a `esegui_turno_messaggi(grafo, sessione, nuovi, ...)`; `Sessione` immutabile (messaggi + riassunto), nessuna persistenza; in caso di errore il turno restituisce la stessa `Sessione`. Un servizio HTTP dell'agente potrebbe riusare `esegui_turno` / `esegui_turno_messaggi` e `costruisci_grafo` senza toccare il grafo.
- **Server MCP** (`server_mcp.py`, porta 8001): strumenti `aggiungi_nota`, `elenca_note`, `elimina_nota` (`destructiveHint`, conferma raccolta dal terminale), `meteo`; resource `utente://preferenze`; prompt `spiega`, `riassumi_conversazione`.
- **Servizio HTTP esistente** (`servizi_http/`, FastAPI, porta 8000): scadenze e catalogo. Dipendenze `fastapi`, `uvicorn`, `httpx` già concordate.
- **Conferma di `elimina_nota`:** oggi è `terminale.chiedi_conferma` (input da terminale). Un'interfaccia non da terminale dovrà decidere come raccogliere la conferma dell'utente: il vincolo «nessuna cancellazione senza conferma dell'utente» resta.
- **Docker Compose:** servizi `assistente`, `servizi-http`, `server-mcp`; LM Studio sull'host.

## 4. Limitazioni note (non riaprire senza motivo)

- **Step 5:** dopo una compressione `riassumi_conversazione` omette il turno compresso (1 tentativo sul testo, poi chiuso); contenuto di `spiega` limitato dalla conoscenza del modello 2B; R7 (Docker) mai eseguita; ogni riga con `/` è un comando.
- **Minori rinviati dalla review dello Step 5:** test del timeout con server muto per `ottieni_prompt`; test `argomento=C#`; prompt `assistant`+`user` produrrebbero due risposte consecutive; ordine import in `mcp_client.py`.
- **Step 1–4:** falsi rifiuti di Router e Revisore; Router lento (40–80 s) con anomalie di ragionamento lungo; «Come mi chiamo?» rifiutato dopo la compressione; testi fissi in italiano.

## 5. Modo di lavorare: workflow rapido (direttiva dell'utente dal 2026-11-17)

Vale per lo Step 6 e per tutti gli step successivi. Sostituisce la direttiva «sviluppo pragmatico» del 2026-11-16.

**Quattro fasi Superpowers, e solo quelle:**
1. **Brainstorming:** requisiti della slide; solo le decisioni progettuali davvero necessarie; niente domande superflue, microdecisioni o lunghe discussioni su casi limite; sempre la soluzione più semplice compatibile con il progetto.
2. **Specifica:** sintetica, con le decisioni approvate, presentata per approvazione. **Niente** builder check, review indipendenti o esperimenti esplorativi.
3. **Piano:** task concreti e ordinati, non decine di microtask; **nessun** task dedicato solo a test, benchmark, spike o review. Attendere l'approvazione.
4. **Implementazione:** solo i task approvati, senza funzionalità non richieste. TDD **non obbligatorio**, nessuna nuova suite per ogni modifica, niente batterie di test ripetute, simulazioni estese o lunghe prove con il modello locale. Verifica limitata a un **controllo funzionale essenziale** (il codice parte, la funzione principale è utilizzabile). Un errore concreto si corregge senza nuovo brainstorming.

**Eliminati:** spike sul modello locale; prove ripetute con Gemma per ogni scenario; review indipendenti obbligatorie; fasi separate di testing e validazione; benchmark e misure approfondite; lunghi cicli di correzione dei prompt; documentazione dettagliata dei casi limite.

**Restano:** le funzionalità richieste dalla slide; nessun danno intenzionale al codice esistente; verifiche minime indispensabili (non come fase autonoma); le **approvazioni esplicite dell'utente** su specifica, piano e merge, oltre a `CLAUDE.md` e push. Nessuna operazione Git senza autorizzazione.

**`CLAUDE.md`:** le sezioni «Metodo» e «Test e verifiche» sono state aggiornate con questo workflow il 2026-11-17, su autorizzazione dell'utente.

## 6. Vincoli (da `CLAUDE.md`, invariati)

- Solo le tecnologie concordate: FastAPI, FastMCP (solo Streamable HTTP), LangGraph, LM Studio sull'host; niente RAG, workflow, cloud o framework non concordati; dipendenze nuove solo con accordo.
- MCP: quanto arriva dalla discovery non si riscrive a mano; resource e prompt mai in `bind_tools`; nessuna cancellazione senza conferma dell'utente raccolta dall'applicazione.
- Da preservare: Router, Revisore e Riassunto con il loro fail-open; un solo `SystemMessage` temporaneo; `Sessione` immutabile; avvio ridotto senza servizi; preferenze all'avvio; comandi `/prompts` e `/prompt`.
- Git: `dev` → `feat/<nome>` → approvazione esplicita → `git merge --no-ff` su `dev` → eliminazione del ramo; Conventional Commits in italiano; mai `main`; push solo su richiesta; mai `.env`, `data/`, PDF, cache in Git.
- Comandi documentati anche per PowerShell.

## 7. Prossima azione

1. Leggere questo handoff e `CLAUDE.md`. Verificare `git status`, `git log -2` (atteso `d1e8561` in cima, oppure il commit di questo handoff sopra `d1e8561`) e la suite (770 verdi), con una sola esecuzione.
2. Chiedere all'utente il testo della slide «Step 6» (§2).
3. Brainstorming rapido (§5), poi specifica sintetica e piano da sottoporre all'utente; solo dopo l'approvazione del piano, ramo `feat/<nome>` da `dev` e implementazione.
