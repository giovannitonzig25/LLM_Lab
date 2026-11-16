# Lezione 6, Step 4 — Resource MCP: preferenze dell'utente: piano di implementazione

> **Per gli esecutori:** SOTTO-SKILL RICHIESTA: `superpowers:executing-plans` (nativa) oppure `superpowers:subagent-driven-development`, secondo la scelta dell'utente. I passi usano la sintassi a caselle (`- [ ]`). Leggere la specifica per intero prima di iniziare.

**Obiettivo:** il server MCP espone la resource `utente://preferenze`, letta dal file `data/preferenze.json`. L'host la legge una volta all'avvio e mette le preferenze in cima al prompt di sistema dell'agente. Costruisce anche l'orologio con il fuso preferito. Se la resource manca, usa i valori predefiniti con un WARNING.

**Architettura:**
- Modulo nuovo `preferenze.py`: dati, valori predefiniti, validazione campo per campo, testo del prompt, `carica_preferenze` (che non solleva mai eccezioni).
- `server_mcp.py` aggiunge la resource. `mcp_client.py` aggiunge `leggi_resource`, che non diventa mai un `BaseTool`.
- `componi_strumenti` esegue nell'ordine discovery → preferenze → orologio e restituisce anche le preferenze.
- `nodo_modello` invia sempre un solo `SystemMessage` temporaneo.
- Il grafo non cambia forma.

**Stack:** Python 3.13, `fastmcp==4.1.6`, `langgraph==1.2.19`, `langchain-openai==1.7.3`, pytest. Nessuna dipendenza nuova.

**Specifica:** `docs/superpowers/specs/2026-11-16-preferenze-design.md`, approvata il 2026-11-16 (commit `c137441`). È vincolante: i riferimenti §n rimandano lì.

**Stato del piano:** approvato dall'utente il 2026-11-16; esecuzione nativa (`superpowers:executing-plans`).

## Vincoli globali

- **Solo lo Step 4.** Esclusi: Prompt MCP (Step 5), agente come servizio HTTP, back-end, front-end, Compose per componente, traduzione dei testi fissi, modifiche a `NOTE_DB_PATH`.
- **Router, Revisore e Riassunto non cambiano** (`router.py`, `revisore.py`, `riassunto.py` intatti). La cornice B.1 dello Step 3 resta identica.
- **Valori predefiniti in un solo punto:** `preferenze.PREFERENZE_PREDEFINITE = Preferenze(lingua="italiano", fuso_orario="Europe/Rome", stile="sintetico")`. Il server non li conosce.
- **URI:** `utente://preferenze`, `mime_type="application/json"`.
- **Validazione** (§7.2):
  - `lingua`: stringa; dopo `strip` non vuota e lunga al massimo 40 caratteri; nessun carattere di controllo (`unicodedata.category(c).startswith("C")`, che include `\n`, `\r`, `\t`);
  - `fuso_orario`: stringa accettata da `ZoneInfo`, con le eccezioni `ZoneInfoNotFoundError`, `ValueError` e `TypeError` intercettate; si usa il valore dopo `strip`;
  - `stile`: dopo `strip().lower()` vale `sintetico` o `dettagliato`.
- **Testo del prompt:** Appendice A della specifica, **testo esatto**. Nei test si legge dal file della specifica, come fa `blocco_testo` in `test_riassunto.py`.
- **Log:**
  - host: logger `assistente.preferenze`;
  - server: logger `assistente.server_mcp`;
  - contenuti obbligatori come da §5.3 e §8; il formato esatto è libero;
  - riga INFO finale `preferenze della sessione: lingua=<v> (<origine>), fuso_orario=<v> (<origine>), stile=<v> (<origine>)`, con origine `resource` o `predefinito`.
- **File:** il server lo legge con `encoding="utf-8-sig"` a ogni richiesta della resource. Se non riesce a leggerlo solleva `fastmcp.exceptions.ResourceError` e non restituisce valori predefiniti.
- **Test** senza rete né modello. Il server FastMCP reale su porta libera (`tests/server_reale.py`) è ammesso. I test non leggono mai `data/preferenze.json` del progetto: usano `tmp_path`.
- **Limite di passaggi invariato** (§11): nessuna asserzione di `test_limite.py` cambia.
- **Git** (CLAUDE.md):
  - ramo `feat/preferenze` da `dev`; Conventional Commits in italiano, ambito `preferenze`;
  - prima di ogni commit eseguire la suite completa, `git status`, controllare il diff e fare uno staging selettivo: mai `.env`, `../LLM_Lez_6.pdf`, cache, `data/`;
  - ogni messaggio termina con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
  - review indipendente e **approvazione esplicita dell'utente** prima di `git merge --no-ff`; nessun push; nessun merge su `main`.
- **Comandi** da `assistente-laboratorio/` in PowerShell. Test: `.\.venv\Scripts\python.exe -m pytest -v`. Base di partenza: **636 test verdi**.
- **Sviluppo pragmatico:** test proporzionati al rischio; al massimo 2 tentativi di correzione del comportamento del modello locale, poi si documenta il limite.

## Test esistenti che cambiano (misurati il 2026-11-16)

Misura fatta con un plugin pytest usa e getta, fuori dalla repository, che anteponeva un `SystemMessage` alla richiesta dell'agente. Risultato: **8 fallimenti su 636**. Uno di questi è un artefatto della sonda, che con il riassunto produceva due `SystemMessage`.

| Test | Cambiamento (T5) |
|---|---|
| `test_revisore.py::test_nuova_domanda_dopo_turno_corretto` | le asserzioni su `modello.chiamate[-1]` si applicano a `ricevuti[1:]`; nuova asserzione: `ricevuti[0]` è un `SystemMessage` |
| `test_revisore.py::test_due_turni_corretti_di_fila` | idem |
| `test_revisore.py::test_turno_precedente_al_limite_resta_intero` | idem |
| `test_terminale.py::test_la_seconda_domanda_vede_la_prima` | idem su `modello.chiamate[1]` |
| `test_terminale.py::test_cronologia_non_persiste_tra_sessioni` | idem |
| `test_riassunto.py::test_agente_senza_riassunto_nessun_system_message` | rinominato `test_agente_senza_riassunto_riceve_solo_le_preferenze`: un solo `SystemMessage`, con contenuto uguale a `testo_prompt(PREFERENZE_PREDEFINITE)`; il resto uguale a `contesto_agente(...)` |
| `test_riassunto.py::test_agente_con_riassunto_riceve_la_cornice` | il contenuto di `richiesta[0]` diventa `testo_prompt(PREFERENZE_PREDEFINITE) + "\n\n" + <B.1 con il riassunto>` |
| `test_riassunto.py::test_chat_usa_la_sessione_accorciata` | **dovrebbe restare verde**, perché l'implementazione produce un solo `SystemMessage`. Se fallisce, fermarsi e capire perché |

La firma di `componi_strumenti` cambia (T4). Per questo:
- le 8 chiamate in `test_strumenti.py` passano da `strumenti, avvisi = …` a `strumenti, _, avvisi = …`;
- il finto `componi_strumenti` di `test_terminale.py::test_main_scrive_gli_avvisi_su_stderr_e_continua` restituisce la tripla.

Sono modifiche meccaniche. Nessun altro test può cambiare significato: se un test diverso fallisce, fermarsi e riferire all'utente.

## Review Focus

1. **File salvato con BOM** da Blocco note o da PowerShell 5.1. Senza `utf-8-sig`, `json.loads` fallirebbe e scatterebbe il fallback in piena dimostrazione. Test in T2.
2. **Server che accetta la connessione ma non risponde.** La lettura deve finire entro `MCP_TIMEOUT` con `ErroreMcp`, senza bloccare l'avvio. Test in T3 con `porta_muta()`.
3. **Valori JSON di tipo sbagliato** (`null`, numeri, liste nei campi): predefinito per quel campo, senza eccezioni. Test in T1.
4. **`lingua` con caratteri non ASCII** (`français`, `español`): va accettata. Il divieto riguarda solo i caratteri di controllo. Test in T1.
5. **Clone appena fatto senza `data/`:** i comandi del README devono creare la cartella prima di `Copy-Item`. Verifica in T6.

---

### Task 0: Ramo di lavoro

- [ ] **Step 1:** `git status` pulito (salvo `../LLM_Lez_6.pdf`), `git switch dev`, `git switch -c feat/preferenze`.
- [ ] **Step 2:** suite completa: atteso `636 passed`.

### Task 1: `preferenze.py` (dati, validazione, prompt, caricamento)

**Files:**
- Create: `src/assistente/preferenze.py`
- Modify: `src/assistente/strumenti.py:18` (`FUSO_PREDEFINITO = PREFERENZE_PREDEFINITE.fuso_orario`)
- Test: `tests/test_preferenze.py`

**Interfaces:**
- Consumes: `assistente.mcp_client.ErroreMcp`, `assistente.config.Config` (`mcp_url`, `mcp_timeout`).
- Produces:
  - `@dataclass(frozen=True) class Preferenze: lingua: str; fuso_orario: str; stile: str`
  - `PREFERENZE_PREDEFINITE: Preferenze`, `URI_PREFERENZE = "utente://preferenze"`, `MAX_LINGUA = 40`
  - `interpreta_preferenze(testo: str) -> Preferenze`: JSON, validazione campo per campo, WARNING, riga INFO finale; non solleva eccezioni
  - `carica_preferenze(config: Config, leggi: Callable[[str, str, float], str]) -> Preferenze`: chiama `leggi(config.mcp_url, URI_PREFERENZE, config.mcp_timeout)`; con `ErroreMcp` restituisce tutti i predefiniti con WARNING e riga INFO; altrimenti `interpreta_preferenze`; INFO di lettura riuscita con `config.mcp_url`
  - `testo_prompt(preferenze: Preferenze) -> str`: Appendice A

- [ ] **Step 1: test che falliscono** in `tests/test_preferenze.py` (`import assistente.preferenze as modulo_preferenze`; WARNING e INFO verificati con `caplog` sul logger `assistente.preferenze`):
  - `test_file_valido_usa_i_tre_valori`: `{"lingua":"inglese","fuso_orario":"America/New_York","stile":"dettagliato"}` → `Preferenze("inglese","America/New_York","dettagliato")`; INFO finale con tre `(resource)`; nessun WARNING.
  - `test_campo_non_valido_usa_il_predefinito_solo_per_quel_campo`, parametrizzato su:
    - `lingua`: `""`, `"   "`, `"x"*41`, `"ita\nliano"`, `5`, `None`;
    - `fuso_orario`: `"Marte/Olympus"`, `""`, `"../x"`, `3`;
    - `stile`: `"dettagliatissimo"`, `None`, `["sintetico"]`;
    - in tutti i casi la chiave assente.

    Esito atteso: quel campo prende il predefinito, gli altri due il valore del file; un WARNING contiene il nome del campo; l'INFO finale riporta `(predefinito)` per quel campo.
  - `test_lingua_non_ascii_accettata`: `"français"` resta tale.
  - `test_lingua_lunga_troncata_nel_log`: `"x"*200` → nessun record contiene più di 40 `x` consecutive.
  - `test_stile_normalizzato`: `"Dettagliato"` → `dettagliato`; `" SINTETICO "` → `sintetico`.
  - `test_valori_con_spazi_ripuliti`: `" inglese "` → `inglese`; `" Asia/Tokyo "` → `Asia/Tokyo`.
  - `test_chiavi_sconosciute_ignorate_con_warning`: `{"fuso": "Asia/Tokyo"}` → WARNING che nomina `fuso`; `fuso_orario` predefinito.
  - `test_testo_non_json_usa_tutti_i_predefiniti` e `test_json_non_oggetto_usa_tutti_i_predefiniti` (`[1,2]`): risultato `PREFERENZE_PREDEFINITE`; WARNING con la causa; INFO con tre `(predefinito)`.
  - `test_carica_con_errore_mcp_usa_i_predefiniti`: `leggi` finto che solleva `ErroreMcp("discovery impossibile")` → `PREFERENZE_PREDEFINITE`; il WARNING contiene il testo dell'errore; nessuna eccezione.
  - `test_carica_passa_url_uri_e_timeout`: `leggi` finto che registra gli argomenti → `(config.mcp_url, "utente://preferenze", config.mcp_timeout)`.
  - `test_carica_riuscita_scrive_info_di_lettura`: un record INFO contiene `utente://preferenze`.
  - `test_testo_prompt_sintetico` e `test_testo_prompt_dettagliato`: uguali all'Appendice A della specifica, letta dal file, con i segnaposti sostituiti.
  - `test_fuso_predefinito_dell_orologio_viene_dalle_preferenze`: `strumenti.FUSO_PREDEFINITO == PREFERENZE_PREDEFINITE.fuso_orario == "Europe/Rome"`.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_preferenze.py -v`: falliscono (modulo assente).
- [ ] **Step 3:** implementare `preferenze.py` con le firme qui sopra. I messaggi di testo dello stile stanno in un dizionario `{stile: testo}` copiato dall'Appendice A. `preferenze.py` non importa `strumenti.py`, per evitare un ciclo; è `strumenti.py` che importa `preferenze.py`.
- [ ] **Step 4:** test del file verdi, poi suite completa: **636 + nuovi**, nessun altro fallimento.
- [ ] **Step 5:** commit `feat(preferenze): aggiunge validazione e testo del prompt delle preferenze`.

### Task 2: resource `utente://preferenze` sul server MCP

**Files:**
- Modify: `src/assistente/server_mcp.py`
- Create: `preferenze.example.json` (radice del progetto, contenuto esatto del §5.1)
- Test: `tests/test_server_mcp.py`

**Interfaces:**
- Produces:
  - `PERCORSO_PREFERENZE_PREDEFINITO: Path = Path(__file__).resolve().parents[2] / "data" / "preferenze.json"`
  - `percorso_preferenze(env: Mapping[str, str] = os.environ) -> Path`: `PREFERENZE_PATH` dopo `strip`, se non vuota, altrimenti il predefinito
  - `crea_server(archivio, client_http=None, percorso_preferenze: str | Path | None = None) -> FastMCP`: con `None` usa `PERCORSO_PREFERENZE_PREDEFINITO`

- [ ] **Step 1: test che falliscono** (server reale con `avvia_server_mcp`, `Client(url).read_resource("utente://preferenze")`; file in `tmp_path`):
  - `test_resource_restituisce_il_testo_del_file`: `[c] = risultato`; `c.text` è uguale al testo scritto e `c.mimeType == "application/json"`.
  - `test_resource_riletta_a_ogni_richiesta`: si scrive il file, si legge, si riscrive con un altro contenuto, si rilegge; la seconda lettura dà il nuovo testo, senza riavviare il server.
  - `test_resource_toglie_il_bom`: file scritto con `encoding="utf-8-sig"` → `json.loads(c.text)` riesce e `c.text` non inizia con `"﻿"`.
  - `test_resource_file_mancante_da_errore_con_percorso`: `pytest.raises(Exception)` e il messaggio contiene il nome del file; WARNING sul logger `assistente.server_mcp`.
  - `test_strumenti_invariati_e_resource_elencata`: `list_tools()` dà i quattro nomi di oggi; `list_resources()` contiene `utente://preferenze`.
  - `test_percorso_predefinito_indipendente_dalla_cartella_corrente`: con `monkeypatch.chdir(tmp_path)` e `PREFERENZE_PATH` assente, `percorso_preferenze({}) == PERCORSO_PREFERENZE_PREDEFINITO`, che termina con `data/preferenze.json` ed è assoluto, con la cartella padre di `data` che contiene `src/assistente/server_mcp.py`.
  - `test_percorso_da_variabile`: `percorso_preferenze({"PREFERENZE_PATH": " x/p.json "}) == Path("x/p.json")`.
  - `test_esempio_versionato_valido`: `json.loads` di `preferenze.example.json` è uguale al dizionario del §5.1.
- [ ] **Step 2:** i test falliscono.
- [ ] **Step 3:** implementare:
  - la resource con `@server.resource("utente://preferenze", mime_type="application/json", description=...)`; `Path.read_text(encoding="utf-8-sig")`; `OSError` e `UnicodeDecodeError` diventano `ResourceError(f"{percorso}: {causa}")`, più un WARNING;
  - INFO a lettura riuscita;
  - in `main()`: `crea_server(..., percorso_preferenze=percorso_preferenze())`, con il percorso nel messaggio di avvio.

  Verificare quale testo dell'errore arriva al client con `ResourceError` (spec §3.1).
- [ ] **Step 4:** suite completa verde; le chiamate esistenti a `crea_server` non cambiano.
- [ ] **Step 5:** commit `feat(preferenze): espone la resource utente://preferenze dal server MCP`.

### Task 3: `leggi_resource` nel client MCP

**Files:**
- Modify: `src/assistente/mcp_client.py`
- Test: `tests/test_mcp_client.py`

**Interfaces:**
- Consumes: `crea_server(..., percorso_preferenze=...)` (T2).
- Produces: `leggi_resource(url: str, uri: str, timeout: float = 10.0) -> str`, che solleva `ErroreMcp`. Il messaggio di `ErroreMcp` contiene l'`uri`, l'`url` e `_testo_errore(errore)`.

- [ ] **Step 1: test che falliscono:**
  - `test_leggi_resource_restituisce_il_testo`: server reale con un file temporaneo → testo uguale al contenuto del file.
  - `test_leggi_resource_file_mancante_errore_mcp`: `ErroreMcp`, con il nome del file nel messaggio.
  - `test_leggi_resource_server_spento`: `porta_chiusa()` → `ErroreMcp`.
  - `test_leggi_resource_server_muto_rispetta_il_timeout`: `porta_muta()` con `timeout=1` → `ErroreMcp` entro 5 s (misurato con `time.monotonic`).
  - `test_leggi_resource_non_crea_strumenti`: `scopri_strumenti(url)` sullo stesso server → i quattro nomi di oggi; nessun nome o descrizione contiene `preferenze`.
- [ ] **Step 2:** i test falliscono.
- [ ] **Step 3:** implementare `async def _leggi(url, uri, timeout)`, sul modello di `_elenca` (`asyncio.timeout`, `Client(url, timeout=timeout)`). Restituisce il `.text` del primo contenuto che ce l'ha; se nessuno ce l'ha, solleva un errore che diventa `ErroreMcp`. Poi `leggi_resource` con `_esegui`; qualunque `Exception` diventa `ErroreMcp`.
- [ ] **Step 4:** suite completa verde.
- [ ] **Step 5:** commit `feat(preferenze): aggiunge la lettura delle resource al client MCP`.

### Task 4: orologio con il fuso della sessione, composizione e avvio

**Files:**
- Modify: `src/assistente/strumenti.py`, `src/assistente/terminale.py`
- Test: `tests/test_strumenti.py`, `tests/test_terminale.py`

**Interfaces:**
- Consumes: `Preferenze`, `PREFERENZE_PREDEFINITE`, `carica_preferenze` (T1); `leggi_resource` (T3).
- Produces:
  - `leggi_orologio(timezone=None, adesso=adesso_utc, predefinito: str = FUSO_PREDEFINITO) -> str`
  - `crea_orologio(fuso: str) -> BaseTool`: nome `orologio`, parametro `timezone: str | None` con predefinito `fuso`, descrizione del §9 con `{fuso}` sostituito
  - `STRUMENTI = [crea_orologio(FUSO_PREDEFINITO), converti_unita, calcola]`; il nome `orologio` resta esportato e uguale a `STRUMENTI[0]`
  - `componi_strumenti(config, scopri=..., dormi=..., adesso=..., chiedi_conferma=None, carica_preferenze: Callable[[], Preferenze] | None = None) -> tuple[list[BaseTool], Preferenze, list[str]]`. Ordine: discovery (con l'attesa invariata, anche in caso di fallimento), poi `carica_preferenze()`, poi l'elenco `[crea_orologio(p.fuso_orario), converti_unita, calcola, *http, *mcp]`. Con `None`: `PREFERENZE_PREDEFINITE`, senza lettura
  - `terminale.main()` passa `carica_preferenze=lambda: preferenze.carica_preferenze(config, leggi_resource)` e consegna le preferenze a `costruisci_grafo(..., preferenze=...)` (T5)

- [ ] **Step 1: test che falliscono:**
  - `test_crea_orologio_senza_argomenti_usa_il_fuso`: `crea_orologio("America/New_York").invoke({})` → testo con `(America/New_York, UTC-0`. L'istante reale basta: l'offset di New York è sempre negativo. Per un istante controllato, `leggi_orologio(None, adesso=..., predefinito="America/New_York")` con 2026-11-16 10:00 UTC → `2026-11-16 05:00:00 (America/New_York, UTC-05:00)`.
  - `test_crea_orologio_con_altro_fuso`: `timezone="Asia/Tokyo"` → `Asia/Tokyo`.
  - `test_crea_orologio_descrizione`: contiene `se omesso si usa America/New_York`.
  - `test_ordine_discovery_preferenze_orologio`: `scopri` e `carica_preferenze` finti registrano su una lista comune → `["scopri", "preferenze"]`; il primo strumento restituito dà l'ora di New York quando le preferenze hanno quel fuso.
  - `test_discovery_fallita_carica_comunque_le_preferenze`: `scopri` che solleva `ErroreMcp` con attesa 0 → avviso `AVVISO_MCP` invariato e `carica_preferenze` chiamato una volta.
  - `test_senza_carica_preferenze_usa_i_predefiniti`: preferenze restituite `== PREFERENZE_PREDEFINITE`.
  - `test_main_bind_tools_senza_resource` (in `test_terminale.py`, server reale con file di preferenze temporaneo `America/New_York` e `crea_modello` finto che registra `strumenti`): nomi = `NOMI_LOCALI + NOMI_HTTP + 4 MCP`; nessun nome o descrizione contiene `utente://`; l'orologio registrato senza argomenti dà New York.
  - Gli adattamenti meccanici elencati in «Test esistenti che cambiano».
- [ ] **Step 2:** i test nuovi falliscono.
- [ ] **Step 3:** implementare. `crea_orologio` usa `StructuredTool.from_function` oppure un `@tool` definito dentro la funzione, a scelta, purché `args` contenga `timezone`. Il `costruisci_grafo` di `main()` riceve `preferenze` solo da T5: in questo task la variabile è già pronta.
- [ ] **Step 4:** suite completa verde.
- [ ] **Step 5:** commit `feat(preferenze): costruisce l'orologio con il fuso delle preferenze all'avvio`.

### Task 5: prompt di sistema dell'agente

**Files:**
- Modify: `src/assistente/grafo.py`, `src/assistente/terminale.py` (passa `preferenze`)
- Test: `tests/test_grafo.py` (nuovi); `tests/test_revisore.py`, `tests/test_terminale.py`, `tests/test_riassunto.py` (adattamenti)

**Interfaces:**
- Consumes: `Preferenze`, `PREFERENZE_PREDEFINITE`, `testo_prompt` (T1); `CORNICE_AGENTE` (Step 3).
- Produces: `costruisci_grafo(..., preferenze: Preferenze = PREFERENZE_PREDEFINITE)`. `nodo_modello` invia `[SystemMessage(sistema), *contesto_agente(...)]`, dove `sistema` è `testo_prompt(preferenze)` oppure, con riassunto, `testo_prompt(preferenze) + "\n\n" + CORNICE_AGENTE.format(riassunto=riassunto)`. Il testo delle preferenze si calcola una volta, alla costruzione del grafo.

- [ ] **Step 1: test che falliscono** in `test_grafo.py`:
  - `test_agente_riceve_un_solo_system_message_con_le_preferenze`: preferenze `inglese/America/New_York/dettagliato` → esattamente un `SystemMessage`, in posizione 0, con contenuto `testo_prompt(...)`.
  - `test_system_message_con_riassunto_unisce_preferenze_e_cornice`: contenuto `testo_prompt(p) + "\n\n" + CORNICE_AGENTE.format(riassunto="R")`; un solo `SystemMessage`.
  - `test_system_message_non_entra_nello_stato`: nessun `SystemMessage` in `esito["messages"]`.
  - `test_router_e_revisore_non_vedono_le_preferenze`: con preferenze non predefinite, i prompt registrati dal classificatore e dal revisore finti non contengono `Preferenze dell'utente` e sono uguali a quelli ottenuti con `PREFERENZE_PREDEFINITE`.
  - Gli adattamenti dei 7 test elencati in «Test esistenti che cambiano».
- [ ] **Step 2:** i test nuovi falliscono; misurare che falliscano **esattamente** i 7 attesi.
- [ ] **Step 3:** implementare in `nodo_modello`; `main()` passa `preferenze=`.
- [ ] **Step 4:** suite completa verde; `test_limite.py` senza modifiche.
- [ ] **Step 5:** commit `feat(preferenze): mette le preferenze in cima al prompt di sistema dell'agente`.

### Task 6: Docker e documentazione

**Files:**
- Modify: `compose.yaml` (servizio `server-mcp`: `volumes: - ./data:/preferenze:ro`, `environment: PREFERENZE_PATH: /preferenze/preferenze.json`), `README.md`
- Test: nessuno automatico; verifiche a mano qui sotto

- [ ] **Step 1:** `docker compose config` valido; il servizio `server-mcp` mostra i due volumi (`dati-note` e `./data`).
- [ ] **Step 2:** verificare i comandi del README in una cartella temporanea senza `data/` (Review Focus 5):

  ```powershell
  New-Item -ItemType Directory -Force data | Out-Null
  Copy-Item preferenze.example.json data\preferenze.json
  ```
- [ ] **Step 3:** README, con solo comandi verificati:
  - sezione «Preferenze dell'utente»: creazione del file, formato e valori ammessi, valori predefiniti, `PREFERENZE_PATH` e percorso predefinito, log da cercare (`assistente.preferenze`, `assistente.server_mcp`), comportamento senza file o senza server, montaggio Docker;
  - variabili del server MCP aggiornate;
  - righe in «Limitazioni note» (§16 della specifica).
- [ ] **Step 4:** suite completa verde; commit `docs(preferenze): documenta le preferenze e il montaggio Docker` (con `compose.yaml`).

### Task 7: prove reali (a mano)

Prove R1–R6 della specifica §14, in quest'ordine. I comandi esatti si registrano in `prove_reali/PROVE.md`, nella nuova sezione «Step 4», insieme ai log rilevanti, alle risposte e alle latenze.

- [ ] **Step 1:** R1–R5 in locale, con `NOTE_DB_PATH` temporaneo e `PREFERENZE_PATH` temporaneo oppure `data/preferenze.json`.
  - Per R2 si modifica solo il file e si riavvia solo l'agente; il server resta acceso.
  - Se il Revisore boccia la risposta in inglese o il modello ignora lingua o stile: al massimo 2 tentativi, poi si documenta e si chiede all'utente.
  - Se un tentativo tocca il testo dell'Appendice A, prima serve l'accordo dell'utente: il testo è fissato dalla specifica.
- [ ] **Step 2:** R6 con Docker; `.env` ripristinato alla fine.
- [ ] **Step 3:** commit `docs(preferenze): registra le prove reali dello Step 4`.

### Task 8: chiusura

- [ ] **Step 1:** review indipendente dell'intero ramo (`superpowers:requesting-code-review`); i rilievi bloccanti si correggono, i minori si documentano.
- [ ] **Step 2:** resoconto all'utente: che cosa è stato eseguito, con quale esito, che cosa resta da provare.
- [ ] **Step 3:** con **autorizzazione esplicita**:
  - `CLAUDE.md` (modulo `preferenze`, `PREFERENZE_PATH`);
  - `git merge --no-ff feat/preferenze` su `dev`;
  - suite verde;
  - eliminazione del ramo.

  Push solo su richiesta.
