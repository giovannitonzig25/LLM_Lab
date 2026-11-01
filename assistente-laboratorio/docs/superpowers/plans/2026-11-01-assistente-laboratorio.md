# Assistente del laboratorio: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (execution method chosen by the user: native, in the current session, no per-task subagents). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** chat da terminale con grafo LangGraph esplicito, modello locale in LM Studio, cronologia di sessione, strumento orologio con tool calling, avviabile con Docker Compose.

**Architecture:** grafo a due nodi (`modello`, `strumenti`) con arco condizionale; il modello è iniettato nel grafo. Il term\inale conserva la cronologia validata e la aggiorna solo se il turno termina senza errore. Moduli piccoli: `config`, `modello`, `strumenti`, `grafo`, `terminale`.

**Tech Stack:** Python sincrono, `langgraph`, `langchain-openai`, `tzdata`, `pytest`, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-01-assistente-laboratorio-design.md`

## Global Constraints

- Lavorare solo in `assistente-laboratorio/`; non toccare le altre lezioni, né `.venv` e `requirements.txt` della radice.
- Branch `dev` corrente; nessun branch o worktree nuovo; nessun push.
- Indirizzo del server e identificativo del modello solo da `LM_STUDIO_BASE_URL` e `LM_STUDIO_MODEL`, senza valori predefiniti; `MAX_PASSAGGI` predefinito 6, valore iniziale configurabile (= `recursion_limit` di LangGraph). Non si assume quanti cicli di strumento garantisca: il comportamento si misura nei test (Task 5).
- Modello `google/gemma-4-e2b`; l'identificativo reale si verifica con `GET /v1/models`.
- Strumento `orologio`, parametro `timezone` (IANA), predefinito `Europe/Rome`; risultato con data, ora, nome del fuso e offset.
- Turno interrotto dal limite: cronologia ripristinata, messaggio chiaro, la chat continua.
- Niente streaming, MCP, RAG, altri strumenti, interfacce grafiche, persistenza.
- Dipendenze solo quelle della tabella sotto, con versioni fissate (`==`); mai `.env`, `.venv`, cache o pesi in Git.
- Comandi in PowerShell. Commit Conventional Commits in italiano, un'estensione per commit; prima di ogni commit `git status`, controllo del diff, staging dei soli file pertinenti.
- I test automatici non usano né rete né modello.

## Dipendenze da approvare

| Pacchetto | Perché | Dove |
|---|---|---|
| `langgraph` | grafo esplicito (porta `langchain-core`) | `requirements.txt` |
| `langchain-openai` | client per l'API compatibile OpenAI di LM Studio, con `bind_tools` (porta `openai`) | `requirements.txt` |
| `tzdata` | database dei fusi per `zoneinfo` su Windows e Docker slim | `requirements.txt` |
| `pytest` | test automatici | `requirements-dev.txt` (include `-r requirements.txt`) |

Si fissano con `==` le sole dipendenze dirette, alla versione installata nell'ambiente (verificata con `pip freeze`); le transitive no (mia scelta, per restare semplici). `requirements-dev.txt` tiene `pytest` fuori dall'immagine Docker.

## Struttura dei file

```
src/assistente/{__init__,config,modello,strumenti,grafo,terminale}.py
tests/{finti,test_grafo,test_terminale,test_config,test_strumenti,test_instradamento,test_limite}.py
prove_reali/verifica_modelli.py   prove_reali/PROVE.md
pytest.ini  .gitignore  .env.example  requirements.txt  requirements-dev.txt
Dockerfile  .dockerignore  compose.yaml  README.md
```

`pytest.ini`: `pythonpath = src`, `testpaths = tests`. Avvio locale: `$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.terminale`.

## Review Focus

Casi che la specifica implica ma che nessun incremento esegue per costruzione; ogni riga ha il test nel compito indicato.

1. Riga vuota o solo spazi alla domanda: ignorata, non entra in cronologia (Task 1).
2. Ctrl+D (EOF) e Ctrl+C: uscita pulita, senza traceback (Task 1).
3. Il modello chiede uno strumento inesistente: messaggio d'errore come risultato, nessun crash (Task 5).
4. `timezone` malformato: `None`, `""`, `42`, `"../etc"`, `"Mars/Base"`: predefinito o errore chiaro, mai eccezione (Task 4).
5. Risposta del modello con testo vuoto: la chat stampa un avviso invece di una riga vuota (Task 3).

Altri casi già coperti: più richieste di strumento nello stesso messaggio (Task 5); server fermo o modello rifiutato (Task 2); `MAX_PASSAGGI` non valido (Task 2).

---

## Incremento 1: grafo con risposta fissa

### Task 1: scheletro, grafo con nodo a risposta fissa e terminale

Il grafo di questo incremento non dipende da alcun modello, nemmeno simulato: un nodo restituisce direttamente una risposta fissa.

**Files:**
- Create: `.gitignore`, `requirements.txt` (solo `langgraph==<installata>`), `requirements-dev.txt`, `pytest.ini`, `README.md` (ambiente e test), `src/assistente/__init__.py`, `grafo.py`, `terminale.py`, `tests/test_grafo.py`, `tests/test_terminale.py`
- Docs: `docs/superpowers/specs/…`, `docs/superpowers/plans/…` (commit a parte)

**Interfaces:**
- Produces:
  - `grafo.py`: `RISPOSTA_FISSA: str = "Risposta fissa dal grafo."`; `class Stato(TypedDict)` con `messages: Annotated[list[AnyMessage], add_messages]`; `costruisci_grafo() -> CompiledStateGraph` con un solo nodo `risposta_fissa` che accoda `AIMessage(RISPOSTA_FISSA)`.
  - `terminale.py`: `esegui_chat(grafo, leggi: Callable[[], str], scrivi: Callable[[str], None]) -> None`; `main() -> int` (costruisce il grafo e avvia la chat).

- [ ] **Step 1: Commit dei documenti.** `git status`; `git add docs/superpowers/specs docs/superpowers/plans`; commit `docs: aggiunge specifica e piano del laboratorio`.
- [ ] **Step 2: Ambiente.** `python -m venv .venv` in `assistente-laboratorio/`; installare `langgraph` e `pytest`; annotare la versione di Python (serve al Dockerfile) e fissare le versioni con `pip freeze`. Scrivere `.gitignore` (`.venv/`, `.env`, `__pycache__/`, `.pytest_cache/`), `pytest.ini`, i due requirements.
- [ ] **Step 3: Test che falliscono.** In `tests/test_grafo.py`:
  - `test_risposta_fissa_attraversa_il_grafo`: `costruisci_grafo().invoke({"messages": [HumanMessage("Salve")]})` restituisce `[HumanMessage, AIMessage]` e l'ultimo contenuto è `RISPOSTA_FISSA`.
  
  In `tests/test_terminale.py` (leggi da una lista, scrivi su una lista):
  - `test_esci_termina_la_chat`; `test_domanda_stampa_la_risposta` (con il grafo reale, `RISPOSTA_FISSA` compare nell'output);
  - `test_riga_vuota_ignorata`: `["", "   ", "esci"]` con un grafo-spia scritto a mano (conta le chiamate a `invoke`) → zero chiamate;
  - `test_eof_e_ctrl_c_terminano_senza_eccezioni`: `leggi` che solleva `EOFError`, poi `KeyboardInterrupt`.
- [ ] **Step 4: Eseguire** `.\.venv\Scripts\python.exe -m pytest -v` → FAIL (moduli mancanti).
- [ ] **Step 5: Implementare** `costruisci_grafo` (nodo `risposta_fissa`, arco da START al nodo e dal nodo a END) ed `esegui_chat` (per ora senza cronologia: ogni domanda è un turno a sé). Nessun modello, nemmeno simulato.
- [ ] **Step 6: Eseguire** i test → PASS. Scrivere nel README: preparazione dell'ambiente e comando dei test.
- [ ] **Step 7: Commit** (due, nell'ordine): `feat(grafo): aggiunge il grafo con risposta fissa`; `docs: descrive ambiente e test nel README`.

**Verifica senza modello:** tutti i test del Task. **Prove reali:** nessuna.

---

## Incremento 2: LM Studio e cronologia

### Task 2: configurazione e collegamento a LM Studio

**Files:**
- Create: `src/assistente/config.py`, `modello.py`, `.env.example`, `prove_reali/verifica_modelli.py`, `prove_reali/PROVE.md`, `tests/finti.py`, `tests/test_config.py`
- Modify: `grafo.py` (il nodo a risposta fissa diventa il nodo `modello`), `terminale.py` (`main()` e gestione errori del server), `tests/test_grafo.py`, `requirements.txt` (`langchain-openai`), `README.md`

**Interfaces:**
- Produces:
  - `tests/finti.py`: `class ModelloSimulato(risposte: list[AIMessage], ripeti_ultima: bool = False)` con `invoke(messaggi: list[BaseMessage]) -> AIMessage` e attributo `chiamate: list[list[BaseMessage]]` (copia dei messaggi ricevuti a ogni chiamata).
  - `grafo.py`: `costruisci_grafo(modello) -> CompiledStateGraph` sostituisce la versione senza argomenti (il modello espone `invoke(list[BaseMessage]) -> AIMessage`); il nodo `modello` chiama `modello.invoke(stato["messages"])`. `RISPOSTA_FISSA` viene rimosso.
  - `config.py`: `class ErroreConfigurazione(Exception)`; `@dataclass(frozen=True) class Config: base_url: str; modello: str; max_passaggi: int`; `carica_config(env: Mapping[str, str] = os.environ) -> Config`.
  - `modello.py`: `crea_modello(config: Config, strumenti: Sequence[BaseTool] = ()) -> Runnable` (`ChatOpenAI` con `base_url`, `api_key` fittizia non segreta, `model`, `temperature=0`; con strumenti, `bind_tools`).
  - `terminale.main() -> int`: carica la config (errore → messaggio e codice 1), configura `logging` su stderr (INFO), costruisce modello e grafo, chiama `esegui_chat`.
  - `esegui_chat`: un `openai.OpenAIError` in un turno stampa un messaggio chiaro che rimanda a `GET /v1/models` e la chat continua.

- [ ] **Step 1: Test che falliscono.** In `tests/test_grafo.py` (sostituisce il test a risposta fissa): `test_il_nodo_modello_usa_il_modello_iniettato` (con `ModelloSimulato([AIMessage("Ciao")])` l'ultimo messaggio è `"Ciao"` e `chiamate` ha un elemento). In `tests/test_terminale.py` i test del Task 1 passano a un grafo costruito con `ModelloSimulato`; `test_riga_vuota_ignorata` verifica `chiamate == []`. In `tests/test_config.py`: `test_config_valida`; `test_manca_base_url` e `test_manca_modello` (`ErroreConfigurazione`, il messaggio nomina la variabile); `test_valori_vuoti_sono_mancanti`; `test_max_passaggi_predefinito_6`; `test_max_passaggi_non_valido` (`"abc"`, `"0"`, `"-1"`). In `test_terminale.py`: `test_errore_del_server_non_interrompe_la_chat` (modello finto che solleva `openai.APIConnectionError`; poi una domanda riuscita).
- [ ] **Step 2: Eseguire** → FAIL.
- [ ] **Step 3: Implementare** `config.py`, `modello.py`, `main()` e la gestione dell'errore del server. `verifica_modelli.py` con la sola libreria standard: legge `LM_STUDIO_BASE_URL` e `LM_STUDIO_MODEL`, chiama `GET {base_url}/models`, stampa gli identificativi, esce con codice 1 se quello configurato non c'è.
- [ ] **Step 4: Eseguire** i test → PASS.
- [ ] **Step 5: Prova reale (LM Studio attivo, `.env` creato da `.env.example`).** Caricare le variabili in PowerShell, eseguire `.\.venv\Scripts\python.exe prove_reali\verifica_modelli.py`, correggere `LM_STUDIO_MODEL` con l'identificativo restituito. Poi avviare la chat: una domanda → risposta reale. Fermare il server e porre una domanda → messaggio chiaro; riavviare il server → la chat risponde di nuovo. Riportare gli esiti.
- [ ] **Step 6: README** (configurazione, avvio locale, verifica identificativo, diagnosi «errore HTTP»): solo comandi appena eseguiti. `PROVE.md`: elenco delle prove reali.
- [ ] **Step 7: Commit:** `feat(config): legge indirizzo e modello dall'ambiente`; `feat(modello): collega il grafo a LM Studio`; `docs: documenta configurazione e prove con LM Studio`.

**Senza modello:** test di config ed errore del server. **Con LM Studio:** Step 5.

### Task 3: cronologia di sessione

**Files:**
- Modify: `src/assistente/terminale.py`, `tests/test_terminale.py`, `README.md`

**Interfaces:**
- Consumes: `costruisci_grafo`, `ModelloSimulato`.
- Produces: `esegui_turno(grafo, cronologia: list[BaseMessage], domanda: str, max_passaggi: int) -> tuple[list[BaseMessage], str]` (nuova cronologia e testo da stampare; in caso di errore restituisce la cronologia ricevuta e il messaggio d'errore). `esegui_chat(grafo, max_passaggi: int, leggi, scrivi)` tiene la cronologia e usa `esegui_turno`; passa `recursion_limit=max_passaggi` all'`invoke`.

- [ ] **Step 1: Test che falliscono:** `test_la_seconda_domanda_vede_la_prima` (dopo due domande, `chiamate[1]` contiene `HumanMessage` e `AIMessage` del primo turno e la nuova domanda, in ordine); `test_cronologia_non_persiste_tra_sessioni` (due `esegui_chat` successive partono da zero); `test_errore_del_server_ripristina_la_cronologia`; `test_risposta_vuota_stampa_un_avviso` (contenuto `""` → avviso, non riga vuota).
- [ ] **Step 2: Eseguire** → FAIL.
- [ ] **Step 3: Implementare** `esegui_turno` ed `esegui_chat` con cronologia in memoria; adeguare i test del Task 1/2 alla nuova firma.
- [ ] **Step 4: Eseguire** tutti i test → PASS.
- [ ] **Step 5: Prova reale (LM Studio):** «Mi chiamo Marco» → «Come mi chiamo?» deve rispondere Marco; chiudere e riavviare: «Come mi chiamo?» non deve conoscere il nome. Riportare gli esiti.
- [ ] **Step 6: Commit:** `feat(terminale): conserva la cronologia della sessione`; `docs: aggiorna README con la cronologia`.

---

## Incremento 3: strumento orologio e instradamento

### Task 4: strumento orologio

**Files:**
- Create: `src/assistente/strumenti.py`, `tests/test_strumenti.py`
- Modify: `requirements.txt` (`tzdata`)

**Interfaces:**
- Produces: `leggi_orologio(timezone: str | None = None, adesso: Callable[[], datetime] = adesso_utc) -> str` (restituisce sempre testo, mai eccezioni; errore → riga che inizia con `Errore:`); `orologio: BaseTool` (nome `orologio`, argomento `timezone: str = "Europe/Rome"`, descrizione per il modello); `STRUMENTI: list[BaseTool] = [orologio]`.

- [ ] **Step 1: Test che falliscono**, con istante fisso `2026-11-01T14:04:05Z`:
  - `test_roma` → contiene `2026-11-01 15:04:05`, `Europe/Rome`, `+01:00`;
  - `test_tokyo` → contiene `2026-11-01 23:04:05`, `Asia/Tokyo`, `+09:00`;
  - `test_predefinito_e_roma` per `None` e `""`;
  - `test_fuso_non_valido_da_errore_chiaro` per `"Mars/Base"`, `"../etc"`, `42` (risultato inizia con `Errore:` e nomina il valore);
  - `test_orologio_ha_schema_con_timezone` (lo schema dello strumento espone `timezone`).
- [ ] **Step 2: Eseguire** → FAIL.
- [ ] **Step 3: Implementare** con `zoneinfo.ZoneInfo`, intercettando `ZoneInfoNotFoundError` e `ValueError`; l'offset formattato `UTC±HH:MM`.
- [ ] **Step 4: Eseguire** → PASS. **Step 5: Commit:** `feat(strumenti): aggiunge lo strumento orologio con fuso orario`.

### Task 5: nodo strumenti, instradamento, log e limite di passaggi

**Files:**
- Modify: `src/assistente/grafo.py`, `terminale.py`, `README.md`
- Create: `tests/test_instradamento.py`, `tests/test_limite.py`

**Interfaces:**
- Consumes: `STRUMENTI`, `crea_modello(config, strumenti)`.
- Produces: `costruisci_grafo(modello, strumenti: Sequence[BaseTool] = ()) -> CompiledStateGraph`; `instrada(stato: Stato) -> str` (`"strumenti"` se l'ultimo `AIMessage` ha `tool_calls`, altrimenti `END`). Logger `assistente.strumenti`, una riga per richiesta (`nome`, `argomenti`) e una per esito (`risultato` o errore). `esegui_turno` intercetta `GraphRecursionError`.

- [ ] **Step 1: Test che falliscono:**
  - `test_instrada_senza_tool_calls_termina`, `test_instrada_con_tool_calls_va_a_strumenti`;
  - `test_percorso_con_strumento`: modello simulato che prima chiede `orologio` con `{"timezone": "Asia/Tokyo"}` e poi risponde; il secondo `invoke` riceve un `ToolMessage` con lo stesso `tool_call_id` e il testo dell'orologio; l'ultimo messaggio è la risposta finale;
  - `test_due_richieste_nello_stesso_messaggio`: due `ToolMessage`, uno per identificativo;
  - `test_strumento_inesistente_da_errore_come_risultato` (nessuna eccezione, il modello riceve `Errore:`);
  - `test_log_richiesta_ed_esito` (`caplog`: righe con `orologio` e `Asia/Tokyo`, e con il risultato);
  - `test_caratterizza_il_limite_di_passaggi` (con `ripeti_ultima=True` e limite 6, poi 2): non assume valori. Registra quante chiamate al modello e quanti `ToolMessage` avvengono prima dell'interruzione, e fissa nel test i valori osservati, annotati poi nel README;
  - `tests/test_limite.py`, modello simulato con `ripeti_ultima=True` che chiede sempre lo strumento: `test_limite_ripristina_la_cronologia` (cronologia uguale a quella precedente alla domanda), `test_nessun_messaggio_parziale_resta` (nessun `ToolMessage` né `AIMessage` con `tool_calls` del turno scartato), `test_messaggio_chiaro_all_utente` (dice che la richiesta non è stata completata e che si può riprovare o riformulare), `test_la_chat_continua_dopo_il_limite` (una domanda successiva ottiene risposta), `test_log_del_limite`.
- [ ] **Step 2: Eseguire** → FAIL.
- [ ] **Step 3: Implementare** il nodo `strumenti` (cerca lo strumento per nome, esegue, aggiunge un `ToolMessage` per chiamata, logga), l'arco condizionale con `instrada`, il ritorno da `strumenti` a `modello`; in `esegui_turno` la gestione di `GraphRecursionError`. `main()` passa `STRUMENTI` a `crea_modello` e `costruisci_grafo`.
- [ ] **Step 4: Eseguire** tutta la suite → PASS.
- [ ] **Step 5: Prova reale (LM Studio):** «Che ora è a Tokyo?» → il log mostra la richiesta con `Asia/Tokyo` e l'esito; la risposta usa l'ora ottenuta. «Che ora è?» → `Europe/Rome`. Con `MAX_PASSAGGI=2` una domanda sull'ora → messaggio di limite e cronologia intatta. **Se `gemma-4-e2b` non chiama lo strumento, riportarlo così com'è**, senza forzare la chiamata né aggiungere trucchi; in tal caso fermarsi e consultare l'utente.
- [ ] **Step 6: README** (strumento, log, `MAX_PASSAGGI`, test). **Step 7: Commit:** `feat(grafo): esegue gli strumenti richiesti dal modello`; `feat(terminale): scarta il turno oltre il limite di passaggi`; `docs: descrive strumento, log e limite`.

---

## Incremento 4: Docker Compose e verifica completa

### Task 6: contenitore e verifica finale

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `compose.yaml`
- Modify: `.env.example` (`LM_STUDIO_DOCKER_URL` facoltativo, commentato), `README.md`, `prove_reali/PROVE.md`, `CLAUDE.md` (struttura e comandi di test, ora stabili)

**Interfaces:**
- Produces: servizio `assistente`, `docker compose run --rm assistente`.

- [ ] **Step 1: Scrivere** `Dockerfile` (`python:<minor di .venv>-slim`, `PYTHONPATH=/app/src`, installa `requirements.txt`, copia `src` e `prove_reali`, utente non root, comando `python -m assistente.terminale`), `.dockerignore` (`.env`, `.venv`, `.git`, cache, `tests`, `docs`) e `compose.yaml` (un servizio, `stdin_open: true`, `tty: true`, `env_file: .env`, `environment: LM_STUDIO_BASE_URL: ${LM_STUDIO_DOCKER_URL:-http://host.docker.internal:1234/v1}`; `extra_hosts` solo se la prova lo richiede). L'indirizzo di Docker sovrascrive quello locale di `.env` (mia scelta).
- [ ] **Step 2: Verificare la configurazione:** `docker compose config` valido e senza segreti in chiaro nel file; `docker compose build`.
- [ ] **Step 3: Prova reale (Docker Desktop e LM Studio attivi):**
  1. `docker compose run --rm --entrypoint python assistente prove_reali/verifica_modelli.py` → raggiunge l'host e vede il modello;
  2. `docker compose run --rm assistente`: «Mi chiamo Marco» → «Come mi chiamo?»; «Che ora è a Tokyo?» con la riga di log dello strumento; `esci`;
  3. server fermo e ripristinato.
  
  Se l'host non è raggiungibile, diagnosticare (porta, «Serve on Local Network» di LM Studio, `extra_hosts`) e documentare solo ciò che è stato verificato.
- [ ] **Step 4: Verifica completa:** `.\.venv\Scripts\python.exe -m pytest -v` (tutti verdi), le prove reali locali dei Task 2, 3, 5 ripetute in sintesi, `git status` senza `.env`, `.venv` o cache.
- [ ] **Step 5: README** (avvio con Docker, diagnosi, struttura) e `CLAUDE.md` (struttura e comandi di test stabili, senza annotare l'avanzamento).
- [ ] **Step 6: Commit:** `feat(docker): avvia l'assistente con Docker Compose`; `docs: documenta l'avvio con Docker e la verifica`.
- [ ] **Step 7: Resoconto:** che cosa è stato eseguito e con quale esito (test automatici, prove con LM Studio, prove con Docker) e che cosa resta da provare. Nessun merge su `main` e nessun push senza richiesta.

---

## Auto-revisione

- **Copertura della specifica:** obiettivi 1–7, limite con scarto del turno (Task 5), strumento con `timezone` (Task 4), log (Task 5), Docker (Task 6), README (ogni incremento), dipendenze (tabella).
- **Precisazioni dell'utente:** il Task 1 usa un nodo a risposta fissa senza modello; il modello simulato e quello reale arrivano nel Task 2. `MAX_PASSAGGI=6` è un valore iniziale: i cicli effettivi si misurano nel Task 5. Esecuzione nativa nella sessione corrente.
- **Coerenza dei tipi:** `costruisci_grafo` cambia firma al Task 2 (da senza argomenti a `modello`) e al Task 5 (aggiunge `strumenti`); `esegui_turno` e `esegui_chat` hanno firma finale dal Task 3; `costruisci_grafo` acquista `strumenti` al Task 5, con valore predefinito che mantiene validi i test precedenti.
- **Lasciato al costruttore:** testi esatti dei messaggi e dei log (i test controllano sottostringhe), versioni delle librerie, versione di Python.
- **Non incluso:** un messaggio di sistema per guidare il modello. Se la prova reale mostra che serve, si decide con l'utente.
