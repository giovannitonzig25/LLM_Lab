# Strumenti locali, HTTP (FastAPI) e MCP (FastMCP) — Piano di implementazione

> **Per gli esecutori:** metodo scelto dall'utente: **esecuzione nativa** (`superpowers:executing-plans`), con **review indipendente alla fine di ogni ramo** (P4) e **approvazione dell'utente prima di ogni merge** (P5). I passi usano la sintassi a caselle (`- [ ]`).

**Obiettivo:** aggiungere all'agente LangGraph esistente sei funzionalità (11 strumenti con `orologio`) tramite funzioni locali, un servizio FastAPI e un server MCP FastMCP, senza modificare il grafo.

**Architettura:** `costruisci_grafo` accetta già una lista di `BaseTool`. All'avvio `componi_strumenti(config)` unisce: strumenti locali, wrapper HTTP scritti a mano e strumenti MCP **scoperti** da un ponte sincrono (`mcp_client.py`) sopra il client FastMCP. Server MCP e servizio FastAPI sono servizi Compose separati (un'immagine, tre comandi).

**Stack:** Python 3.13, LangGraph, `fastmcp==4.1.6`, `fastapi==0.162.2`, `uvicorn==0.54.0`, `httpx==0.28.1`, SQLite (`sqlite3`), pytest. Versioni verificate con `pip install --dry-run` in `.venv`: nessun conflitto con quelle già fissate.

**Specifica:** `docs/superpowers/specs/2026-11-03-strumenti-http-mcp-design.md` (approvata il 2026-11-09). Le sezioni 5, 6, 10bis, 10ter e 10quater sono vincolanti; leggerle prima di ogni task.

## Vincoli globali

- Solo MCP via **Streamable HTTP** (no stdio); server MCP e servizio FastAPI come servizi Compose separati; LM Studio resta sull'host.
- Grafo, terminale e test esistenti non si riscrivono. Interventi ammessi sul codice esistente: `strumenti.py`, `terminale.py` (solo composizione degli strumenti e avvisi), `config.py`, `Dockerfile`, `compose.yaml`, `.env.example`, `requirements.txt`, README.
- Strumenti MCP **mai riscritti a mano** nel client (nome, descrizione, schema vengono da `list_tools()`); strumenti HTTP con wrapper `@tool` scritti a mano, richieste sincrone con timeout.
- Ogni richiesta di strumento → `ToolMessage` con il `tool_call_id` corretto. Errori di strumento/rete in testo `Errore: ...`.
- Nessuno strumento cancella senza una **conferma dell'utente raccolta dall'applicazione** (terminale), indipendente da ciò che il modello scrive negli argomenti (vedi «Divergenze dalla specifica»). Nessun dato reale o personale nel catalogo (corsi **fittizi**).
- L'avvio ridotto (server MCP assente) deve funzionare **anche in Docker Compose**: nessun `depends_on` con `condition: service_healthy` sull'agente; i controlli di salute restano sui servizi. Se `server-mcp` non riesce nemmeno a partire (per esempio porta 8001 occupata), l'avvio ridotto si ottiene con `docker compose run --rm --no-deps assistente` (verificato, vedi «Divergenze»); questo comando va nel README.
- Nomi e descrizioni degli strumenti in italiano, con un breve esempio d'uso, senza sovrapposizioni; nessuno strumento «di servizio».
- Test automatici senza modello né Internet (un server FastMCP reale su `127.0.0.1`, porta libera, è ammesso); meteo sempre simulato nei test.
- Porte pubblicate solo su `127.0.0.1`; utente non root; nessuna credenziale versionata; SQLite mai versionato.
- Git: Conventional Commits in italiano, staging selettivo, `git status` e diff prima di ogni commit; ogni commit termina con la riga `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Nessun push, nessun merge su `main`.
- Comandi PowerShell da `assistente-laboratorio/`; test: `.\.venv\Scripts\python.exe -m pytest -v`.

## Divergenze dalla specifica (approvate dall'utente il 2026-11-09)

Richieste dall'utente dopo la prima lettura del piano. La specifica è stata **emendata di conseguenza** (§5.3, §5.6, §5.7, §8, §10, §10ter, §10bis): piano e specifica sono allineati. Limite accettato dall'utente: il server MCP non protegge da cancellazioni di altri client; la conferma è chiesta prima di verificare se l'ID esiste.

1. **Conferma di `elimina_nota` (spec §5.6 opzione A, §10ter):** il parametro `conferma` scelto dal modello **non** è una protezione sufficiente. Nuovo meccanismo, il meno invasivo compatibile con grafo e terminale (che non cambiano):
   - il server dichiara `elimina_nota(id: int)` con l'annotazione MCP standard `destructiveHint=True` e **senza** parametro `conferma`;
   - il ponte (`StrumentoMcp`) legge l'annotazione dalla discovery (nessun elenco scritto a mano nel client) e, prima di chiamare il server, invoca una funzione `chiedi_conferma(messaggio) -> bool` ricevuta dall'applicazione;
   - il terminale passa una funzione che mostra «Confermi: elimina_nota {id: 3}? [s/N]» e legge la risposta con `input()`; è un'azione **fuori dal modello**: qualunque argomento scelto dal modello (anche un `conferma=True` inventato) non può sostituirla. Risposta diversa da `s`/`sì`, EOF o assenza della funzione → la chiamata al server **non parte** e il modello riceve `Errore: cancellazione non confermata dall'utente`;
   - nessuna modifica al grafo (la funzione gira dentro il nodo strumenti, sincrona) e nessun `interrupt`. Ctrl+C durante la domanda segue il percorso già esistente.
   - Effetto sulla spec: l'opzione B di §5.6 («conferma nel terminale») era stata scartata perché si riteneva servisse modificare grafo o nodo strumenti; in questa forma non serve. La condizione bloccante di §10ter (modello che passa `conferma=true`) non esiste più; resta il vincolo che nessuna cancellazione avviene senza conferma.
2. **Compose e avvio ridotto (spec §5.3, §5.7):** `depends_on: service_healthy` sull'agente è sostituito da `condition: service_started` più una **attesa limitata all'avvio** (`MCP_ATTESA_AVVIO`, secondi: 0 in locale, 20 in Compose) con ripetizione della discovery solo in fase di avvio; scaduta l'attesa, avviso e strumenti locali. Nessun nuovo tentativo ai turni successivi (invariato). I controlli di salute restano e fanno una **vera discovery MCP**, non solo una connessione TCP.

   **Verifica empirica già eseguita (Docker 29.2.0, Compose v5.0.2, progetto di prova fuori dal repository, ora ripulito):**

   | Caso (dipendenza `dep`, agente `app`) | Esito di `docker compose run --rm app` |
   |---|---|
   | `dep` avviato ma sempre *unhealthy*, `service_started` (con o senza `required: false`) | `app` parte |
   | `dep` avviato che esce subito con codice 1, `service_started` | `app` parte |
   | `dep` unhealthy, `service_healthy` + `required: false` | `app` parte dopo un avviso (dopo l'attesa dei controlli) |
   | `dep` **non riesce a partire** (porta occupata o comando inesistente), anche con `required: false` | **`run` fallisce**, `app` non parte |
   | stesso caso con `run --rm --no-deps app` | `app` parte |

   Conseguenze: `required: false` è supportato ma **non aggiunge nulla** a `service_started` e non copre il guasto di avvio del server: non lo si usa. Un server fermo, in crash o non sano non impedisce l'avvio; un server che non riesce a partire richiede `--no-deps`. Decisione: `service_started` (così `docker compose run --rm assistente` avvia comodamente il server) e `--no-deps` documentato come comando per l'avvio ridotto.

## Focus della review

Casi che la specifica implica ma che nessun test ordinario copre; ognuno ha il suo test nel task indicato.

1. **Conferma saltata:** il modello chiede `elimina_nota` subito, anche con `conferma=True` inventato, senza alcuna conferma dell'utente → la cancellazione deve essere impedita. Test in T5; prova reale in T7.
2. **Server MCP che cade a metà sessione:** `ToolMessage` con `Errore: ...`, la chat prosegue (T2).
3. **Argomenti di tipo sbagliato** dal modello (`"limite": "abc"`, `id` come testo, parametro mancante): messaggio chiaro, mai traceback né crash del turno (T2, T4).
4. **Testo della nota con apostrofi, `'; DROP TABLE note;--`, emoji, newline:** salvato e restituito letteralmente (T4).
5. **Più richieste di strumento nello stesso messaggio** del modello: un `ToolMessage` per ciascuna, `tool_call_id` corretti e ordine rispettato (T2).

## Struttura dei file

| File | Responsabilità | Task |
|---|---|---|
| `src/assistente/note.py` | `ArchivioNote` (SQLite), `Nota`, `ErroreNote` | T1, T4, T5 |
| `src/assistente/server_mcp.py` | `crea_server(archivio, client_http=None) -> FastMCP`, `main()`; avvio `python -m assistente.server_mcp` | T1, T4, T5, T8 |
| `src/assistente/mcp_client.py` | `scopri_strumenti`, `StrumentoMcp`, `ErroreMcp` (ponte sincrono; conferma per strumenti `destructiveHint`) | T2, T5 |
| `src/assistente/verifica_mcp.py` | `verifica(url, timeout) -> int` e `main()`: vera discovery MCP, codice di uscita 0/1; usato dal controllo di salute e dalle verifiche Docker (`python -m assistente.verifica_mcp`) | T6 |
| `src/assistente/meteo.py` | `leggi_meteo`, `ErroreMeteo` | T8 |
| `src/assistente/unita.py`, `calcolatrice.py` | funzioni pure + `@tool` `converti_unita`, `calcola` | T10, T11 |
| `src/assistente/servizi_http/` (`app.py`, `scadenze.py`, `catalogo.py`, `dati/festivita.json`, `dati/catalogo.json`, `__main__.py`) | servizio FastAPI | T12, T14 |
| `src/assistente/strumenti_http.py` | `crea_strumenti_http(base_url, timeout) -> list[BaseTool]` | T13, T14 |
| `strumenti.py`, `config.py`, `terminale.py` | composizione e nuove variabili | T3, T13 |
| `tests/server_reale.py` | helper `avvia_server_mcp(server) -> ContextManager[str]` (URL) | T1 |

Variabili nuove (`config.py`, con predefiniti locali): `MCP_URL` (`http://localhost:8001/mcp`), `MCP_TIMEOUT` (secondi, 10), `MCP_ATTESA_AVVIO` (secondi, 0; ≥ 0), `SERVIZI_BASE_URL` (`http://localhost:8000`), `SERVIZI_TIMEOUT` (10). Lato server: `NOTE_DB_PATH`, `MCP_HOST` (`127.0.0.1`), `MCP_PORT` (8001). Compose: `MCP_DOCKER_URL` (`http://server-mcp:8001/mcp`), `SERVIZI_DOCKER_URL` (`http://servizi-http:8000`).

## Procedura di ramo (da seguire per i rami 1–6)

- [ ] **P1.** `git switch dev; git status` pulito → `git switch -c feat/<nome>`.
- [ ] **P2.** Eseguire i task del ramo (test prima del codice, commit piccoli).
- [ ] **P3.** Suite completa verde; prove reali con LM Studio (più formulazioni per strumento, chiamate verificate nei log) e, dove pertinente, con Docker; esiti in `prove_reali/PROVE.md`, distinguendo **simulato** da **provato con il modello locale**.
- [ ] **P4.** Review con `superpowers:requesting-code-review` sul diff del ramo, includendo l'assenza di regressioni (suite completa, Docker).
- [ ] **P5.** **Fermarsi e chiedere l'approvazione dell'utente** con il resoconto di P3 e P4.
- [ ] **P6.** `git switch dev; git merge --no-ff feat/<nome>`; suite verde su `dev`; `git branch -d feat/<nome>`. Nessun push.

---

## Ramo 0 — Documentazione su `dev`

### T0: piano e `CLAUDE.md`

**Files:** Modify `CLAUDE.md`; il piano e la specifica sono già in `docs/superpowers/`.

- [ ] **Step 1:** Dopo l'approvazione del piano, applicare a `CLAUDE.md` i punti 1–4 e 6 della spec §9 (confini, scelte tecniche, Compose a più servizi, flusso Git `dev` → `feat/<nome>` → `merge --no-ff`, regola MCP/HTTP). Il punto 5 (struttura e comandi) si applica in T15, quando i comandi esistono.
- [ ] **Step 2:** `git status`, diff, commit `docs: aggiorna CLAUDE.md per strumenti HTTP e MCP` (con specifica e piano).

---

## Ramo 1 — `feat/mcp-note` (prima integrazione MCP; va completato e verificato prima del resto)

### T1: server FastMCP e primo strumento `aggiungi_nota`, invocazione diretta

**Files:** Create `src/assistente/note.py`, `src/assistente/server_mcp.py`, `tests/server_reale.py`, `tests/test_note.py`, `tests/test_server_mcp.py`. Modify `requirements.txt`.

**Interfaces:**
- Produces: `ArchivioNote(percorso: str, adesso: Callable[[], datetime] = adesso_utc)` con `aggiungi(testo: str) -> Nota`; `Nota(id: int, testo: str, creata: str)` (dataclass frozen, `creata` = `YYYY-MM-DD HH:MM:SS` UTC); `ErroreNote(Exception)`; `crea_server(archivio: ArchivioNote) -> FastMCP`; `avvia_server_mcp(server) -> ContextManager[str]` che restituisce l'URL `http://127.0.0.1:<porta>/mcp` (porta libera, server in un thread, chiusura pulita).

- [ ] **Step 1:** Aggiungere a `requirements.txt` `fastmcp==4.1.6`, `fastapi==0.162.2`, `uvicorn==0.54.0`, `httpx==0.28.1`; `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`; `pytest` ancora verde (48 test).
- [ ] **Step 2 (verifica API):** l'API di FastMCP 4.x non è nota al piano. Con `help()`/documentazione della versione installata, confermare: creazione del server e registrazione degli strumenti, avvio Streamable HTTP (path `/mcp`), client (`list_tools`, `call_tool`), rappresentazione di errori e risultati, **annotazioni degli strumenti** (`destructiveHint`) dichiarabili dal server e leggibili dal client dopo `list_tools()`. Annotare in un commento di `mcp_client.py` le chiamate effettivamente usate.
- [ ] **Step 3: test di `ArchivioNote` (`tests/test_note.py`)**, con `tmp_path` e istante fisso `2026-11-09 10:00:00`:
  `test_aggiungi_restituisce_id_e_data`: `ArchivioNote(...).aggiungi("consegnare il report venerdì") == Nota(1, "consegnare il report venerdì", "2026-11-09 10:00:00")`; seconda nota → `id == 2`.
- [ ] **Step 4:** Eseguire → FAIL; implementare `ArchivioNote.aggiungi` con SQLite (tabella `note(id INTEGER PRIMARY KEY AUTOINCREMENT, testo TEXT NOT NULL, creata TEXT NOT NULL)`, creata alla prima operazione, parametri `?`); PASS.
- [ ] **Step 5: test del server reale (`tests/test_server_mcp.py`)**, con `avvia_server_mcp(crea_server(ArchivioNote(tmp)))` e un client FastMCP asincrono diretto (`asyncio.run`):
  - `test_discovery_elenca_aggiungi_nota`: `list_tools()` contiene `aggiungi_nota` con descrizione non vuota e un parametro `testo` di tipo stringa nello schema;
  - `test_invocazione_diretta_aggiungi_nota`: `call_tool("aggiungi_nota", {"testo": "ciao"})` → testo contenente `id 1` e la data; la riga esiste nel database.
- [ ] **Step 6:** Implementare `crea_server` con `aggiungi_nota(testo: str) -> str` (descrizione italiana con esempio: «Salva una nota. Esempio: "ricordami di consegnare il report venerdì"»; risultato `Nota creata: id 1, data 2026-11-09 10:00:00`; log della modifica) e `tests/server_reale.py`. Eseguire i test → PASS.
- [ ] **Step 7:** Verifica manuale: avviare `crea_server` in una finestra PowerShell separata (`main()` arriva in T4: per ora uno script in `prove_reali/`) e invocare il primo strumento due volte di seguito. Commit `feat(mcp): server FastMCP con aggiungi_nota e invocazione diretta`.

### T2: ponte sincrono `mcp_client.py`

**Files:** Create `src/assistente/mcp_client.py`, `tests/test_mcp_client.py`.

**Interfaces:**
- Consumes: `crea_server`, `avvia_server_mcp` (T1); `costruisci_grafo(modello, strumenti)` e `tests/finti.py` (finto modello esistente).
- Produces: `scopri_strumenti(url: str, timeout: float = 10.0) -> list[BaseTool]`; `class ErroreMcp(Exception)` (discovery impossibile); `StrumentoMcp(BaseTool)` con `name`, `description`, `args_schema` (JSON Schema ricevuto dal server) e `_run(**argomenti) -> str` sincrono: apre la connessione, chiama, chiude, converte il risultato in testo; errore dello strumento → `Errore: <messaggio del server>`; timeout → `Errore: timeout dopo <n> s`; server non raggiungibile → `Errore: server MCP non raggiungibile su <url>`. Mai eccezioni dalla chiamata. Loggare la discovery (nomi scoperti, logger `assistente.mcp`) e ogni invocazione.

- [ ] **Step 1: test (`tests/test_mcp_client.py`)**, tutti con server reale:
  - `test_discovery_riporta_nome_descrizione_e_schema_del_server`: confronta `StrumentoMcp.name/description` con `list_tools()` diretto, senza stringhe scritte a mano; `args_schema` contiene `testo`;
  - `test_chiamate_ripetute_stesso_processo`: tre `invoke` consecutivi → id 1, 2, 3, nessun errore di ciclo o connessione;
  - `test_due_turni_del_grafo_con_finto_modello`: il finto modello chiede `aggiungi_nota`; `ToolMessage.tool_call_id` uguale all'id della richiesta, risposta finale prodotta; secondo turno con la cronologia del primo;
  - `test_due_richieste_nello_stesso_messaggio` (focus 5): due `tool_calls` con id `a` e `b` → due `ToolMessage` con id `a` e `b`, in ordine;
  - `test_server_non_raggiungibile_alla_discovery`: URL su porta chiusa → `ErroreMcp`;
  - `test_server_caduto_a_meta_sessione` (focus 2): scoperta, chiusura del server, `invoke` → testo che inizia con `Errore:`, nessuna eccezione;
  - `test_timeout`: server finto che non risponde (porta aperta senza protocollo) con `timeout=0.5` → `Errore: timeout`, in meno di 3 s;
  - `test_errore_dello_strumento_non_e_un_successo`: argomento mancante/di tipo sbagliato (`{"testo": 5}` o `{}`) → `Errore: ...`, mai traceback (focus 3);
  - `test_log_discovery_e_invocazione`: `caplog` contiene il nome dello strumento scoperto e l'invocazione.
- [ ] **Step 2:** Eseguire → FAIL; implementare il ponte (un `asyncio.run` per chiamata, funzione asincrona interna con `asyncio.wait_for`); PASS. Se il grafo ha già un ciclo attivo nel thread, deve comunque funzionare: se il test `test_due_turni...` lo rivela, risolvere nel ponte, non nel grafo.
- [ ] **Step 3:** Suite completa verde; commit `feat(mcp): ponte sincrono con discovery e invocazione degli strumenti`.

### T3: composizione all'avvio e avvio ridotto

**Files:** Modify `src/assistente/config.py`, `src/assistente/strumenti.py`, `src/assistente/terminale.py`, `.env.example`. Test: `tests/test_config.py`, `tests/test_strumenti.py`, `tests/test_terminale.py`.

**Interfaces:**
- Consumes: `scopri_strumenti`, `ErroreMcp` (T2); `Config` esistente.
- Produces: `Config` con i nuovi campi `mcp_url: str`, `mcp_timeout: float`, `mcp_attesa_avvio: float` (con predefiniti, i test esistenti restano validi); `componi_strumenti(config: Config, scopri=scopri_strumenti, dormi=time.sleep, adesso=time.monotonic) -> tuple[list[BaseTool], list[str]]` (strumenti, avvisi); `STRUMENTI` resta la lista dei locali. La discovery è ripetuta (pausa di 1 s) **solo finché `adesso()` non supera `mcp_attesa_avvio`**; con attesa 0 un solo tentativo. T5 aggiunge il parametro `chiedi_conferma`.

- [ ] **Step 1: test:**
  - config: `MCP_URL`/`MCP_TIMEOUT`/`MCP_ATTESA_AVVIO` assenti → predefiniti; `MCP_TIMEOUT="abc"` o `<= 0`, `MCP_ATTESA_AVVIO="abc"` o `< 0` → `ErroreConfigurazione`;
  - `test_compone_locali_piu_mcp`: `scopri` finto restituisce uno strumento → lista = `[orologio, <mcp>]`, nessun avviso;
  - `test_avvio_ridotto_con_avviso`: `scopri` solleva `ErroreMcp` → solo `orologio`; un avviso contenente l'URL e il testo «Riavvia l'agente quando il server è attivo», **senza nomi di strumenti**;
  - `test_attesa_all_avvio_server_in_ritardo`: attesa 20, `scopri` fallisce due volte poi riesce (`dormi`/`adesso` finti, nessuna attesa reale) → strumenti presenti, nessun avviso;
  - `test_attesa_scaduta`: attesa 3, `scopri` fallisce sempre → avviso dopo ~3 s simulati; con attesa 0 un solo tentativo;
  - terminale: con avviso, `main()` lo scrive su stderr e continua (l'agente risponde).
- [ ] **Step 2:** Eseguire → FAIL; implementare; il terminale usa `componi_strumenti` al posto di `STRUMENTI`, stampa gli avvisi su stderr e li registra nei log. Aggiungere le variabili a `.env.example`. PASS, suite verde.
- [ ] **Step 3:** Commit `feat(avvio): compone gli strumenti MCP con avvio ridotto se il server è spento`.

### T4: `elenca_note`, validazioni, SQLite completo, punto d'ingresso

**Files:** Modify `note.py`, `server_mcp.py`, `tests/test_note.py`, `tests/test_server_mcp.py`.

**Interfaces:**
- Produces: `ArchivioNote.elenca(filtro: str | None = None, limite: int = 20) -> list[Nota]` (dalla più recente; `limite` 1–100); `aggiungi` valida: testo vuoto/solo spazi o oltre 500 caratteri → `ErroreNote`; `sqlite3.Error` e percorsi inutilizzabili → `ErroreNote("archivio non accessibile")`; strumento MCP `elenca_note(filtro: str | None = None, limite: int = 20) -> str`; gli `ErroreNote` diventano errori MCP (`ToolError`) con il messaggio; `main()` legge `NOTE_DB_PATH`, `MCP_HOST`, `MCP_PORT` (Streamable HTTP, `python -m assistente.server_mcp`).

- [ ] **Step 1: test:**
  - `test_elenca_ordine_filtro_limite`: 3 note → ordine decrescente per id/data; `filtro="report"` restituisce solo quelle pertinenti; `limite=2` ne restituisce 2; `limite=0` e `limite=101` → `ErroreNote`;
  - `test_testo_vuoto_e_troppo_lungo`: `""`, `"   "`, `"x" * 501` → `ErroreNote`, database invariato; `"x" * 500` accettato;
  - `test_testo_speciale_salvato_letteralmente` (focus 4): `"l'ordine; DROP TABLE note;--"`, `"città ☂\nriga due"` → `elenca()` li restituisce identici, la tabella esiste;
  - `test_archivio_non_accessibile`: percorso che è una cartella → `ErroreNote` con «archivio non accessibile»;
  - `test_persistenza_dopo_riavvio`: due istanze di `ArchivioNote` sullo stesso file → la seconda vede le note della prima;
  - server reale: `test_elenca_note_via_mcp`, `test_errori_via_mcp` (testo vuoto → errore, `limite="abc"` → errore, mai traceback, focus 3), `test_log_di_ogni_modifica` (`caplog` del server).
- [ ] **Step 2:** Eseguire → FAIL; implementare; PASS.
- [ ] **Step 3:** Verifica a mano: `$env:PYTHONPATH="src"; $env:NOTE_DB_PATH="data\note.db"; .\.venv\Scripts\python.exe -m assistente.server_mcp` in una finestra separata; aggiungere `data/` e `*.db` a `.gitignore` e `.dockerignore`. Commit `feat(mcp): elenca_note, validazioni e punto d'ingresso del server`.

### T5: `elimina_nota` con conferma dell'utente raccolta dall'applicazione

**Files:** Modify `note.py`, `server_mcp.py`, `mcp_client.py`, `strumenti.py`, `terminale.py`, tests (`test_note.py`, `test_server_mcp.py`, `test_mcp_client.py`, `test_terminale.py`).

**Interfaces:**
- Produces: `ArchivioNote.elimina(id: int) -> None` (ID inesistente → `ErroreNote("nota <id> non trovata")`); strumento server `elimina_nota(id: int) -> str` **senza** parametro `conferma`, registrato con l'annotazione `destructiveHint=True`; descrizione: «Elimina la nota con l'id indicato. L'applicazione chiede conferma all'utente prima di cancellare. Esempio: "elimina la nota 3"»; risultato `Nota 3 eliminata`.
- `scopri_strumenti(url, timeout=10.0, chiedi_conferma: Callable[[str], bool] | None = None)`; `StrumentoMcp.richiede_conferma: bool` (da `destructiveHint` ricevuto dalla discovery; l'assenza dell'annotazione vale `False`) e lo stesso valore in `StrumentoMcp.metadata["destructiveHint"]`. In `_run`, se `richiede_conferma`: chiama `chiedi_conferma(f"Confermi: {nome} {argomenti}?")`; se la funzione è `None`, risponde `False`, solleva (tranne `KeyboardInterrupt`) o restituisce non-`True` → **nessuna chiamata al server**, risultato `Errore: cancellazione non confermata dall'utente`; log della richiesta e dell'esito della conferma. Gli argomenti che il modello passa fuori schema (per esempio `conferma`) non influenzano il percorso.
- `componi_strumenti(..., chiedi_conferma=None)` la inoltra a `scopri`. `terminale.py`: `main()` passa `lambda msg: input(f"{msg} [s/N]: ").strip().lower() in {"s", "si", "sì"}`; `EOFError` → `False`.

- [ ] **Step 1: test del server (reale):**
  - `test_discovery_elimina_nota_destructive_e_senza_conferma`: `elimina_nota` ha `destructiveHint` vero e il suo schema **non** contiene `conferma`;
  - `test_cancellazione_diretta`: `call_tool("elimina_nota", {"id": 1})` → `Nota 1 eliminata`, riga assente, log della modifica (la protezione è del ponte, non del server: documentato nel docstring e nel README);
  - `test_id_inesistente`: `id=99` → `Errore: nota 99 non trovata`, database invariato.
- [ ] **Step 2: test del ponte e del grafo (server reale, finto modello):**
  - `test_modello_chiede_subito_la_cancellazione_con_conferma_true` (focus 1): finto modello emette `elimina_nota` con `{"id": 1, "conferma": True}` senza nessuna conferma dell'utente; `chiedi_conferma` finto → `False` → la nota **esiste ancora**, `ToolMessage` con il `tool_call_id` giusto e testo `Errore: cancellazione non confermata dall'utente`, la funzione di conferma è stata invocata **una volta**;
  - `test_senza_funzione_di_conferma_non_si_cancella`: `chiedi_conferma=None` → stessa conseguenza (nessuna cancellazione);
  - `test_conferma_negata_o_che_solleva_non_cancella`: funzione che solleva `EOFError`/`RuntimeError` → nessuna cancellazione;
  - `test_cancellazione_dopo_conferma_dell_utente`: funzione → `True` → `Nota 1 eliminata`, riga assente; la funzione ha ricevuto un messaggio con nome e id;
  - `test_id_inesistente_dopo_conferma`: `id=99`, conferma `True` → `Errore: nota 99 non trovata`;
  - `test_destructive_hint_acquisito_dalla_discovery_e_conservato_nel_tool`: dopo `scopri_strumenti(url)` su server reale, ogni elemento è un `BaseTool` e `{t.name: t.richiede_conferma for t in strumenti} == {"aggiungi_nota": False, "elenca_note": False, "elimina_nota": True}`; per `elimina_nota` anche `t.metadata["destructiveHint"] is True` (l'annotazione sopravvive nell'adattamento a `BaseTool`; gli altri hanno `False`);
  - `test_il_hint_viene_dal_server_non_dal_nome`: server di prova creato nel test con `cancella_tutto` annotato `destructiveHint=True` e `elimina_altro` **senza** annotazione → conferma richiesta solo per il primo (nessun nome scritto a mano nel client);
  - `test_strumenti_non_distruttivi_non_chiedono_conferma`: per **ogni** strumento scoperto con `richiede_conferma == False` (oggi `aggiungi_nota`, `elenca_note`) l'invocazione con una funzione di conferma che fa fallire il test se chiamata va a buon fine senza chiedere nulla; T8 estende lo stesso test a `meteo`.
- [ ] **Step 3: test del terminale:** `main()` (con `input` e modello finti) mostra il prompt `[s/N]`; risposta `n` o riga vuota → nessuna cancellazione; `s` → cancellazione; `EOFError` durante la conferma → nessuna cancellazione e nessun crash.
- [ ] **Step 4:** Eseguire → FAIL; implementare; PASS; suite verde. Commit `feat(mcp): elimina_nota con conferma dell'utente fuori dal modello`.

### T6: Docker Compose con `server-mcp`, controllo di salute con vera discovery, avvio ridotto

**Files:** Create `src/assistente/verifica_mcp.py`, `tests/test_verifica_mcp.py`. Modify `Dockerfile`, `compose.yaml`, `.env.example`, `README.md`.

**Interfaces:** `verifica(url: str, timeout: float = 5.0) -> int` esegue una **vera discovery** (`scopri_strumenti`) e restituisce 0 se trova almeno uno strumento, altrimenti 1 con un messaggio su stderr; `main()` legge `MCP_URL` e `MCP_TIMEOUT`; `python -m assistente.verifica_mcp`.

- [ ] **Step 1: test:** server reale → `verifica(url) == 0` e il messaggio elenca i nomi scoperti (`aggiungi_nota`, …); porta chiusa → `1`; porta aperta che non parla MCP (socket in ascolto) → `1` (una semplice connessione TCP **non** basta).
- [ ] **Step 2:** Implementare; PASS. `Dockerfile`: prima di `USER app` creare `/data` con proprietario `app` (`RUN mkdir /data && chown app /data`), perché il volume con nome erediti i permessi.
- [ ] **Step 3:** `compose.yaml`:
  - `server-mcp` (stessa immagine, `command: ["python","-m","assistente.server_mcp"]`, `MCP_HOST=0.0.0.0`, `MCP_PORT=8001`, `NOTE_DB_PATH=/data/note.db`, volume `dati-note:/data`, `ports: ["127.0.0.1:8001:8001"]`) con `healthcheck: test: ["CMD","python","-m","assistente.verifica_mcp"]`, `MCP_URL=http://localhost:8001/mcp` nell'ambiente del controllo, `interval: 10s`, `timeout: 8s`, `start_period: 10s`;
  - `assistente`: `depends_on: server-mcp: condition: service_started` (**mai** `service_healthy`; `required: false` non serve, vedi «Divergenze»), `MCP_URL: ${MCP_DOCKER_URL:-http://server-mcp:8001/mcp}`, `MCP_ATTESA_AVVIO: ${MCP_ATTESA_AVVIO:-20}`; volume `dati-note` dichiarato.
- [ ] **Step 4: verifica con Docker (server attivo, vera discovery):** `docker compose config`; `docker compose build`; `docker compose up -d server-mcp` → stato `healthy`; `docker compose run --rm --no-deps assistente python -m assistente.verifica_mcp` → codice 0 con i nomi degli strumenti scoperti; `docker compose run --rm assistente` → i log dell'agente mostrano la discovery; `docker compose down` poi `up -d`: le note restano; solo `down -v` le cancella.
- [ ] **Step 5: verifica con Docker (server assente, avvio ridotto):** `docker compose down`; `docker compose run --rm --no-deps assistente` (server **non** avviato) → l'agente parte dopo l'attesa, mostra l'avviso, e «che ora è?» usa `orologio` (riga di log dello strumento); ripetere con `up -d server-mcp`, poi `docker compose stop server-mcp` e `docker compose run --rm assistente` (il server viene riavviato come dipendenza: caso normale) e con `--no-deps` (server fermo, avvio ridotto). Ripetere con il server **in crash** (processo terminato dentro il container) e con la **porta 8001 occupata** sull'host: `docker compose run --rm assistente` può fallire per l'avvio della dipendenza (comportamento Compose verificato), mentre `docker compose run --rm --no-deps assistente` deve avviare l'agente in modalità ridotta con avviso e `orologio` funzionante. Riportare gli esiti reali in PROVE.md.
- [ ] **Step 6:** README: uso locale (finestra PowerShell separata per il server) e con Compose, `MCP_URL`, `MCP_DOCKER_URL`, `MCP_ATTESA_AVVIO`, comportamento ridotto e il comando `docker compose run --rm --no-deps assistente` per avviare l'agente quando il server MCP non riesce a partire, il limite documentato sulla conferma di `elimina_nota` (la protezione riguarda l'uso tramite il nostro agente, non altri client MCP), `down -v`, `docker compose build` dopo ogni modifica. Solo comandi verificati. Commit `feat(docker): servizio server-mcp con salute a vera discovery e avvio ridotto`.

### T7: prove reali e chiusura del ramo 1

- [ ] **Step 1 (prove con LM Studio, locale e Docker):** «Ricordami di consegnare il report venerdì» → **una sola** chiamata a `aggiungi_nota`; «elenca le mie note»; «elimina la nota 99» → il terminale chiede conferma, poi errore chiaro; «cancella la nota 3» → il **terminale** mostra `[s/N]`; risposta `n` → nota intatta e il modello lo comunica; risposta `s` → cancellazione; riavvio del server → le note restano; orologio ancora funzionante; cronologia e limite ai passaggi ancora validi. Verificare le chiamate nei log.
- [ ] **Step 2 (avvio ridotto reale, locale e Docker):** server MCP non avviato → l'assistente parte, mostra l'avviso, «che ora è a Tokyo?» usa `orologio`. In Docker: i passi 4 e 5 di T6 con LM Studio attivo (`docker compose run --rm --no-deps assistente`), annotando l'esito in PROVE.md.
- [ ] **Step 3 (la conferma non dipende dal modello):** se in una prova il modello scrive `conferma=true` o chiama `elimina_nota` senza che l'utente abbia chiesto una cancellazione, il terminale deve comunque chiedere `[s/N]`; riportare l'esito reale.
- [ ] **Step 4:** Annotare in `prove_reali/PROVE.md` (simulato vs provato); commit `docs: registra le prove del ramo mcp-note`; Procedura P3–P6.

---

## Ramo 2 — `feat/mcp-meteo`

### T8: strumento `meteo` nel server MCP

**Files:** Create `src/assistente/meteo.py`, `tests/test_meteo.py`. Modify `server_mcp.py`, `tests/test_server_mcp.py`.

**Interfaces:** `leggi_meteo(citta: str, client: httpx.Client) -> str`; `ErroreMeteo(Exception)`; `crea_server(archivio, client_http: httpx.Client | None = None)`; strumento `meteo(citta: str) -> str`. Open-Meteo: geocodifica `https://geocoding-api.open-meteo.com/v1/search?name=<citta>&count=5&language=it`, poi `https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&current=temperature_2m,weather_code&timezone=auto`; timeout esplicito. Codici WMO tradotti in italiano (sereno, parzialmente nuvoloso, nebbia, pioggerella, pioggia, neve, rovesci, temporale); codice sconosciuto → «condizioni non classificate (codice N)».

- [ ] **Step 1: test con `httpx.MockTransport`** (nessuna rete):
  - `test_risultato_con_unita_e_ora`: es. `Roma (Lazio, Italia): 18.4 °C, parzialmente nuvoloso, rilevato il 2026-11-09 10:00`;
  - `test_citta_ambigua_dichiarata`: due candidati → il testo dichiara la città scelta (nome, regione, paese) e che esistono altri candidati;
  - `test_citta_con_accenti_e_spazi`: `Forlì`, `San Donà di Piave` codificate correttamente;
  - errori distinti, con messaggi diversi: `test_citta_non_trovata`, `test_timeout`, `test_servizio_non_disponibile` (HTTP 503), `test_risposta_non_valida` (JSON inatteso), `test_rete_assente` (`httpx.ConnectError`, mai «città non trovata»);
  - server reale: `meteo` compare nella discovery con `richiede_conferma == False` e senza invocare la funzione di conferma (estende il test di T5); chiamata con trasporto finto; errore → `Errore: ...` attraverso il ponte.
- [ ] **Step 2:** Eseguire → FAIL; implementare; PASS. Commit `feat(mcp): strumento meteo con Open-Meteo`.

### T9: prove reali e chiusura del ramo 2

- [ ] «Che tempo fa a Bologna?», «Piove a Forlì?» (strumento corretto nei log, nessuno scambio con `orologio`); rete assente → errore di trasporto; dal container: raggiungibilità di Open-Meteo (`docker compose run --rm server-mcp ...`). PROVE.md; Procedura P3–P6.

---

## Rami 3 e 4 — strumenti locali

### T10: `converti_unita` (ramo `feat/conversione-unita`)

**Files:** Create `src/assistente/unita.py`, `tests/test_unita.py`. Modify `strumenti.py` (aggiunta a `STRUMENTI`).

**Interfaces:** `converti(valore: float, da: str, a: str) -> str`; `@tool converti_unita(valore: float, da: str, a: str) -> str`. Elenco chiuso: lunghezza `mm cm m km in ft mi`; massa `g kg lb oz`; volume `ml l gal` (gal USA = 3.785411784 l); temperatura `C F K`. Risultato con unità, es. `10 km = 6.2137 mi`. Unità sconosciuta o incompatibile → `Errore: ...` che elenca le unità ammesse.

- [ ] **Step 1: test:** `10 km → mi`, `100 C → F == 212`, `0 K → C == -273.15`, `1 gal → l`; `km → kg` incompatibile; `parsec` sconosciuta; stesso risultato con maiuscole diverse (`KM`); valore stringa non numerico → errore chiaro.
- [ ] **Step 2:** Implementare; PASS; Procedura P1–P6 con prove reali («quanti chilometri sono 10 miglia?», «100 gradi Fahrenheit in Celsius»). Commit `feat(strumenti): converti_unita`.

### T11: `calcola` (ramo `feat/calcolatrice`)

**Files:** Create `src/assistente/calcolatrice.py`, `tests/test_calcolatrice.py`. Modify `strumenti.py`.

**Interfaces:** `valuta(espressione: str) -> str`; `@tool calcola(espressione: str) -> str`. Solo `ast`, mai `eval`/`exec`: numeri, `+ - * / **`, `-`/`+` unari, parentesi. Limiti: espressione ≤ 200 caratteri, `|esponente| ≤ 100`, `|risultato| ≤ 1e15`.

- [ ] **Step 1: test:** `2+3*4 == 14`, `(2+3)*4`, `2**10`, `-3**2`, `10/4 == 2.5`; rifiuti con `Errore:`: `1/0`, `2+`, `__import__('os')`, `abs(1)`, `a+1`, `9**9**9`, `2**1000`, stringa di 201 caratteri, `"1; 2"`; nessun effetto collaterale.
- [ ] **Step 2:** Implementare; PASS; Procedura P1–P6 con prove reali («quanto fa 17 per 23 più 5?»). Commit `feat(strumenti): calcola con ast`.

---

## Rami 5 e 6 — servizio FastAPI

### T12: servizio date e scadenze (ramo `feat/http-scadenze`)

**Files:** Create `src/assistente/servizi_http/{__init__,app,scadenze,__main__}.py`, `servizi_http/dati/festivita.json`, `tests/test_scadenze.py`, `tests/test_servizi_http.py`.

**Interfaces:** `scadenze.giorni_lavorativi(da: date, a: date, festivita: set[date]) -> int` (estremi inclusi); `scadenze.calcola_scadenza(da: date, giorni: int, festivita: set[date]) -> date` (il giorno di partenza non conta; N-esimo giorno lavorativo successivo); `crea_app() -> FastAPI` con `GET /giorni-lavorativi?da=YYYY-MM-DD&a=YYYY-MM-DD` → `{"da","a","giorni_lavorativi","nota"}` e `GET /scadenza?da=YYYY-MM-DD&giorni=N` → `{"da","giorni","data_scadenza","nota"}`; `nota` ricorda che il risultato non è normativo. Weekend = sabato e domenica. `festivita.json`: festività nazionali italiane 2026–2027 (1/1, 6/1, Pasqua e Lunedì dell'Angelo — 5 e 6/4/2026, 28 e 29/3/2027 —, 25/4, 1/5, 2/6, 15/8, 1/11, 8/12, 25/12, 26/12). Date fuori 2026–2027, non valide o intervalli invertiti → 422 con messaggio in italiano; `giorni` fuori 1–365 → 422. `GET /salute` → `{"stato":"ok"}` per il controllo di salute. Punto d'ingresso `python -m assistente.servizi_http` (uvicorn, `SERVIZI_HOST` 127.0.0.1, `SERVIZI_PORT` 8000).

- [ ] **Step 1: test della logica (puri):** `giorni_lavorativi(2026-11-02 lun, 2026-11-06 ven) == 5`; con `2026-11-01` (festivo, domenica) e `2026-11-02`: caso weekend+festività; `calcola_scadenza(2026-12-24, 1) == 2026-12-28` (25 e 26 festivi, weekend); stesso giorno; `da == a`.
- [ ] **Step 2: test API con `TestClient`:** risposta corretta; `da` dopo `a` → 422; `2026-02-30` → 422; `2025-01-01` → 422; `giorni=-1`, `0`, `100000`, `abc` → 422; 29 febbraio 2028 fuori anni coperti → 422.
- [ ] **Step 3:** Eseguire → FAIL; implementare; PASS. Commit `feat(http): servizio FastAPI per giorni lavorativi e scadenze`.

### T13: wrapper HTTP e servizio Compose

**Files:** Create `src/assistente/strumenti_http.py`, `tests/test_strumenti_http.py`. Modify `config.py`, `strumenti.py`, `compose.yaml`, `.env.example`, `README.md`.

**Interfaces:** `crea_strumenti_http(base_url: str, timeout: float) -> list[BaseTool]` con `@tool giorni_lavorativi(data_inizio: str, data_fine: str)` («non serve per l'ora attuale») e `@tool calcola_scadenza(data_inizio: str, giorni: int)`; `Config.servizi_base_url`, `Config.servizi_timeout`; `componi_strumenti` aggiunge gli strumenti HTTP **sempre** (nessuna discovery).

- [ ] **Step 1: test** (`httpx.MockTransport`): richiesta corretta (URL, parametri); successo → testo con risultato e nota; 422 → `Errore: ...` comprensibile con il dettaglio; 404/500 → testo; servizio spento → `Errore: servizio non raggiungibile ...`; timeout → `Errore: ...`; `componi_strumenti` contiene i nuovi nomi.
- [ ] **Step 2:** Implementare; PASS. Compose: servizio `servizi-http` (`python -m assistente.servizi_http`, `SERVIZI_HOST=0.0.0.0`, porta `127.0.0.1:8000:8000`, healthcheck con una richiesta HTTP reale a `/salute`, non una semplice connessione TCP); `assistente` dipende anche da questo con `condition: service_started` (mai `service_healthy`: gli strumenti HTTP sono sempre registrati e un servizio spento dà `Errore:` alla chiamata), con `SERVIZI_BASE_URL: ${SERVIZI_DOCKER_URL:-http://servizi-http:8000}`. Verifica `docker compose build/up/run`.
- [ ] **Step 3:** Prove reali («quanti giorni lavorativi tra il 2 e il 20 novembre 2026?», «scadenza a 10 giorni lavorativi dal 9 novembre», «che ora è?» → `orologio`, non `giorni_lavorativi`); servizio spento → errore alla chiamata. PROVE.md; commit `feat(http): wrapper degli strumenti e servizio Compose`; Procedura P3–P6.

### T14: catalogo (ramo `feat/http-catalogo`)

**Files:** Create `servizi_http/catalogo.py`, `servizi_http/dati/catalogo.json`, `tests/test_catalogo.py`. Modify `servizi_http/app.py`, `strumenti_http.py`, `tests/test_servizi_http.py`, `tests/test_strumenti_http.py`.

**Interfaces:** `catalogo.json`: ~10 corsi **fittizi** (`codice` univoco tipo `ITS-001`, `titolo`, `settore`, `sede`, `durata_ore`, `descrizione`; nessun dato reale, dichiarato fittizio nel README). `GET /catalogo?q=<testo>&max_risultati=5` (`q` obbligatorio e non vuoto; `max_risultati` 1–10, predefinito 5; ricerca senza maiuscole su titolo, settore, sede; risposta: lista di `{codice,titolo,settore,sede}` e `totale`); `GET /catalogo/{codice}` (tutti i campi; 404 se inesistente). Strumenti `@tool cerca_catalogo(query: str, max_risultati: int = 5)` e `@tool dettaglio_catalogo(codice: str)`.

- [ ] **Step 1: test:** ricerca per titolo/settore/sede, senza maiuscole; ricerca senza risultati → il wrapper dichiara `Nessun corso trovato` (nessun elemento inventato); `max_risultati=0` e `11` → 422; codice inesistente → `Errore: corso <codice> non trovato`; `q=""` → 422; i risultati della ricerca **non** contengono durata e descrizione (compaiono solo nel dettaglio); codici univoci e campi obbligatori presenti in `catalogo.json`.
- [ ] **Step 2:** Eseguire → FAIL; implementare; PASS. Descrizioni dei due strumenti distinte («cerca» per parola chiave, «dettaglio» per codice noto).
- [ ] **Step 3:** Prove reali: «che corsi ci sono a Udine?» → `cerca_catalogo`; «dimmi la durata del corso ITS-003» → `dettaglio_catalogo`; domanda in due passaggi (cerca, poi dettaglio) verificata nei log; ricerca senza risultati → il modello lo dice e non inventa. PROVE.md; commit `feat(http): catalogo corsi fittizi con ricerca e dettaglio`; Procedura P3–P6.

---

## Verifica finale

### T15: regressione, prove reali complessive, documentazione (su `dev`)

- [ ] **Step 1:** Suite completa verde; `docker compose build` e avvio dei tre servizi da zero; entrambi i controlli di salute `healthy`; **vera discovery MCP in Docker**: `docker compose run --rm --no-deps assistente python -m assistente.verifica_mcp` esce con 0 e stampa i nomi degli strumenti scoperti (non basta la porta aperta); poi i log di `docker compose run --rm assistente` mostrano discovery, invocazione e `ToolMessage`.
- [ ] **Step 1bis (avvio ridotto in Docker):** con `server-mcp` fermo, `docker compose run --rm --no-deps assistente` parte, mostra l'avviso e risponde con `orologio`; con `servizi-http` fermo, gli strumenti HTTP restituiscono `Errore: servizio non raggiungibile ...`. Esiti in PROVE.md.
- [ ] **Step 2:** Criteri di spec §8, uno per riga in `prove_reali/PROVE.md`: nuove funzionalità disponibili; `orologio` funziona; selezione corretta con più formulazioni per ciascuno degli 11 strumenti; discovery e invocazioni MCP nei log; `tool_call_id` corretto; errori gestiti (servizio spento, timeout, input non valido, ID inesistente); cronologia, limite passaggi e Ctrl+C; istruzioni Compose. Distinguere **simulato** da **provato**.
- [ ] **Step 3:** Se il modello sbaglia lo strumento in due o più domande-tipo, **fermarsi** e riformulare le descrizioni con l'utente prima di aggiungere altro.
- [ ] **Step 4:** Aggiornare README completo e applicare a `CLAUDE.md` il punto 5 della spec §9 (moduli e comandi verificati). Commit `docs: verifica finale e README aggiornato`.
