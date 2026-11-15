# Lezione 6, Step 1 — Router di ambito: piano di implementazione

> **Per gli esecutori:** SOTTO-SKILL RICHIESTA: `superpowers:executing-plans` (nativa) oppure `superpowers:subagent-driven-development`, secondo la scelta dell'utente. I passi usano la sintassi a caselle (`- [ ]`). Leggere la specifica per intero prima di iniziare.

**Obiettivo:** aggiungere prima dell'agente un nodo Router LLM che classifica la domanda come `conversazione` o `fuori_ambito`; le richieste fuori ambito ricevono un rifiuto fisso e il turno termina senza agente né strumenti.

**Architettura:** il grafo diventa `START → router → (modello ⇄ strumenti | rifiuto) → END`. Un modulo nuovo, `router.py`, contiene schema, contesto, prompt, testo del rifiuto e nodo Router. `grafo.py` collega i nodi. Il classificatore è un client `ChatOpenAI` separato, senza strumenti, con output strutturato `json_schema`, iniettato nel grafo come oggi il modello. `esegui_turno` compensa il passaggio del Router nel `recursion_limit`.

**Stack:** Python 3.13, `langgraph==1.2.19`, `langchain-openai==1.7.3` (Pydantic arriva con LangChain), pytest. Nessuna dipendenza nuova.

**Specifica:** `docs/superpowers/specs/2026-11-15-router-ambito-design.md` (approvata il 2026-11-15). Le sezioni §5–§12 sono vincolanti; la §n citata in ogni task rimanda a lì.

## Vincoli globali

- Solo questo incremento: niente Revisore, riassunto della cronologia, primitive MCP nuove, back-end o front-end, ottimizzazioni di latenza o modelli nuovi.
- Ambito solo da `AMBITO_AGENTE`: obbligatoria, `strip`, non vuota, al massimo **500** caratteri; nessun testo predefinito nel codice.
- Router: client separato **senza `bind_tools`**, `temperature=0`, `reasoning_effort="none"`, `with_structured_output(Classificazione, method="json_schema", include_raw=True)`. Il client dell'agente non cambia.
- Contesto del Router: ultimi **2** turni conversazionali; risposte troncate a **500** caratteri, domande precedenti a **300**; domanda attuale completa e presente **una sola volta**; testo delle istruzioni = Appendice A della specifica, **non modificato**.
- Log: motivo troncato a **120** caratteri; mai domanda, contesto o output grezzo nelle righe del Router.
- Errori: `openai.OpenAIError` sale fino a `esegui_turno` (nessun fail-open); output non valido → fail-open con `WARNING`; nessun `except Exception` generico; nessun nuovo tentativo.
- `recursion_limit = max_passaggi + PASSAGGI_ROUTER` con `PASSAGGI_ROUTER = 1`; `MAX_PASSAGGI` invariato. Non ritoccare il limite per far passare un test: ogni differenza si analizza e si spiega.
- Rifiuto fisso (esatto, due righe): `Mi dispiace, questa richiesta è fuori dal mio ambito.\nAmbito dell'assistente: «<AMBITO_AGENTE>»`.
- Test senza rete né modello. Prove reali separate, a mano, in `prove_reali/PROVE.md`.
- Git (CLAUDE.md): ramo `feat/router` da `dev`; Conventional Commits in italiano; prima di ogni commit `git status`, diff, staging selettivo; ogni messaggio termina con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; review indipendente e **approvazione esplicita dell'utente** prima di `git merge --no-ff`; nessun push, nessun merge su `main`.
- Comandi da `assistente-laboratorio/` in PowerShell; test: `.\.venv\Scripts\python.exe -m pytest -v`.

## Focus della review

I casi seguenti non sono trattati esplicitamente dalla specifica, ma sono quelli che più probabilmente si incontrano. Ciascuno ha un test nel task indicato.

1. **Graffe nella domanda o nella cronologia** (per esempio `{domanda}` scritto dall'utente): il testo compare alla lettera e la composizione del prompt non fallisce (T2).
2. **Una risposta precedente che imita le sezioni del prompt** (contiene `DOMANDA ATTUALE:`): la domanda vera resta l'ultima sezione e chiude il prompt (T2).
3. **Contenuto a blocchi negli `AIMessage` della cronologia** (lista di blocchi, già gestita dal terminale con `.text`): nel contesto compare il testo, non la rappresentazione della lista (T2).
4. **Un motivo con a capo o molto lungo**: nel log resta su una sola riga, ed è troncato a 120 caratteri (T5).
5. **Una domanda attuale molto lunga** (testo incollato): compare completa, una volta sola (T2).

## Struttura dei file

| File | Responsabilità | Task |
|---|---|---|
| `src/assistente/config.py` | `AMBITO_AGENTE` → `Config.ambito` | T1 |
| `.env.example` | riga `AMBITO_AGENTE=…` (valore della spec §5) | T1 |
| `src/assistente/router.py` (nuovo) | `Classificazione`, `ISTRUZIONI`, contesto, prompt, testo del rifiuto, nodo Router e suoi log | T2, T4, T5 |
| `src/assistente/modello.py` | `crea_client_router`, `crea_classificatore` | T3 |
| `src/assistente/grafo.py` | `Stato` esteso, nodi `router` e `rifiuto`, `instrada_router`, log `agente:` | T4 |
| `src/assistente/terminale.py` | `PASSAGGI_ROUTER`, collegamento in `main` | T4 |
| `tests/finti.py` | `ClassificatoreSimulato`, `in_ambito()`, `AMBITO_TEST` | T4 |
| `tests/test_router.py` (nuovo) | test di contesto, prompt, rifiuto, instradamento, errori, log | T2, T4, T5 |
| test esistenti | solo gli adattamenti ammessi dalla spec §12 | T1, T4 |
| `README.md` | Router, variabile, `-Encoding UTF8`, latenza, filtro non di sicurezza | T6, T7 |
| `prove_reali/PROVE.md` | esiti delle prove reali | T7 |
| `CLAUDE.md` | riga "Struttura" con `router` (solo con autorizzazione) | T8 |

---

## Task 0 — Specifica e piano su `dev` (solo con autorizzazione dell'utente)

- [ ] **Step 1:** Chiedere all'utente l'autorizzazione al commit di specifica e piano. Senza autorizzazione ci si ferma qui.
- [ ] **Step 2:** `git switch dev; git status`. Devono comparire solo i due file in `docs/superpowers/` e `../LLM_Lez_6.pdf`, che non va aggiunto.
- [ ] **Step 3:** `git add docs/superpowers/specs/2026-11-15-router-ambito-design.md docs/superpowers/plans/2026-11-15-router-ambito.md`; commit `docs: aggiunge specifica e piano del Router di ambito`.
- [ ] **Step 4:** `git switch -c feat/router`.

---

## Task 1 — Configurazione `AMBITO_AGENTE` (spec §5)

**Files:** Modify `src/assistente/config.py`, `.env.example`, `tests/test_config.py`, `tests/test_strumenti.py` (solo `_ENV`), `tests/test_terminale.py` (solo i `monkeypatch.setenv` dei test di `main`).

**Interfaces — Produces:** `Config.ambito: str` (campo senza predefinito, subito dopo `max_passaggi`); costante `AMBITO_MAX_CARATTERI = 500` in `config.py`.

- [ ] **Step 1: test che falliscono** in `tests/test_config.py`:
  - aggiungere `"AMBITO_AGENTE": "Ambito di prova."` a `BASE`; in `test_config_valida` aggiungere `ambito="Ambito di prova."` al `Config(...)` atteso, senza altre modifiche;
  - aggiungere `"AMBITO_AGENTE"` al `parametrize` di `test_variabile_mancante_viene_nominata`;
  - `test_ambito_vuoto_o_di_spazi_e_mancante` (parametri `""`, `"   "`): `ErroreConfigurazione` con `match="AMBITO_AGENTE"`;
  - `test_ambito_viene_ripulito_dagli_spazi`: `"  Ambito.  "` → `config.ambito == "Ambito."`;
  - `test_ambito_al_limite_e_valido`: 500 caratteri → valido;
  - `test_ambito_troppo_lungo`: 501 caratteri → `ErroreConfigurazione` il cui messaggio contiene `"AMBITO_AGENTE"`, `"500"` e `"501"`.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_config.py -v` → i nuovi test FALLISCONO.
- [ ] **Step 3: implementare** in `carica_config`: lettura con `_obbligatoria(env, "AMBITO_AGENTE")`, poi controllo della lunghezza (messaggio con limite e lunghezza ricevuta).
- [ ] **Step 4: adattare i test** che costruiscono la configurazione (ammesso dalla spec §12):
  - `_ENV` in `tests/test_strumenti.py` riceve `"AMBITO_AGENTE": "a"`;
  - i test di `main` in `tests/test_terminale.py` ricevono `monkeypatch.setenv("AMBITO_AGENTE", "a")`.
  Nessuna asserzione cambia.
- [ ] **Step 5:** `.env.example`: dopo `LM_STUDIO_MODEL` aggiungere un commento («Ambito dell'agente, una riga, al massimo 500 caratteri; obbligatoria») e la riga `AMBITO_AGENTE=` con il valore esatto della spec §5.
- [ ] **Step 6:** suite completa → tutti verdi (407 + nuovi).
- [ ] **Step 7:** `git status`, diff, commit `feat(config): aggiunge la variabile obbligatoria AMBITO_AGENTE`.

---

## Task 2 — Contesto, prompt e testo del rifiuto (spec §6, §7, §10)

Funzioni pure, ancora senza collegamento al grafo.

**Files:** Create `src/assistente/router.py`, `tests/test_router.py`.

**Interfaces — Produces** (in `router.py`):
- `class Classificazione(BaseModel)`: `categoria: Literal["conversazione", "fuori_ambito"]`; `motivo: str = Field(min_length=1, description=DESCRIZIONE_MOTIVO)`. `DESCRIZIONE_MOTIVO` chiede, in italiano, «una motivazione breve e generica, senza ripetere il testo della richiesta né dati personali».
- Costanti: `TURNI_CONTESTO = 2`, `MAX_RISPOSTA_CONTESTO = 500`, `MAX_DOMANDA_CONTESTO = 300`, `NESSUNA_RISPOSTA = "(nessuna risposta)"`, `ISTRUZIONI` (testo esatto dell'Appendice A, con i segnaposto `{ambito}`, `{contesto}`, `{domanda}`).
- `turni_precedenti(messaggi: Sequence[BaseMessage]) -> list[tuple[str, str]]`: coppie `(domanda, risposta)` già troncate, al massimo `TURNI_CONTESTO`, in ordine cronologico, calcolate **escludendo l'ultimo `HumanMessage`** (la domanda attuale).
- `componi_prompt(messaggi: Sequence[BaseMessage], ambito: str) -> str`: la domanda attuale è il testo dell'ultimo `HumanMessage`; contesto con righe `Utente: …` / `Assistente: …`, oppure `(nessuno)`.
- `testo_rifiuto(ambito: str) -> str`: restituisce esattamente `"Mi dispiace, questa richiesta è fuori dal mio ambito.\nAmbito dell'assistente: «" + ambito + "»"`.

Algoritmo di `turni_precedenti`, non determinato dalla firma:
- ogni `HumanMessage` apre un turno;
- la risposta del turno è l'ultimo `AIMessage` senza `tool_calls` prima del `HumanMessage` successivo, letto con `.text`;
- i `ToolMessage` e gli `AIMessage` con `tool_calls` si ignorano;
- se la risposta è vuota o manca, si usa `NESSUNA_RISPOSTA`.

La composizione deve inserire i valori **una sola volta** (un solo `str.format` su `ISTRUZIONI`), così graffe nei valori non vengono reinterpretate.

- [ ] **Step 1: test che falliscono** in `tests/test_router.py` (costante `AMBITO = "Ambito di prova."`):
  - `test_continuazione_vede_il_turno_precedente`: cronologia `Human("Che tempo fa a Roma?")`, `AI("A Roma 14 °C.")`, `Human("E a Trieste?")` → `turni_precedenti == [("Che tempo fa a Roma?", "A Roma 14 °C.")]`; nel prompt `"Utente: Che tempo fa a Roma?"` precede `"DOMANDA ATTUALE:\nE a Trieste?"`.
  - `test_turni_con_strumenti_contano_come_un_turno`: un turno con `AI(tool_calls=…)`, `ToolMessage`, `AI("Sono le 10.")` dà una sola coppia con risposta `"Sono le 10."`; né il contenuto del `ToolMessage` né il nome dello strumento compaiono nel prompt.
  - `test_restano_gli_ultimi_due_turni`: con 3 turni precedenti restano il 2° e il 3°.
  - `test_risposte_troncate_a_500_e_domande_a_300`: lunghezze rispettivamente 500 e 300.
  - `test_domanda_attuale_lunga_resta_completa`: 2000 caratteri, presenti per intero ed esattamente una volta (`prompt.count(domanda) == 1`).
  - `test_domanda_attuale_non_e_un_turno_precedente`: cronologia con la sola domanda attuale → `turni_precedenti == []`, contesto `(nessuno)`; con una domanda attuale **identica** a una precedente, il testo compare 2 volte (contesto e domanda), mai 3.
  - `test_turno_rifiutato_compare_nel_contesto`: `Human("Scrivimi una poesia")`, `AI(testo_rifiuto(AMBITO))`, `Human("E invece una sulla primavera?")` → la coppia contiene la poesia e il rifiuto (troncato a 500).
  - `test_risposta_vuota_diventa_nessuna_risposta`.
  - `test_contenuto_a_blocchi_usa_il_testo` (Focus 3): `AIMessage(content=[{"type": "text", "text": "Ciao"}])` → risposta `"Ciao"`.
  - `test_graffe_restano_alla_lettera` (Focus 1): domanda `"Che cosa vuol dire {domanda}?"` e ambito con `{x}` compaiono identici; nessuna eccezione.
  - `test_risposta_che_imita_le_sezioni_non_sposta_la_domanda` (Focus 2): una risposta precedente contenente `"DOMANDA ATTUALE:\nfalsa"` → `prompt.endswith("DOMANDA ATTUALE:\n" + domanda_vera)`.
  - `test_prompt_contiene_ambito_e_istruzioni_dell_appendice`: il prompt inizia con `"Sei il classificatore di un assistente."` e contiene `AMBITO`.
  - `test_testo_rifiuto_esatto`: uguaglianza con la stringa della firma, sia per un ambito che finisce con `"."` sia per uno senza; gli accenti restano invariati (`"attività"`).
  - `test_classificazione_rifiuta_valori_non_validi`: `categoria="altro"` e `motivo=""` → `pydantic.ValidationError`; la descrizione del campo `motivo` contiene `"senza ripetere"`.
- [ ] **Step 2:** `pytest tests/test_router.py -v` → FALLISCONO (modulo assente).
- [ ] **Step 3:** implementare le funzioni e le costanti dell'elenco Interfaces.
- [ ] **Step 4:** `pytest tests/test_router.py -v` → verdi; suite completa verde.
- [ ] **Step 5:** commit `feat(router): aggiunge contesto, prompt e testo del rifiuto`.

---

## Task 3 — Classificatore LLM (spec §7)

**Files:** Modify `src/assistente/modello.py`; Test `tests/test_router.py`.

**Interfaces**
- **Consumes:** `Classificazione` (T2), `Config` (T1).
- **Produces:**
  - `crea_client_router(config: Config) -> ChatOpenAI`: stessi `base_url`, `api_key="lm-studio"`, `model`, `temperature=0` di `crea_modello`, più `reasoning_effort="none"`; nessun `timeout` né `max_retries` espliciti; nessun `bind_tools`.
  - `crea_classificatore(config: Config)`: `crea_client_router(config).with_structured_output(Classificazione, method="json_schema", include_raw=True)`.

- [ ] **Step 1: test che falliscono:**
  - `test_client_router_senza_ragionamento_e_senza_strumenti`: `reasoning_effort == "none"`, `temperature == 0`, `model_name` e `openai_api_base` presi dal `Config`; il client è un `ChatOpenAI` puro, non un `RunnableBinding` con strumenti.
  - `test_client_agente_invariato`: `crea_modello(config)` ha `reasoning_effort is None`.
  - `test_classificatore_si_costruisce_senza_rete`: `crea_classificatore(config)` restituisce un oggetto con `invoke`; non parte nessuna richiesta, perché costruirlo non contatta il server.
- [ ] **Step 2:** i test FALLISCONO.
- [ ] **Step 3:** implementare le due funzioni.
- [ ] **Step 4:** test verdi; suite completa verde.
- [ ] **Step 5:** commit `feat(modello): aggiunge il classificatore del Router senza strumenti`.

---

## Task 4 — Router nel grafo, rifiuto, limite e avvio (spec §4, §8 riga 1, §9, §10, §11)

Questo task è atomico per necessità. La compensazione del limite, il Router obbligatorio nel grafo e l'adattamento dei test vanno insieme: separati, la caratterizzazione esistente cambierebbe valori.

**Files:** Modify `src/assistente/router.py`, `src/assistente/grafo.py`, `src/assistente/terminale.py`, `tests/finti.py`, i test che chiamano `costruisci_grafo` (`test_calcolatrice`, `test_grafo`, `test_instradamento`, `test_limite`, `test_mcp_client`, `test_terminale`, `test_unita`) e i test di `main` in `test_terminale.py`; Test `tests/test_router.py`.

**Interfaces**
- **Consumes:** T2, T3; `Config.ambito`.
- **Produces:**
  - `tests/finti.py`:
    - `AMBITO_TEST = "Ambito di prova."`;
    - `ClassificatoreSimulato(esiti: list[Classificazione | dict | BaseException], ripeti_ultima: bool = False)`. `invoke(messaggi)` registra i messaggi in `self.chiamate`. Un esito `Classificazione` produce `{"raw": AIMessage(""), "parsed": esito, "parsing_error": None}`, un `dict` viene restituito così com'è, un'eccezione viene lanciata;
    - `in_ambito() -> ClassificatoreSimulato` (sempre `conversazione`, `ripeti_ultima=True`);
    - `fuori_ambito() -> ClassificatoreSimulato` (sempre `fuori_ambito`).
  - `router.py`: `crea_nodo_router(classificatore, ambito: str) -> Callable[[dict], dict]`. Il nodo invoca `classificatore.invoke([HumanMessage(componi_prompt(stato["messages"], ambito))])` e restituisce `{"categoria": ..., "motivo": ...}`. Scrive il log `INFO` del §11 sul logger `assistente.router`, con la `durata` misurata con `time.perf_counter()` e il suffisso `→ agente` / `→ rifiuto`. In questo task si gestisce solo il caso riuscito.
  - `grafo.py`:
    - `Stato` aggiunge `categoria: NotRequired[str]` e `motivo: NotRequired[str]`;
    - `instrada_router(stato) -> str` restituisce `"modello"` o `"rifiuto"`;
    - nodo `rifiuto`: `{"messages": [AIMessage(testo_rifiuto(ambito))]}` più il log `INFO` `rifiuto: risposta fissa, agente non eseguito` (logger `assistente.router`);
    - `nodo_modello` scrive il log `INFO` `agente: chiamata al modello` (logger `assistente.router`) prima di `modello.invoke`;
    - nuova firma `costruisci_grafo(modello, strumenti: Sequence[BaseTool] = (), *, classificatore, ambito: str)`;
    - archi `START → router`, `add_conditional_edges("router", instrada_router, ["modello", "rifiuto"])`, `rifiuto → END`; il resto invariato.
  - `terminale.py`: `PASSAGGI_ROUTER = 1`; `recursion_limit = max_passaggi + PASSAGGI_ROUTER`; il messaggio del limite e il log continuano a usare `max_passaggi`. `main` passa `classificatore=crea_classificatore(config), ambito=config.ambito`.

- [ ] **Step 1: test che falliscono** in `tests/test_router.py` (grafo con `ModelloSimulato`, gli `STRUMENTI` reali e `caplog` su `assistente.router` e `assistente.strumenti`):
  - `test_in_ambito_passa_all_agente`: risposta dell'agente restituita; log con `categoria=conversazione`, il motivo, `durata=` e `→ agente`, poi `agente: chiamata al modello`.
  - `test_fuori_ambito_rifiuta_senza_agente_ne_strumenti`: risposta `== testo_rifiuto(AMBITO_TEST)`; `modello.chiamate == []`; nessun log `agente:` né `strumento richiesto`; log `→ rifiuto` e `rifiuto: risposta fissa`.
  - `test_router_eseguito_una_volta_con_tool_calling`: agente → `orologio` → agente; `len(classificatore.chiamate) == 1`; i messaggi ricevuti dal classificatore sono un solo `HumanMessage` e nessun `AIMessage` con `tool_calls` esce dal Router.
  - `test_cronologia_dopo_il_rifiuto`: `esegui_turno` da `[Human("Ciao"), AI("Salve")]` con fuori ambito → cronologia `== precedente + [Human(domanda), AI(testo_rifiuto(...))]`; nessun messaggio contiene il motivo; nessun `additional_kwargs`/`name` aggiunto al rifiuto.
  - `test_cronologia_in_ambito_identica_a_prima`: stessa sequenza di contenuti e tipi di messaggi che si otteneva senza Router (confronto con i messaggi attesi scritti nel test).
  - `test_fuori_ambito_dopo_conversazione_pertinente`: cronologia su meteo, classificatore `fuori_ambito` → rifiuto, agente non chiamato; il prompt ricevuto dal classificatore contiene i turni sul meteo.
  - `test_in_ambito_dopo_rifiuti`: due turni rifiutati, poi `conversazione` → l'agente viene chiamato e i messaggi che riceve contengono i due rifiuti; il prompt del Router contiene i turni rifiutati.
  - `test_errore_del_server_nel_router` (parametri `openai.APIConnectionError(request=httpx.Request("POST", "http://x"))` e `openai.APITimeoutError(request=…)`): `esegui_turno` restituisce un testo che inizia con «Non riesco a ottenere una risposta dal server», la cronologia invariata, e `modello.chiamate == []`.
  - `test_rifiuto_con_max_passaggi_2`: rifiuto completato, `modello.chiamate == []`.
  - `test_rifiuto_con_max_passaggi_1_fissa_il_limite`: testo del limite («non è stata completata»), cronologia invariata, agente non chiamato. Il comportamento è fissato e documentato; se LangGraph si comporta diversamente da quanto dedotto nella spec §9, ci si ferma e lo si analizza.
  - `test_limite_superato_con_router_conserva_la_cronologia`: `ModelloSimulato([CHIEDE_ORA], ripeti_ultima=True)`, `in_ambito()`, limite 6, cronologia precedente non vuota → restituita invariata.
- [ ] **Step 2:** i nuovi test FALLISCONO.
- [ ] **Step 3:** implementare `crea_nodo_router`, le modifiche a `grafo.py` e a `terminale.py` e le aggiunte a `finti.py`.
- [ ] **Step 4: adattare i test esistenti.**
  - Ogni `costruisci_grafo(m, s)` diventa `costruisci_grafo(m, s, classificatore=in_ambito(), ambito=AMBITO_TEST)`.
  - I test di `main` sostituiscono anche `terminale.crea_classificatore` con `lambda config: in_ambito()`.
  - **Nessuna asserzione cambia.** In particolare `test_caratterizza_il_limite_di_passaggi` mantiene `[(2, 1, 1), (6, 3, 3)]`.
- [ ] **Step 5:** suite completa → verde. Se la caratterizzazione cambia valori, **non** si tocca il limite: ci si ferma, si analizza e lo si riferisce all'utente.
- [ ] **Step 6:** commit `feat(grafo): aggiunge il Router di ambito e il nodo di rifiuto`.

---

## Task 5 — Fail-open, eccezioni impreviste e dati minimi nei log (spec §8, §11)

**Files:** Modify `src/assistente/router.py`; Test `tests/test_router.py`.

**Interfaces — Produces** (in `router.py`):
- `MAX_MOTIVO_LOG = 120`.
- `motivo_per_log(motivo: str) -> str`: spazi e a capo compressi in un singolo spazio, poi troncamento a 120 caratteri.
- Nel nodo (emendamento spec §8): `classificatore.invoke(...)` è racchiuso in `try/except pydantic.ValidationError` (solo quella eccezione, solo attorno a quella chiamata). Sia quel caso sia `parsing_error` non nullo o `parsed` nullo restituiscono `{"categoria": "conversazione", "motivo": f"classificazione non riuscita: {type(errore).__name__}"}` (oppure `"output vuoto"` se manca l'errore) e si scrive il `WARNING` del §11. Il dettaglio diagnostico consentito è soltanto: il nome del tipo di errore e, per una `pydantic.ValidationError`, l'elenco dei campi non validi (`loc`). Mai `str(errore)`, che può contenere l'input.

- [ ] **Step 1: test che falliscono:**
  - `test_output_non_valido_inoltra_all_agente`: esito `{"raw": AIMessage('{"categoria": "boh"}'), "parsed": None, "parsing_error": <ValidationError reale ottenuta validando quel JSON>}` → l'agente viene chiamato; `WARNING` con `classificazione non valida`, `ValidationError`, `categoria`, `inoltro all'agente`; nessun log `INFO` di classificazione riuscita.
  - `test_validation_error_del_classificatore_inoltra_all_agente`: il `ClassificatoreSimulato` lancia una `pydantic.ValidationError` reale → fail-open come sopra.
  - `test_client_reale_con_output_non_valido_inoltra_all_agente` (parametri: categoria `"boh"`, motivo vuoto, testo non JSON, contenuto vuoto, risposta troncata con `finish_reason="length"`): `crea_classificatore` con `crea_client_router` reso testabile tramite un `httpx.Client(transport=httpx.MockTransport(...))` che restituisce quel contenuto (nessuna rete) → l'agente simulato viene chiamato, compare il `WARNING`, nel log non c'è il contenuto restituito. Caso valido di controllo: `fuori_ambito` → rifiuto.
  - `test_output_vuoto_inoltra_all_agente`: `parsed=None`, `parsing_error=None` → inoltro e `WARNING` con `output vuoto`.
  - `test_log_del_router_senza_dati_superflui`: domanda `"Mi chiamo Mario Rossi, che ore sono?"` e risposta grezza riconoscibile; nessuna riga di `assistente.router`, sia nel caso riuscito sia nel fail-open, contiene la domanda, `"Mario Rossi"`, il testo grezzo o `"TURNI PRECEDENTI"`.
  - `test_motivo_nel_log_breve_e_su_una_riga` (Focus 4): motivo di 300 caratteri con `"\n"` → nel log una sola riga, il motivo è lungo al massimo 120 caratteri; nello stato resta il motivo completo.
  - `test_eccezione_imprevista_non_viene_nascosta`: un classificatore che lancia `RuntimeError("bug")` → `esegui_turno` lascia propagare `RuntimeError`.
- [ ] **Step 2:** FALLISCONO (almeno i primi quattro).
- [ ] **Step 3:** implementare.
- [ ] **Step 4:** suite completa verde. Controllare con `Select-String -Path src\assistente\router.py,src\assistente\grafo.py -Pattern "except Exception"` che non ci siano risultati.
- [ ] **Step 5:** commit `feat(router): inoltra all'agente se la classificazione non è valida`.

---

## Task 6 — Documentazione (spec §4.1, §5, §11, §13)

**Files:** Modify `README.md`.

- [ ] **Step 1:** nel comando che carica `.env` aggiungere `-Encoding UTF8` a `Get-Content`. Prima di scriverlo, eseguirlo in PowerShell 5.1 e controllare che `$env:AMBITO_AGENTE` contenga «attività» corretta.
- [ ] **Step 2:** tabella delle variabili: riga `AMBITO_AGENTE` (obbligatoria, una riga, al massimo 500 caratteri, usata dal Router e nel rifiuto). Nota per chi aggiorna: senza la riga il programma non parte.
- [ ] **Step 3:** sezione «Router di ambito», con:
  - lo schema del grafo;
  - le categorie;
  - il comportamento tollerante;
  - le continuazioni (ultimi 2 turni);
  - il rifiuto fisso;
  - la cronologia;
  - il fail-open per output non valido;
  - gli errori del server;
  - il limite di passaggi (`MAX_PASSAGGI` resta dell'agente, il Router è compensato);
  - i log con un esempio;
  - la frase esplicita: **«Il Router è un filtro di pertinenza, non un meccanismo di sicurezza.»**
  Aggiornare anche la «Struttura» con `router`.
- [ ] **Step 4:** «Limitazioni note»: latenza del Router, con i valori misurati dallo spike e la promessa di aggiornarli in T7; il motivo nei log è testo generato, solo mitigato.
- [ ] **Step 5:** commit `docs: documenta il Router di ambito e AMBITO_AGENTE`.

---

## Task 7 — Prove reali con LM Studio e Docker (spec §13)

Le prove le esegue a mano chi implementa, con l'utente se serve. Ogni esito va in `prove_reali/PROVE.md`, sotto una nuova sezione «Ramo `feat/router` — Step 1 Lezione 6 (data)», separata dai test simulati. Per ogni prova si annotano domanda, categoria, motivo, `durata`, presenza o assenza delle righe `agente:` e `strumento richiesto`.

- [ ] **Step 1:** verificare il modello con `prove_reali\verifica_modelli.py`, dopo aver caricato `.env` con il comando aggiornato.
- [ ] **Step 2 (locale, servizio HTTP e server MCP attivi):** prove §13 numeri 1–7 e 8bis, in una sessione.
- [ ] **Step 3:** prova §13.8: LM Studio fermato durante la sessione, poi una domanda → messaggio di errore del server, cronologia invariata (verificata con una domanda di continuazione dopo il riavvio).
- [ ] **Step 4 (Docker):** `docker compose build`, poi `docker compose run --rm assistente`: almeno una domanda in ambito con strumento e una fuori ambito, con i log. Poi `AMBITO_AGENTE` tolta temporaneamente da `.env` → errore di configurazione e codice 1; poi ripristinarla.
- [ ] **Step 5:** riepilogo delle latenze (minimo, massimo, mediana delle `durata`) in `PROVE.md`; aggiornare i valori nel README («Limitazioni note»). Annotare ogni classificazione sbagliata come tale, senza riformulare le domande per ottenere l'esito atteso.
- [ ] **Step 6:** commit `docs: registra le prove reali del Router di ambito` (`PROVE.md` e `README.md`).

---

## Task 8 — Verifica finale, review, merge (CLAUDE.md «Git»)

- [ ] **Step 1:** suite completa verde (riportare il numero di test); `git status` pulito; `git diff dev --stat` limitato ai file della tabella «Struttura dei file».
- [ ] **Step 2:** controllo dei criteri di accettazione della spec §14, uno per riga, ciascuno con la prova (test o voce di `PROVE.md`).
- [ ] **Step 3:** review indipendente con `superpowers:requesting-code-review` sul diff `dev...feat/router`, con spec e piano come riferimento. Valutare i rilievi con `superpowers:receiving-code-review`. Ogni correzione segue TDD e diventa un commit separato.
- [ ] **Step 4:** proporre all'utente l'aggiornamento di `CLAUDE.md` (riga «Struttura»: `router` (Router di ambito, contesto e rifiuto)). Solo dopo la sua autorizzazione: modifica e commit `docs: aggiorna CLAUDE.md con il modulo router`.
- [ ] **Step 5:** **fermarsi** e presentare all'utente il resoconto: cosa è stato eseguito, con quale esito, cosa resta da provare, i rilievi della review. Attendere l'approvazione esplicita del merge.
- [ ] **Step 6:** solo dopo l'approvazione: `git switch dev; git merge --no-ff feat/router -m "Merge branch 'feat/router' into dev"`; suite completa verde su `dev`; `git branch -d feat/router`. Nessun push, nessun merge su `main`.
