# Handoff — Lezione 6, Step 5 (2026-11-16)

Documento per avviare lo Step 5 in una nuova sessione Claude Code. Va letto per intero prima di qualsiasi altra azione.

> **Lo Step 5 non è iniziato.** Non ci sono brainstorming, specifica, piano né codice. Si parte dal brainstorming con Superpowers (`superpowers:brainstorming`). Niente codice, ramo o commit prima che l'utente abbia approvato la specifica e poi il piano.

## 1. Stato del progetto (verificato alla scrittura)

- **Repository:** `repo-lab-llm`, progetto in `assistente-laboratorio/`. Le altre cartelle sono altre lezioni: non leggerle per copiarne il codice e non modificarle.
- **Ramo:** `dev`, allineato a `origin/dev` dopo il push dello Step 4 (`60cfb1e`). Nessun ramo di lavoro aperto. `main` invariato (`9a6c073`).
- **Sopra `60cfb1e`:** il solo commit di questo handoff, se l'utente ne autorizza il commit.
- **Test:** **696 verdi** su `dev` (`.\.venv\Scripts\python.exe -m pytest -q`, circa 1–2 minuti).
- **Non tracciati:**
  - `../LLM_Lez_6.pdf`, materiale del corso, **mai** in Git;
  - `data/preferenze.json`, file reale delle preferenze, escluso perché `data/` è ignorata; contiene i valori dell'esempio.
- **Step completati della Lezione 6** (specifiche e piani in `docs/superpowers/`, prove reali in `prove_reali/PROVE.md`):
  - **Step 1 Router di ambito:** merge `8f7f9b8`.
  - **Step 2 Revisore:** merge `086228c`.
  - **Step 3 Riassunto della cronologia:** merge `c975c41`.
  - **Step 4 Resource MCP, preferenze dell'utente:** merge `60cfb1e`. Specifica `specs/2026-11-16-preferenze-design.md`, piano `plans/2026-11-16-preferenze.md`.
- **`CLAUDE.md`:** aggiornato con il modulo `preferenze`. Si modifica di nuovo solo con autorizzazione esplicita, a fine Step.

## 2. Obiettivo dello Step 5: da confermare sulla slide

**Il testo della slide «Step 5» non è stato letto.** Il PDF non si apre con gli strumenti disponibili: mancano `pdftoppm` e `pypdf`, e il testo è codificato nei font. Per lo Step 4 il testo l'ha recuperato e verificato l'utente.

**Unica informazione confermata dall'utente (2026-11-16):** lo Step 5 riguarda i **Prompt MCP richiamati esplicitamente dall'utente**.

**Prima azione:** chiedere all'utente il testo della slide «Step 5». Servono i requisiti, le evidenze richieste e gli eventuali vincoli, per esempio come l'utente richiama un prompt dal terminale e se il prompt passa per il grafo. La specifica deve riportarli nel testo esatto. Non anticipare gli step successivi: agente come servizio HTTP, back-end con salvataggio delle chat, front-end, Compose per componente.

**Differenza da tenere presente rispetto allo Step 4:**
- una **resource** la legge l'host da solo, all'avvio;
- un **prompt** MCP è un modello di messaggio esposto dal server, con argomenti, e secondo l'utente lo richiama **l'utente** in modo esplicito.

In nessuno dei due casi lo sceglie il modello, e nessuno dei due va passato a `bind_tools`.

## 3. Architettura attuale rilevante (verificata su `60cfb1e`)

```
Avvio (terminale.main)
  config → componi_strumenti: discovery MCP (attesa MCP_ATTESA_AVVIO) → carica_preferenze (resource) → orologio con il fuso
         → crea_modello(bind_tools: solo strumenti) → costruisci_grafo(..., preferenze)

Turno
START → riassunto → router ─┬─ conversazione → modello ─┬─ tool_calls → strumenti → modello
                            │                           ├─ risposta vuota → END
                            │                           └─ risposta → revisore ─┬─ coerente / fail-open / limite → END
                            │                                                   └─ da correggere → modello (osservazione)
                            └─ fuori_ambito → rifiuto → END
```

- **Server MCP** (`server_mcp.py`, FastMCP 4.1.6, solo Streamable HTTP sulla porta 8001):
  - **strumenti:** `aggiungi_nota`, `elenca_note`, `elimina_nota` (con `destructiveHint`), `meteo`;
  - **resource:** `utente://preferenze` (`application/json`). Il server rilegge il file a ogni richiesta, con `utf-8-sig`; se non lo legge, solleva `ResourceError`;
  - **nessun prompt** MCP;
  - `crea_server(archivio, client_http=None, percorso_preferenze=None)`, con percorso da `PREFERENZE_PATH` e predefinito calcolato dalla posizione del modulo.
- **Client MCP** (`mcp_client.py`), ponte sincrono `_esegui` sopra il client asincrono:
  - `scopri_strumenti` usa `list_tools()`: nome, descrizione e schema non si scrivono mai a mano;
  - `leggi_resource(url, uri, timeout)` usa `read_resource`; gli errori diventano `ErroreMcp`;
  - un'eventuale funzione per i prompt va scritta sullo stesso schema: `asyncio.timeout`, `Client(url, timeout=...)`, errori convertiti in `ErroreMcp`;
  - le API FastMCP vanno **verificate sulla libreria installata** prima della specifica (`get_prompt`, `list_prompts`), come per `read_resource` nella spec dello Step 4 §3.1.
- **Preferenze** (`preferenze.py`):
  - `Preferenze` (immutabile), `PREFERENZE_PREDEFINITE`, `interpreta_preferenze`, `carica_preferenze(config, leggi)`, `testo_prompt`;
  - logger `assistente.preferenze`.
- **Agente:** riceve **sempre** un solo `SystemMessage` temporaneo: blocco delle preferenze, poi, se c'è un riassunto, una riga vuota e la cornice B.1. Il messaggio non entra nello stato.
- **Terminale** (`terminale.py`):
  - `esegui_chat` legge le righe con `input("Tu: ")`;
  - `esci` termina;
  - oggi **non esistono comandi speciali** (niente `/`): un richiamo esplicito di un prompt da parte dell'utente sarebbe il primo;
  - la cronologia vive nella `Sessione` immutabile;
  - `esegui_turno` passa copie dei messaggi e, se il turno fallisce, restituisce la sessione ricevuta.
- **Limite di passaggi:** `1 (Riassunto) + 1 (Router) + (MAX_REVISIONI + 1) × (MAX_PASSAGGI + 1)`. Lo Step 4 non l'ha cambiato. Un nodo nuovo cambierebbe formula e caratterizzazione: i valori si **misurano**, non si adattano.
- **Docker Compose:** servizi `assistente`, `servizi-http`, `server-mcp`. Il servizio `server-mcp` monta:
  - il volume `dati-note` su `/data`;
  - `./data` in sola lettura su `/preferenze`.

## 4. Limitazioni note (non riaprire senza motivo)

- **Step 4:**
  - il rifiuto del Router, gli avvisi e le conferme restano in italiano qualunque sia la lingua preferita;
  - lingua e stile dipendono dal modello: lo stile non si nota su risposte di una frase, come le conversioni;
  - con il file mancante il server registra il traceback di FastMCP;
  - il container `server-mcp` vede tutta la cartella `data/` in sola lettura.
- **Rilievi minori rinviati dalla review dello Step 4, da decidere con l'utente:**
  - su Windows `ZoneInfo` accetta `Europe\Rome` e `utc` (comportamento ereditato da `leggi_orologio`); su Linux probabilmente no;
  - il parametro `percorso_preferenze` di `crea_server` oscura la funzione omonima del modulo;
  - i nomi delle chiavi sconosciute non sono troncati nei log.
- **Step 3:**
  - il Router rifiuta «Come mi chiamo?» quando il nome è solo nel riassunto;
  - l'agente può scrivere «Ho salvato»;
  - la soglia conta messaggi, non token;
  - caso A1;
  - negli elenchi lunghi singoli elementi possono andare persi.
- **Rilievi minori rinviati dallo Step 3:**
  - test M5 per `(type, content)`;
  - testo di un `AIMessage` con `tool_calls` non trascritto;
  - `ToolMessage` che precede la propria chiamata trascritto due volte.
- **Step 1–2:**
  - falsi rifiuti del Router e del Revisore;
  - errori di calcolo occasionali.
- **Latenze** (prove dello Step 4): Router 28–52 s, Revisore 6–14 s. Una sessione da 2 domande richiede circa 220 s in locale; una da 1 domanda in Docker circa 66 s.
- **Anomalia del Router:** può generare migliaia di token di ragionamento nonostante `reasoning_effort="none"`. Nello Step 4 è successo con una domanda esplicativa: 1005 s, poi `LengthFinishReasonError` e fail-open. Nelle prove reali va messo in conto e un limite di durata aiuta.

## 5. Modo di lavorare (direttive dell'utente)

- **Sviluppo pragmatico, dal 2026-11-16:**
  - test proporzionati al rischio;
  - non ripetere verifiche già superate su parti non modificate;
  - al massimo 2 tentativi di correzione del comportamento del modello locale, poi documentare il limite e proporre come procedere;
  - una prova reale mirata per ogni modifica di prompt;
  - risolvere i problemi bloccanti e documentare i minori.
- **Brainstorming:** l'utente preferisce **una decisione alla volta**, con una proposta concreta e una domanda finale. Approva ogni decisione in modo esplicito.
- **Restano obbligatorie le approvazioni esplicite** dell'utente su: specifica, piano, `CLAUDE.md`, merge, push. Nessuna operazione Git senza autorizzazione.
- **Esecuzione:** nello Step 4 l'utente ha scelto l'esecuzione nativa (`superpowers:executing-plans`) con review indipendente finale del ramo.
- **Lezioni dello Step 4:**
  - una review indipendente della specifica (builder check) **prima** di consegnarla ha trovato problemi reali;
  - misurare i test esistenti che cambieranno con una sonda usa e getta (plugin pytest nella scratchpad) **prima** di scrivere il piano;
  - per le prove reali usare uno script pilota nella scratchpad, che avvia i servizi e pilota il terminale via stdin, con `NOTE_DB_PATH` e `PREFERENZE_PATH` temporanei;
  - nelle sostituzioni via script Python, attenzione a `\n` dentro stringhe triple: due volte è finito un a capo reale nel codice. Per le stringhe con escape usare Edit.

## 6. Vincoli

- **Regole in `CLAUDE.md`:**
  - Superpowers: brainstorming → specifica approvata → piano approvato → implementazione;
  - incrementi piccoli verificati;
  - comandi anche per PowerShell;
  - nessun `.env`, cache, pesi, PDF o `data/` in Git.
- **MCP:**
  - FastMCP, solo Streamable HTTP, niente stdio;
  - quanto arriva dalla discovery non si riscrive mai a mano nel client: per i prompt, nome, descrizione e argomenti devono venire da `list_prompts`;
  - nessuna cancellazione senza conferma raccolta dal terminale.
- **Flusso Git:**
  - `dev` → `feat/<nome>` → review indipendente → approvazione esplicita → `git merge --no-ff` su `dev` → suite verde → eliminazione del ramo;
  - mai `main`; push solo su richiesta;
  - Conventional Commits in italiano.
- **Test e prove:**
  - test automatici senza rete né modello; un server FastMCP reale su porta libera è ammesso (`tests/server_reale.py`);
  - prove reali con LM Studio e Docker separate, registrate in `PROVE.md`;
  - per le prove usare `NOTE_DB_PATH` e `PREFERENZE_PATH` temporanei e non toccare `data/note.db`;
  - `.env` va ripristinato dopo le prove Docker.
- **Da preservare:**
  - Router, Revisore e Riassunto con il loro fail-open;
  - preferenze lette all'avvio con fallback;
  - un solo `SystemMessage` temporaneo;
  - `Sessione` immutabile;
  - conferma di `elimina_nota`;
  - avvio ridotto senza servizi;
  - resource e prompt mai in `bind_tools`.
- **Dipendenze:** nessuna nuova senza accordo.

## 7. Prossima azione

1. Leggere questo handoff e `CLAUDE.md`. Verificare:
   - `git status`;
   - `git log -2`: atteso `60cfb1e` in cima, oppure il commit di questo handoff sopra `60cfb1e`;
   - la suite: 696 verdi.
2. Chiedere all'utente il testo della slide «Step 5» (vedi §2) e confermare l'obiettivo.
3. Avviare `superpowers:brainstorming`, una decisione alla volta, poi specifica con builder check e piano da sottoporre all'utente. Solo dopo, con autorizzazione, il ramo `feat/<nome>` da `dev`.
