# Handoff — Lezione 6, Step 4 (2026-11-16)

Documento per avviare lo Step 4 in una nuova sessione Claude Code. Va letto per intero prima di qualsiasi altra azione.

> **Lo Step 4 non è iniziato.** Non ci sono brainstorming, specifica, piano né codice. Si parte dal brainstorming con Superpowers (`superpowers:brainstorming`). Niente codice, ramo o commit prima che l'utente abbia approvato la specifica e poi il piano.

## 1. Stato del progetto (verificato alla scrittura)

- **Repository:** `repo-lab-llm`, progetto in `assistente-laboratorio/`. Le altre cartelle sono altre lezioni: non leggerle per copiarne il codice e non modificarle.
- **Ramo:** `dev`, allineato a `origin/dev` dopo il push dello Step 3. Nessun ramo di lavoro aperto. `main` invariato (`9a6c073`).
- **Ultimo commit dello Step 3:** `c975c41` Merge branch 'feat/riassunto' into dev. Sopra c'è il commit di questo handoff, **non pushato**.
- **Test:** **636 verdi** su `dev` (`.\.venv\Scripts\python.exe -m pytest -q`).
- **Non tracciato:** `../LLM_Lez_6.pdf`, materiale del corso, **mai** in Git.
- **Step completati della Lezione 6** (specifiche e piani in `docs/superpowers/`, prove reali in `prove_reali/PROVE.md`):
  - **Step 1 Router di ambito:** merge `8f7f9b8`.
  - **Step 2 Revisore:** merge `086228c`.
  - **Step 3 Riassunto della cronologia:** merge `c975c41`. Specifica `specs/2026-11-15-riassunto-design.md`, rivista il 2026-11-16 (cornice B.1, §13.4).
- **`CLAUDE.md`:** aggiornato con il modulo `riassunto`. Si modifica di nuovo solo con autorizzazione esplicita, a fine Step.

## 2. Obiettivo dello Step 4: Resource MCP — preferenze dell'utente (confermato)

**Fonte:** slide «Step 4» di `../LLM_Lez_6.pdf`, pagina 8. Contenuto recuperato e verificato dall'utente il 2026-11-16; non serve riaprire il PDF.

**Requisiti della slide:**

1. Il server MCP espone la resource `utente://preferenze`, che contiene:
   - lingua delle risposte;
   - fuso orario predefinito;
   - stile delle risposte (sintetico o dettagliato).
2. L'applicazione host legge la resource **all'inizio di ogni sessione** e inserisce le preferenze **in cima al prompt di sistema**.
3. La resource **non** va esposta tra gli strumenti passati a `bind_tools`: la lettura la decide l'host, non il modello.
4. Se la resource non è disponibile, si usano **valori predefiniti** e la situazione viene **segnalata nei log**.

**Obiettivo didattico:** modificando il file delle preferenze, il comportamento dell'agente cambia senza modificare il codice.

**Evidenze richieste:**
- alla domanda «Che ore sono?» l'agente usa il fuso predefinito senza chiederlo (la slide suggerisce di provare con `America/New_York`);
- modificando lingua o stile nel file delle preferenze, la sessione successiva risponde di conseguenza;
- la lettura della resource è visibile nei log, separata dalle chiamate ai tool.

**Fuori ambito:** lo Step 5 tratta i **Prompt MCP** richiamati esplicitamente dall'utente. Non anticiparlo nello Step 4, né anticipare gli step successivi (agente come servizio HTTP, back-end con salvataggio delle chat, front-end, Compose per componente).

**Nella specifica:** riportare questi requisiti e queste evidenze nel testo esatto qui sopra.

## 3. Architettura attuale rilevante (verificata su `c975c41`)

```
START → riassunto → router ─┬─ conversazione → modello ─┬─ tool_calls → strumenti → modello
                            │                           ├─ risposta vuota → END
                            │                           └─ risposta → revisore ─┬─ coerente / fail-open / limite → END
                            │                                                   └─ da correggere → modello (osservazione)
                            └─ fuori_ambito → rifiuto → END
```

- **Server MCP** (`server_mcp.py`, FastMCP 4.1.6, solo Streamable HTTP sulla porta 8001):
  - espone **solo strumenti**: `aggiungi_nota`, `elenca_note`, `elimina_nota` (con `annotations={"destructiveHint": True}`) e `meteo`;
  - non espone **nessuna resource e nessun prompt**;
  - le note stanno in SQLite (`note.py`, `NOTE_DB_PATH`).
- **Client MCP** (`mcp_client.py`):
  - ponte sincrono sopra il client asincrono di FastMCP;
  - `scopri_strumenti` usa `list_tools()`: nome, descrizione e schema non si scrivono mai a mano;
  - la conferma nel terminale scatta in base a `destructiveHint` letto dalla discovery;
  - `verifica_mcp.py` è il controllo di salute usato da Compose.
  - Oggi non esiste discovery di resource o prompt.
- **Composizione degli strumenti all'avvio:** `strumenti.componi_strumenti` mette insieme strumenti locali, HTTP e MCP. Senza server MCP l'agente parte con un avviso.
- **Stato e sessione:**
  - `Stato` contiene `messages`, `riassunto`, `inizio_turno`, `revisioni` e gli altri campi del grafo;
  - la cronologia vive in una `Sessione` immutabile (`terminale.py`);
  - `esegui_turno` passa copie dei messaggi e, se il turno fallisce, restituisce la sessione ricevuta.
- **Limite di passaggi:** `1 (Riassunto) + 1 (Router) + (MAX_REVISIONI + 1) × (MAX_PASSAGGI + 1)`. Un nodo nuovo nel grafo cambierebbe formula e caratterizzazione: i valori si **misurano**, non si adattano.
- **Configurazione:** le variabili sono validate in `config.py` e documentate in `.env.example` e nel README.
- **Docker Compose:** servizi `assistente`, `servizi-http` e `server-mcp`. Le note stanno nel volume `dati-note`; `compose.yaml` non è stato toccato dallo Step 3.

## 4. Limitazioni note (non riaprire senza motivo)

- **Step 3:**
  - il Router rifiuta «Come mi chiamo?» quando il nome è solo nel riassunto;
  - l'agente può scrivere «Ho salvato» anche se non salva nulla;
  - la soglia conta messaggi, non token;
  - caso A1: compressione a ogni turno quando gli ultimi turni bastano a superare la soglia;
  - negli elenchi lunghi singoli elementi possono andare persi.
- **Rilievi minori rinviati dalla review dello Step 3, da decidere con l'utente:**
  - test M5 per `(type, content)` invece di `model_dump`;
  - testo di un `AIMessage` con `tool_calls` non trascritto;
  - `ToolMessage` che precede la propria chiamata trascritto due volte.
- **Step 1–2:**
  - falsi rifiuti del Router (per esempio «cena aziendale con budget», «400 diviso 8») e del Revisore su risposte corrette;
  - errori di calcolo occasionali dell'agente;
  - latenze (mediane): Router circa 36 s, Revisore circa 10 s, riassuntore circa 10 s quando comprime.
- **Anomalia osservata:** il Router può generare migliaia di token di ragionamento con `reasoning_effort="none"`, fino a esaurire il contesto e finire in fail-open. Visto solo con una cornice scartata.

## 5. Modo di lavorare (direttive dell'utente)

- **Sviluppo pragmatico, dal 2026-11-16, vale per tutti gli step:**
  - test proporzionati al rischio;
  - non ripetere verifiche già superate su parti non modificate;
  - al massimo 2 tentativi di correzione del comportamento del modello locale, poi documentare il limite e proporre come procedere;
  - una prova reale mirata per ogni modifica di prompt;
  - risolvere i problemi bloccanti e documentare i minori.
- **Restano obbligatorie le approvazioni esplicite** dell'utente su: specifica, piano, `CLAUDE.md`, merge, push.
- **Lezioni dello Step 3:**
  - eseguire la suite completa **prima** di ogni commit;
  - negli spike con il modello reale usare le stesse condizioni dell'applicazione (strumenti collegati all'agente);
  - mettere un limite di durata alle chiamate;
  - intercettare gli errori che l'applicazione gestisce.

## 6. Vincoli

- **Regole in `CLAUDE.md`:**
  - Superpowers: brainstorming → specifica approvata → piano approvato → implementazione;
  - incrementi piccoli verificati;
  - comandi anche per PowerShell;
  - nessun `.env`, cache, pesi o PDF in Git.
- **MCP:**
  - FastMCP, solo Streamable HTTP, niente stdio;
  - quanto arriva dalla discovery non si riscrive mai a mano nel client;
  - nessuna cancellazione senza conferma raccolta dal terminale.
- **Flusso Git:**
  - `dev` → `feat/<nome>` → review indipendente → approvazione esplicita → `git merge --no-ff` su `dev` → suite verde → eliminazione del ramo;
  - mai `main`; push solo su richiesta;
  - Conventional Commits in italiano.
- **Test e prove:**
  - test automatici senza rete né modello; un server FastMCP reale su porta libera è ammesso;
  - prove reali con LM Studio e Docker separate, registrate in `PROVE.md`;
  - per le prove sulle note usare `NOTE_DB_PATH` temporaneo e non toccare `data/note.db`;
  - `.env` va ripristinato dopo le prove Docker.
- **Da preservare:**
  - Router, Revisore e Riassunto con il loro fail-open;
  - `Sessione` immutabile;
  - conferma di `elimina_nota`;
  - avvio ridotto senza servizi.
- **Dipendenze:** nessuna nuova senza accordo.

## 7. Prossima azione

1. Leggere questo handoff e `CLAUDE.md`. Verificare `git status`, `git log -2` (atteso il commit di questo handoff sopra `c975c41`) e la suite (636 verdi).
2. L'obiettivo dello Step 4 è confermato (vedi §2): non serve rileggere la slide.
3. Avviare `superpowers:brainstorming`, poi specifica e piano da sottoporre all'utente. Solo dopo, con autorizzazione, il ramo `feat/<nome>` da `dev`.
