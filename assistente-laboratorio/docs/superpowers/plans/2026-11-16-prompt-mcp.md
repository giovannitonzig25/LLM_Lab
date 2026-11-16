# Lezione 6, Step 5 — Prompt MCP: comandi riusabili nella CLI: piano di implementazione

> **Per gli esecutori:** SOTTO-SKILL RICHIESTA: `superpowers:executing-plans` (nativa) oppure `superpowers:subagent-driven-development`, secondo la scelta dell'utente. I passi usano la sintassi a caselle (`- [ ]`). Leggere la specifica per intero prima di iniziare.

**Obiettivo:** il server MCP espone i prompt `spiega` e `riassumi_conversazione`; la CLI offre `/prompts` e `/prompt nome argomento=valore`, controlla gli argomenti rispetto a `prompts/list` e manda i messaggi compilati al grafo come una domanda normale.

**Architettura:**
- `server_mcp.py`: due `@server.prompt` in `crea_server`.
- `mcp_client.py`: `PromptMcp`, `ArgomentoPrompt`, `elenca_prompt`, `ottieni_prompt` (stesso schema di `leggi_resource`).
- Modulo nuovo `comandi.py`: scomposizione della riga, controllo, testi, conversione dei messaggi ed `esegui_comando`, che restituisce righe da stampare ed eventuali messaggi per il turno.
- `terminale.py`: `esegui_turno_messaggi` (corpo attuale di `esegui_turno`), smistamento delle righe con `/` in `esegui_chat`, collegamento in `main`.
- Grafo, stato, Router, Revisore, Riassunto, preferenze, strumenti e Compose **non cambiano**.

**Stack:** Python 3.13, `fastmcp==4.1.6`, `langgraph==1.2.19`, `langchain-core`, pytest; `shlex` della libreria standard. Nessuna dipendenza nuova.

**Specifica:** `docs/superpowers/specs/2026-11-16-prompt-mcp-design.md`, approvata il 2026-11-16. È vincolante: i riferimenti §n rimandano lì.

**Stato del piano:** bozza, da approvare. Review indipendente del piano fatta il 2026-11-16: nessun problema grave; tre ambiguità minori risolte in T3 (`/prompt` con `elenca` in errore, precedenza di `CLIENT_NON_CONFIGURATO`, WARNING solo per il controllo fallito), una scelta confermata in T2 (testo dell'errore per un messaggio non testuale).

## Vincoli globali

- **Solo lo Step 5.** Esclusi: agente come servizio HTTP, back-end, front-end, Compose per componente; altri comandi oltre a `/prompts` e `/prompt`; cache dei prompt; completamento automatico.
- **Non cambiano:** `grafo.py`, `router.py`, `revisore.py`, `riassunto.py`, `preferenze.py`, `strumenti.py`, `config.py`, `compose.yaml`, `Dockerfile`. Limite di passaggi e formula invariati.
- **Discovery:** nome, descrizione e argomenti dei prompt vengono solo da `list_prompts()`. Nel client nessun nome di prompt, argomento o livello scritto a mano (i test possono usarli).
- **Prompt mai in `bind_tools`:** `elenca_prompt` e `ottieni_prompt` non producono `BaseTool` e non sono chiamate da `componi_strumenti`.
- **Testi dei prompt:** Appendice A della specifica, **testo esatto**; nei test si leggono dal file della specifica (blocchi ```` ```text ````), come fa `blocco_testo` in `tests/test_riassunto.py`.
- **Descrizioni dei prompt** (§5): `spiega` → `Spiega un argomento al livello scelto: base, intermedio o avanzato (predefinito base).`; `riassumi_conversazione` → `Riassume la conversazione della sessione in corso nello stile indicato, testo libero (predefinito breve).`
- **Testi fissi della CLI** (esatti):
  - `COMANDO_SCONOSCIUTO = "Comando sconosciuto. Comandi disponibili: /prompts, /prompt nome argomento=valore"`
  - `USO_PROMPTS = "Uso: /prompts"`
  - `USO_PROMPT = "Uso: /prompt nome argomento=valore … (valori con spazi tra virgolette doppie). Usa /prompts per l'elenco."`
  - `"Nessun prompt disponibile."`, `"Prompt disponibili:"`
  - prefissi `"Prompt MCP non disponibili: "` (errore di `elenca`), `"Prompt non eseguito: "` (errore di `ottieni`), `"Prompt non utilizzabile: "` (conversione)
  - `CLIENT_NON_CONFIGURATO = "Prompt MCP non disponibili: client non configurato."`
- **Log:** `assistente.mcp` per scoperta, richiamo, messaggi ottenuti ed errori (§6.3); `assistente.comandi` per le richieste respinte dall'host (§8). Formato libero, contenuti obbligatori.
- **Test** senza modello né rete esterna; server FastMCP reale su porta libera ammesso (`tests/server_reale.py`).
- **Git** (CLAUDE.md): ramo `feat/prompt-mcp` da `dev`; Conventional Commits in italiano; prima di ogni commit suite completa, `git status`, controllo del diff, staging selettivo (mai `.env`, `../LLM_Lez_6.pdf`, cache, `data/`); messaggi che terminano con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; review indipendente e **approvazione esplicita dell'utente** prima di `git merge --no-ff`; nessun push; nessun merge su `main`.
- **Comandi** da `assistente-laboratorio/` in PowerShell. Test: `.\.venv\Scripts\python.exe -m pytest -v`. Base di partenza: **696 test verdi**.
- **Sviluppo pragmatico:** test proporzionati al rischio; al massimo 2 tentativi di correzione del comportamento del modello locale (solo sul testo dei prompt nel server, con accordo dell'utente perché l'Appendice A è fissata), poi si documenta il limite.

## Test esistenti che cambiano (misurati il 2026-11-16)

Sonda usa e getta su una copia di `src/`, `tests/` e `docs/` nella scratchpad, con le modifiche minime della specifica: due prompt in `crea_server`, `esegui_turno` come involucro di `esegui_turno_messaggi`, parametri `elenca`/`ottieni` in `esegui_chat`, intercettazione delle righe con `/`, collegamento in `main`. Risultato: **696 passed, nessun fallimento**.

**Nessun test esistente cambia.** In particolare `test_terminale.py::test_main_bind_tools_senza_resource` (elenco esatto degli strumenti legati) resta verde: è già la prova che i prompt non finiscono in `bind_tools`. Se un test esistente fallisce, fermarsi e riferire all'utente.

## Review Focus

1. **Server che accetta la connessione ma non risponde** durante `/prompts`: deve finire entro `MCP_TIMEOUT` con `ErroreMcp` e la chat deve continuare. Test in T2 con `porta_muta()`.
2. **Server spento tra `list_prompts` e `get_prompt`** (o che rifiuta il valore): nessun turno, sessione invariata, messaggio «Prompt non eseguito: …». Test in T3 e T4.
3. **Maiuscole:** `/PROMPTS` e `/prompt Spiega` non sono riconosciuti (comando sconosciuto; prompt sconosciuto). Test in T3.
4. **Turno normale dopo un prompt:** la domanda successiva vede nella cronologia il messaggio compilato e la risposta del prompt. Test in T4.
5. **Valori con apostrofi, barre rovesciate e `#`** senza virgolette: accettati così come sono. Test in T3.

---

### Task 0: Ramo di lavoro

- [ ] **Step 1:** `git status` pulito (salvo `../LLM_Lez_6.pdf`), `git switch dev`, `git switch -c feat/prompt-mcp`.
- [ ] **Step 2:** suite completa: atteso `696 passed`.

### Task 1: i due prompt sul server MCP

**Files:**
- Modify: `src/assistente/server_mcp.py` (`crea_server`, prima di `return server`; docstring del modulo e di `crea_server`)
- Test: `tests/test_server_mcp.py`

**Interfaces:**
- Produces: prompt MCP `spiega(argomento: str, livello: str = "base")` e `riassumi_conversazione(stile: str = "breve")`, ciascuno con un solo messaggio `user`; `PromptError` per un livello non ammesso.

- [ ] **Step 1: test che falliscono** (Client FastMCP in memoria, `Client(server)`; testi letti dalla specifica con un helper `blocco_testo(intestazione)` locale al file, come in `test_riassunto.py`, puntato al file della specifica dello Step 5):
  - `test_prompt_elencati_con_descrizioni_e_argomenti`: `list_prompts()` contiene `spiega` e `riassumi_conversazione` con le descrizioni esatte dei Vincoli globali; argomenti `[("argomento", True), ("livello", False)]` e `[("stile", False)]` (nome, `required`).
  - `test_spiega_per_livello`, parametrizzato su `base`, `intermedio`, `avanzato` con le tre guide dell'Appendice A.1: `get_prompt("spiega", {"argomento": "Model Context Protocol", "livello": <l>})` → un solo messaggio, `role == "user"`, testo uguale a `blocco_testo("### A.1").format(argomento=..., livello=<l>, guida_livello=<guida>)`.
  - `test_spiega_senza_livello_usa_base`: come sopra con livello `base`.
  - `test_spiega_livello_non_ammesso`: `livello="esperto"` → eccezione il cui testo contiene `livello non valido: esperto` e `valori ammessi: base, intermedio, avanzato`. Parametrizzare anche `"Base"` (confronto esatto).
  - `test_riassumi_conversazione`: con `{"stile": "elenco puntato"}` e senza argomenti (`breve`) → un solo messaggio `user` uguale a `blocco_testo("### A.2").format(stile=...)`.
  - `test_prompt_non_tra_gli_strumenti`: `list_tools()` non contiene `spiega` né `riassumi_conversazione`.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_server_mcp.py -v`: i nuovi falliscono.
- [ ] **Step 3:** implementare con `@server.prompt(description=...)`; argomenti `str` semplici (niente `Literal`/`Annotated`, §3.1); guide dei livelli in un dizionario `{livello: guida}` nel modulo; template come costanti copiate dall'Appendice A; livello non ammesso → `fastmcp.exceptions.PromptError("livello non valido: <valore> (valori ammessi: base, intermedio, avanzato)")`.
- [ ] **Step 4:** test del file verdi, poi suite completa: **696 + nuovi**.
- [ ] **Step 5:** commit `feat(server-mcp): aggiunge i prompt spiega e riassumi_conversazione`.

### Task 2: `elenca_prompt` e `ottieni_prompt` nel client MCP

**Files:**
- Modify: `src/assistente/mcp_client.py` (docstring del modulo: aggiungere le chiamate verificate `list_prompts`/`get_prompt`)
- Test: `tests/test_mcp_client.py`

**Interfaces:**
- Consumes: i prompt di T1 (solo nei test).
- Produces:
  - `@dataclass(frozen=True) class ArgomentoPrompt: nome: str; descrizione: str; obbligatorio: bool`
  - `@dataclass(frozen=True) class PromptMcp: nome: str; descrizione: str; argomenti: tuple[ArgomentoPrompt, ...]`
  - `elenca_prompt(url: str, timeout: float = 10.0) -> tuple[PromptMcp, ...]`
  - `ottieni_prompt(url: str, nome: str, argomenti: dict[str, str], timeout: float = 10.0) -> list[tuple[str, str]]`
  - Errori: `ErroreMcp(f"discovery dei prompt impossibile su {url}: {testo}")` e `ErroreMcp(f"prompt {nome} non ottenuto da {url}: {testo}")`, `testo` da `_testo_errore`; contenuto senza `.text` → `ErroreMcp(f"prompt {nome} non ottenuto da {url}: messaggio non testuale nel prompt {nome}")` (scelta voluta: stesso prefisso degli altri errori di `ottieni_prompt`, il testo di §6.1 resta contenuto).
  - Verificato dalla review del piano (FastMCP 4.1.6, Streamable HTTP): `PromptError` arriva come `mcp.shared.exceptions.MCPError` con il testo originale; un prompt che restituisce `[Message(Image(...).to_image_content(), role="user")]` (`from fastmcp.prompts import Message`) produce un `ImageContent` senza `.text`.

- [ ] **Step 1: test che falliscono** (server reale dalla fixture `server` già presente nel file; log con `caplog` sul logger `assistente.mcp`):
  - `test_elenca_prompt_copia_la_discovery`: restituisce una tupla di `PromptMcp`; `spiega` ha la descrizione del server e `argomenti == (ArgomentoPrompt("argomento", "", True), ArgomentoPrompt("livello", "", False))`; INFO con i nomi scoperti.
  - `test_ottieni_prompt_restituisce_ruolo_e_testo`: `ottieni_prompt(url, "spiega", {"argomento": "MCP"})` → `[("user", <testo con «MCP» e livello base>)]`; INFO `prompt richiamato` con nome e argomenti e INFO `prompt ottenuto` con i messaggi.
  - `test_ottieni_prompt_rifiutato_dal_server`: `livello="esperto"` → `ErroreMcp` con `livello non valido: esperto` nel testo (conferma la classe d'errore sul trasporto HTTP, §3.1); WARNING registrato.
  - `test_prompt_porta_chiusa`: `elenca_prompt` e `ottieni_prompt` su `porta_chiusa()` → `ErroreMcp`.
  - `test_elenca_prompt_porta_muta_rispetta_il_timeout`: `porta_muta()`, `timeout=0.5` → `ErroreMcp` in meno di 5 s (Review Focus 1).
  - `test_ottieni_prompt_non_testuale`: server FastMCP di prova con un prompt che restituisce un messaggio con un'immagine (`fastmcp.utilities.types.Image`, già importato nel file) → `ErroreMcp` con `messaggio non testuale`. Se la libreria non consente un prompt con immagine, usare un client finto: scelta del costruttore (§18 della specifica).
- [ ] **Step 2:** i nuovi test falliscono (nomi non importabili).
- [ ] **Step 3:** implementare con coroutine `_elenca_prompt` / `_ottieni_prompt` sullo schema di `_leggi`: `asyncio.timeout`, `Client(url, timeout=timeout)`, conversione di ogni eccezione in `ErroreMcp` nella funzione sincrona; `description`/`arguments` `None` → `""`/`()`; `required` `None` → `False`.
- [ ] **Step 4:** test del file verdi, poi suite completa.
- [ ] **Step 5:** commit `feat(mcp): aggiunge discovery e lettura dei prompt MCP`.

### Task 3: modulo `comandi.py`

**Files:**
- Create: `src/assistente/comandi.py`
- Test: `tests/test_comandi.py`

**Interfaces:**
- Consumes: `PromptMcp`, `ArgomentoPrompt`, `ErroreMcp` da `mcp_client`.
- Produces:
  - `class ErroreComando(Exception)`: il messaggio è il testo da mostrare all'utente.
  - `scomponi_richiesta(riga: str) -> tuple[str, dict[str, str]]`: riga che inizia con `/prompt`; solleva `ErroreComando`.
  - `controlla_richiesta(prompts: Sequence[PromptMcp], nome: str, argomenti: Mapping[str, str]) -> list[str]`: problemi, vuoto = via libera.
  - `riga_uso(prompt: PromptMcp) -> str`
  - `testo_elenco(prompts: Sequence[PromptMcp]) -> str`
  - `converti_messaggi(coppie: Sequence[tuple[str, str]]) -> list[BaseMessage]`: solleva `ErroreComando`.
  - `esegui_comando(riga: str, elenca: Callable[[], Sequence[PromptMcp]] | None, ottieni: Callable[[str, dict[str, str]], list[tuple[str, str]]] | None) -> tuple[list[str], list[BaseMessage]]`: righe da stampare e messaggi per il turno (vuoti se non parte nessun turno). Non solleva per errori MCP o d'uso.

- [ ] **Step 1: test che falliscono**, funzioni pure con `PromptMcp` costruiti nel test e `elenca`/`ottieni` finti che registrano le chiamate:
  - **Scomposizione** (`scomponi_richiesta`):
    - `'/prompt spiega argomento="Model Context Protocol" livello=base'` → `("spiega", {"argomento": "Model Context Protocol", "livello": "base"})`;
    - `"/prompt spiega argomento=dell'MCP"` → valore `dell'MCP`; `'/prompt spiega argomento="l\'intelligenza artificiale"'` → `l'intelligenza artificiale`; `r"/prompt spiega argomento=C:\cartella\file"` → barre conservate; `"/prompt spiega argomento=#uno"` → `#uno` (Review Focus 5);
    - `"/prompt spiega a=b=c"` → `{"a": "b=c"}`; `"/prompt spiega livello="` → `{"livello": ""}`; `"/prompt spiega"` → `{}`;
    - `ErroreComando` per: `'/prompt spiega argomento="aperta'` (messaggio che inizia con `Virgolette non chiuse.` e contiene `USO_PROMPT`), `"/prompt"`, `"/prompt spiega argomento"`, `"/prompt spiega =x"`, `"/prompt spiega a=1 a=2"`; ogni messaggio contiene `USO_PROMPT`.
  - **Controllo** (`controlla_richiesta`, prompt `spiega` con `argomento` obbligatorio e `livello` facoltativo):
    - richiesta valida → `[]`;
    - nome `xyz` e nome `Spiega` → `["Prompt sconosciuto: xyz. Usa /prompts per l'elenco."]` (solo quella riga; Review Focus 3);
    - `{}` → contiene `"Argomenti obbligatori mancanti: argomento."`;
    - `{"argomento": "x", "pippo": "1"}` → contiene `"Argomenti sconosciuti: pippo. Argomenti accettati: argomento, livello."`;
    - `{"argomento": "x", "livello": "  "}` → contiene `"Valore vuoto per: livello."`;
    - `{"pippo": "1", "livello": ""}` → le righe nell'ordine mancanti, sconosciuti, vuoti, poi `"Uso: /prompt spiega argomento=… [livello=…]"`;
    - prompt senza argomenti con `{"x": "1"}` → `"Argomenti sconosciuti: x. Argomenti accettati: nessuno."`.
  - **Uso ed elenco:** `riga_uso(spiega) == "Uso: /prompt spiega argomento=… [livello=…]"`; `testo_elenco` riproduce il formato di §7.3 (riga `Prompt disponibili:`, righe `/prompt <nome> — <descrizione>`, argomenti indentati di 4 spazi con `(obbligatorio)`/`(facoltativo)` e `: <descrizione>` se presente; descrizione vuota → niente trattino); `testo_elenco(()) == "Nessun prompt disponibile."`.
  - **Conversione:** `[("user", "a")]` → `[HumanMessage("a")]`; `[("assistant", "a"), ("user", "b")]` → `[AIMessage("a"), HumanMessage("b")]`; `ErroreComando` con `"Prompt non utilizzabile: l'ultimo messaggio non è dell'utente."` per `[("user","a"),("assistant","b")]`, `"Prompt non utilizzabile: nessun messaggio."` per `[]`, `"Prompt non utilizzabile: ruolo non riconosciuto: system."` per `[("system","a")]`.
  - **`esegui_comando`:**
    - `"/prompts"` → `([testo_elenco(prompts)], [])`; `elenca` che solleva `ErroreMcp("x")` → `(["Prompt MCP non disponibili: x"], [])`;
    - `"/prompts x"` → `([USO_PROMPTS], [])`; `"/PROMPTS"`, `"/aiuto"` → `([COMANDO_SCONOSCIUTO], [])`; `elenca` non chiamata;
    - `elenca=None` o `ottieni=None` con `/prompts`, `/prompt spiega argomento=x` e anche `/prompt` scritto male (`'/prompt spiega a="x'`) → `([CLIENT_NON_CONFIGURATO], [])`: il controllo del client viene **prima** della scomposizione e richiede entrambe le funzioni;
    - `/prompt spiega argomento=x` con `elenca` che solleva `ErroreMcp("x")` → `(["Prompt MCP non disponibili: x"], [])`, `ottieni` non chiamata;
    - `/prompt` con scomposizione fallita → `([<messaggio dell'ErroreComando>], [])`, `elenca` e `ottieni` non chiamate, nessun WARNING;
    - `/prompt` con controllo fallito → righe d'errore, `[]`, `ottieni` **non** chiamata, WARNING su `assistente.comandi` con nome, argomenti e problemi (solo in questo caso, §8);
    - `ottieni` che solleva `ErroreMcp("y")` → `(["Prompt non eseguito: y"], [])` (Review Focus 2);
    - `/prompt spiega argomento=MCP` valido con `ottieni` → `[("user", "Spiega MCP")]` → righe `["[prompt spiega] Spiega MCP"]`, messaggi `[HumanMessage("Spiega MCP")]`; con `[("assistant","a"),("user","b")]` → righe `["[prompt spiega, assistente] a", "[prompt spiega] b"]`;
    - conversione fallita → riga `Prompt non utilizzabile: …`, `[]`.
- [ ] **Step 2:** i test falliscono (modulo assente).
- [ ] **Step 3:** implementare. `scomponi_richiesta` usa:
  ```python
  lexer = shlex.shlex(riga, posix=True)
  lexer.whitespace_split = True
  lexer.quotes = '"'
  lexer.escape = ""
  lexer.commenters = ""
  ```
  `ValueError` → `ErroreComando("Virgolette non chiuse. " + USO_PROMPT)`; per le altre cause una frase breve in italiano seguita da `USO_PROMPT`. In `esegui_comando` il nome del comando è `riga.split()[0]`; per `/prompts` e `/prompt`, se `elenca` o `ottieni` è `None` si restituisce subito `CLIENT_NON_CONFIGURATO`; per `/prompt` l'ordine è poi: scomposizione → `elenca` (errore → `"Prompt MCP non disponibili: …"`) → controllo → `ottieni` (errore → `"Prompt non eseguito: …"`) → conversione. Le righe d'errore del controllo si restituiscono una per elemento della lista.
- [ ] **Step 4:** test del file verdi, poi suite completa.
- [ ] **Step 5:** commit `feat(comandi): aggiunge i comandi /prompts e /prompt con il controllo degli argomenti`.

### Task 4: terminale e test d'integrazione

**Files:**
- Modify: `src/assistente/terminale.py` (`esegui_turno`, nuova `esegui_turno_messaggi`, `esegui_chat`, `main`)
- Test: `tests/test_terminale.py`

**Interfaces:**
- Consumes: `esegui_comando` (T3); `elenca_prompt`, `ottieni_prompt` (T2).
- Produces:
  - `esegui_turno_messaggi(grafo, sessione: Sessione, nuovi: Sequence[BaseMessage], max_passaggi: int, *, max_revisioni: int) -> tuple[Sessione, str]`
  - `esegui_turno(...)`: firma invariata, delega a `esegui_turno_messaggi` con `[HumanMessage(domanda)]`.
  - `esegui_chat(grafo, max_passaggi, leggi, scrivi, *, max_revisioni, elenca=None, ottieni=None) -> None`

- [ ] **Step 1: test che falliscono** (helper `esegui` del file esteso con `elenca`/`ottieni` facoltativi; `GrafoSpia` già presente):
  - `test_comandi_non_invocano_il_grafo`, parametrizzato su `/prompts`, `/aiuto`, `/prompt spiega` (argomento mancante), `/prompt spiega argomento=x` con `ottieni` che solleva `ErroreMcp`, e su `elenca=None`: `GrafoSpia.chiamate == 0`, la chat prosegue fino a `esci` e stampa la riga attesa.
  - `test_prompt_valido_passa_al_grafo`: `ottieni` finto → `[("user", "Spiega MCP")]`; il grafo spia riceve come ultimo messaggio un `HumanMessage` con `"Spiega MCP"`; lo stampato è `["[prompt spiega] Spiega MCP", "x"]`.
  - `test_domanda_dopo_un_prompt_vede_il_prompt` (Review Focus 4): grafo reale (`grafo_con("risposta al prompt", "risposta 2")`), righe `["/prompt spiega argomento=MCP", "e poi?", "esci"]`; nella seconda chiamata al modello compaiono il `HumanMessage` compilato e `"risposta al prompt"`.
  - `test_turno_di_prompt_fallito_lascia_la_sessione`: `esegui_turno_messaggi` con un grafo che solleva `GraphRecursionError` → restituisce lo stesso oggetto `Sessione` (`is`).
  - `test_prompt_attraversa_tutto_il_grafo` (§12.5): `costruisci_grafo` con `ModelloSimulato` che prima chiede uno strumento finto (`StructuredTool` che restituisce `"ok"`) e poi risponde, `in_ambito()`, `approva_sempre()`, `riassuntore_inerte()`; `esegui_turno_messaggi` con `[HumanMessage(<testo A.1 compilato>)]` → il classificatore e il revisore sono stati chiamati una volta, lo strumento eseguito, la risposta è quella finale, la sessione contiene il messaggio del prompt.
  - `test_main_prompt_spiega_dal_server_reale`: come `test_main_bind_tools_senza_resource` (server reale, modello finto), righe `["/prompts", '/prompt spiega argomento="Model Context Protocol"', "esci"]`; lo stdout contiene `Prompt disponibili:` e `[prompt spiega] Spiega l'argomento «Model Context Protocol» a livello base.`; il modello finto riceve quel testo come ultimo `HumanMessage`.
- [ ] **Step 2:** i nuovi test falliscono.
- [ ] **Step 3:** implementare. In `esegui_chat`, dopo i controlli di `esci` e della riga vuota: se `domanda.startswith("/")` → `righe, messaggi = esegui_comando(domanda, elenca, ottieni)`, ogni riga con `scrivi`; se `messaggi` → `esegui_turno_messaggi` e `scrivi` della risposta; poi `continue`. In `main`: `elenca=lambda: elenca_prompt(config.mcp_url, config.mcp_timeout)`, `ottieni=lambda nome, argomenti: ottieni_prompt(config.mcp_url, nome, argomenti, config.mcp_timeout)`.
- [ ] **Step 4:** suite completa: **nessun test esistente cambiato**, tutti verdi.
- [ ] **Step 5:** commit `feat(terminale): richiama i prompt MCP dalla CLI e li manda al grafo`.

### Task 5: documentazione

**Files:**
- Modify: `README.md`

- [ ] **Step 1:** README, con solo comandi verificati in T6:
  - sezione «Comandi della CLI»: `/prompts`, `/prompt nome argomento=valore`, virgolette doppie per i valori con spazi, esempi `spiega` e `riassumi_conversazione`, controllo degli argomenti, comportamento con il server MCP spento, log da cercare (`assistente.mcp`, `assistente.comandi`);
  - righe in «Limitazioni note» (§16 della specifica).
- [ ] **Step 2:** commit `docs(comandi): documenta i comandi della CLI per i prompt MCP` (dopo T6, quando i comandi sono verificati; si può unire al commit di T6).

### Task 6: prove reali (a mano)

Prove R1–R7 della specifica §14. Script pilota nella scratchpad che avvia server MCP e servizio HTTP e pilota il terminale via stdin, con `NOTE_DB_PATH` e `PREFERENZE_PATH` temporanei. Esiti, comandi, log rilevanti, risposte e latenze in `prove_reali/PROVE.md`, nuova sezione «Step 5».

- [ ] **Step 1:** R1–R6 in locale. Per R4 `SOGLIA_RIASSUNTO` bassa (per esempio 4) e almeno 3 turni prima del prompt. Se il Router rifiuta `riassumi_conversazione` o la risposta non rispetta il livello: al massimo 2 tentativi, solo sul testo dei prompt nel server e **con l'accordo dell'utente** (Appendice A fissata); poi si documenta il limite.
- [ ] **Step 2:** R7 con Docker (`docker compose build`, `docker compose run --rm assistente`); `.env` ripristinato alla fine.
- [ ] **Step 3:** commit `docs(comandi): registra le prove reali dello Step 5` (con il README di T5).

### Task 7: chiusura

- [ ] **Step 1:** review indipendente dell'intero ramo (`superpowers:requesting-code-review`); i rilievi bloccanti si correggono, i minori si documentano.
- [ ] **Step 2:** resoconto all'utente: che cosa è stato eseguito, con quale esito, che cosa resta da provare.
- [ ] **Step 3:** con **autorizzazione esplicita**: `CLAUDE.md` (modulo `comandi`, comandi `/prompts` e `/prompt`, prompt nel server MCP); `git merge --no-ff feat/prompt-mcp` su `dev`; suite verde; eliminazione del ramo. Push solo su richiesta.
