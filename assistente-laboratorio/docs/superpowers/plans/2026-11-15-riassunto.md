# Lezione 6, Step 3 — Riassunto della cronologia: piano di implementazione

> **Per gli esecutori:** SOTTO-SKILL RICHIESTA: `superpowers:executing-plans` (nativa) oppure `superpowers:subagent-driven-development`, secondo la scelta dell'utente. I passi usano la sintassi a caselle (`- [ ]`). Leggere la specifica per intero prima di iniziare.

**Obiettivo:** aggiungere all'inizio di ogni turno un nodo Riassunto. Oltre `SOGLIA_RIASSUNTO` messaggi il nodo sostituisce i turni più vecchi con un riassunto aggiornato nel campo `riassunto` dello stato e conserva gli ultimi 2 turni completi. Il riassunto arriva poi a Router, agente e Revisore.

**Architettura:**
- Il grafo diventa `START → riassunto → router → (modello ⇄ strumenti → revisore ⇄ modello | rifiuto) → END`.
- Il modulo nuovo `riassunto.py` contiene costanti, segmentazione dei turni, trascrizione, prompt (v4), cornice dell'agente e nodo con fail-open.
- Il riassuntore è un `ChatOpenAI` separato, senza strumenti né output strutturato, iniettato nel grafo come il classificatore del Router.
- Nel terminale, messaggi e riassunto viaggiano insieme in una `Sessione` immutabile. `esegui_turno` passa al grafo copie dei messaggi e, se il turno fallisce, restituisce la sessione ricevuta.

**Stack:** Python 3.13, `langgraph==1.2.19`, `langchain-openai==1.7.3`, pytest. Nessuna dipendenza nuova.

**Specifica:** `docs/superpowers/specs/2026-11-15-riassunto-design.md`, approvata dall'utente il 2026-11-15 insieme alle cinque scelte confermate dopo la review e alla correzione D1. È vincolante: i riferimenti §n di ogni task rimandano lì.

**Stato del piano:** approvato dall'utente il 2026-11-15 dopo la review indipendente. T0 è eseguito nella sessione di preparazione; l'esecuzione riprende da T1 in una nuova sessione (vedi `docs/superpowers/handoffs/2026-11-15-riassunto-implementazione-handoff.md`).

## Vincoli globali

- **Solo lo Step 3.** Esclusi:
  - memoria persistente tra esecuzioni;
  - stima o conteggio dei token;
  - revisioni dei prompt di Router, Revisore o riassuntore oltre a quanto previsto dalla specifica (prompt v4 e cornici B.1/B.2 **testo esatto**);
  - primitive MCP, servizio HTTP dell'agente, back-end, front-end, Compose per componente;
  - modifiche a `compose.yaml`.
- **Riassuntore:** client separato **senza `bind_tools`**, stesso `base_url` e modello, `temperature=0`, `reasoning_effort="none"`, `max_tokens=768`. Prompt in un unico `HumanMessage`: `ISTRUZIONI` = **Appendice A, testo esatto**, copiato dal file della specifica e mai riscritto a memoria.
- **Costanti** (spec §6.4): `TURNI_CONSERVATI = 2`, `MAX_TOKENS_RIASSUNTO = 768`, `MAX_RISULTATO_TRASCRITTO = 1000`. **`SOGLIA_RIASSUNTO`**: predefinito 20, intero positivo.
- **Condizioni** (§6.2): chiamata solo se `len(messages) > soglia` **e** c'è almeno un turno completo oltre gli ultimi 2. Si contano tutti i messaggi dello stato.
- **Taglio** (§6.3): sempre all'indice di una domanda reale (`HumanMessage` non osservazione). Restano gli ultimi 2 turni completi più la domanda attuale.
- **Aggiornamento atomico** (§8): prima si valida il nuovo riassunto, poi si restituiscono insieme `riassunto` e i `RemoveMessage(id=...)`. Con un errore atteso: aggiornamento vuoto `{}`, WARNING, turno che prosegue.
- **Ordine delle eccezioni** (§8): `openai.LengthFinishReasonError` (solo difensiva) prima di `openai.OpenAIError`. Poi, sulla risposta, testo vuoto o di soli spazi e `response_metadata["finish_reason"] == "length"`. Non si intercetta `ValidationError`. Si intercetta solo attorno a `invoke`; trascrizione e prompt restano fuori dal `try`. Niente `except Exception`, niente retry.
- **Log** (§10): logger `assistente.riassunto`. Nel WARNING solo `type(errore).__name__` oppure l'etichetta `vuoto` / `troncato (finish_reason=length)`, più la durata. Mai `str(errore)`, `repr(errore)`, testi dell'utente, degli strumenti, del riassunto o del modello.
- **Sessione** (§5): `@dataclass(frozen=True)`, `messaggi: tuple[BaseMessage, ...] = ()`, `riassunto: str = ""`. `esegui_turno` passa **sempre** `riassunto` e **copie** dei messaggi (`model_copy()`). Se il turno fallisce restituisce **lo stesso oggetto** ricevuto.
- **Riassunto vuoto** (§9.4): prompt di Router e Revisore e richiesta all'agente **identici** a quelli dello Step 2.
- **Limite di passaggi** (§11): `recursion_limit = PASSAGGI_RIASSUNTO + PASSAGGI_ROUTER + (max_revisioni + 1) × (max_passaggi + PASSAGGI_REVISORE)`, tutte le costanti = 1. **Mai cambiare un'asserzione per far passare un test**: un valore misurato diverso dalla previsione va fermato, analizzato e riferito all'utente.
- **Test** senza rete né modello; client reale con `httpx.MockTransport` ammesso. Prove reali separate, in `prove_reali/PROVE.md`. Le prove con le note usano un database temporaneo (`NOTE_DB_PATH`) e si fanno solo in locale.
- **Git** (CLAUDE.md):
  - ramo `feat/riassunto` da `dev`; Conventional Commits in italiano;
  - prima di ogni commit `git status`, diff e staging selettivo: mai `.env`, `../LLM_Lez_6.pdf`, cache, `data/`;
  - ogni messaggio termina con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
  - review indipendente e **approvazione esplicita dell'utente** prima di `git merge --no-ff`; nessun push, nessun merge su `main`.
- **Comandi** da `assistente-laboratorio/` in PowerShell. Test: `.\.venv\Scripts\python.exe -m pytest -v`. Base di partenza: **543 test verdi**.
- **Import nei test:** il modulo si importa con un alias (`import assistente.riassunto as modulo_riassunto`), come `modulo_revisore`.

## Previsioni da misurare (non da adattare)

| # | Previsione | Fonte | Task |
|---|---|---|---|
| M1 | Caratterizzazione del ciclo di strumenti invariata: `(2,1)→3/3`, `(6,1)→7/7`, `(2,0)→2/1`, `(6,0)→4/3`, perché il passaggio in più compensa il nuovo nodo. **Il nodo e la formula vanno introdotti nello stesso task**: con il solo nodo, la review del piano ha misurato 8 fallimenti | spec §11, review della specifica e del piano (prototipo) | T5 |
| M2 | `limite_ricorsione(6,1), (6,0), (1,1)` = `(16, 9, 6)`, al posto di `(15, 8, 5)` | spec §11 | T5 |
| M3 | Valori piccoli invariati; nei test di `test_revisore.py` gli esiti «riuscito / interrotto» restano, ma i turni durano un passaggio in più: 14 e 16 invece di 13 e 15. Con il limite 16 il massimo è 15 e un turno con giudizio finale usa un numero **pari** di passaggi. Le asserzioni non cambiano; vanno corretti solo i commenti e i nomi diventati falsi | spec §11, review del piano | T5 |
| M4 | Il rifiuto usa 3 passaggi (Riassunto, Router, rifiuto) e si completa con qualunque valore (`test_router.py::test_rifiuto_con_max_passaggi_1_e_zero_revisioni_si_completa`, limite 4) | spec §11 | T5 |
| M5 | Con le copie dei messaggi falliscono **solo** queste 3 asserzioni, che confrontano oggetti della cronologia precedente con quelli di un turno **riuscito**: le copie hanno un `id` assegnato, gli originali no. Le asserzioni `cronologia == precedente` dei turni **falliti** restano vere, perché la sessione restituita è la stessa. <br>• `tests/test_router.py:226` `assert cronologia[:2] == precedente`<br>• `tests/test_router.py:314` `assert cronologia[:2] == precedente and len(cronologia) == 4`<br>• `tests/test_revisore.py:676` `assert cronologia[:2] == precedente and ...`, in un test parametrizzato 2×2, quindi **4 casi**<br>In tutto **6 casi falliti**, confermati dal prototipo della review del piano | spec §5.3 | T6 |
| M6 | Nel payload HTTP del riassuntore `max_tokens` diventa `max_completion_tokens: 768` (langchain-openai 1.7.3, `base.py:3845`); `reasoning_effort: "none"`, `temperature: 0` (serializzato come `0.0`); nessuna chiave `tools`. Confermato dalla review del piano | review della specifica e del piano | T3 |
| M7 | Una risposta HTTP reale con `finish_reason: "length"` arriva in `AIMessage.response_metadata["finish_reason"] == "length"` senza eccezioni. Confermato dalla review del piano | review della specifica e del piano | T3 |

**Correzione D1, approvata dall'utente il 2026-11-15 e riportata nella specifica §5.3.** La review del piano ha mostrato con un prototipo che il test 2 sugli `id`, quello sul caso realistico, **non può fallire**: i messaggi di una sessione uscita da un turno hanno già un `id`, e `RemoveMessage` non modifica gli oggetti. Il piano tratta quindi:
- il test 1 (sessione senza `id`) come test TDD: deve fallire senza copie (T6, Step 3a);
- il test 2 come test di regressione.

**Regola per M5.** Il significato del test è «i messaggi precedenti restano»; ora si confronta per tipo e contenuto (`[(type(m), m.content) for m in ...]`), non per identità dell'oggetto. È un adattamento imposto dalla decisione sulle copie, approvata dall'utente. Se falliscono test **diversi** da questi 3, ci si ferma.

## Focus della review

Casi che la specifica implica ma che i test esistenti non coprono, i più probabili nell'uso reale. Ognuno ha un test nel task indicato.

1. **Turno precedente con correzione del Revisore**, quindi con bozza e osservazione, che esce con la compressione. Il taglio resta alla domanda reale, bozza e osservazione non compaiono nella trascrizione ma contano per la soglia (T2, T4).
2. **Più chiamate allo stesso strumento** con `ToolMessage` in ordine invertito: abbinamento per `tool_call_id`, nessuna associazione inventata (T2).
3. **Seconda compressione:** il riassunto precedente è nel prompt e il nuovo lo sostituisce. Una compressione fallita lascia intatto quello precedente (T4, T6).
4. **Domanda dell'utente con graffe o contenuto a blocchi** (`{turni}`, lista di blocchi): la composizione non fallisce e usa `.text` (T2).
5. **Soglia molto bassa** (`SOGLIA_RIASSUNTO=1`) con turni lunghi: compressione a ogni turno finché ci sono turni eliminabili, mai a vuoto (caso A1) (T4).

## Struttura dei file

| File | Responsabilità | Task |
|---|---|---|
| `src/assistente/config.py`, `.env.example` | `SOGLIA_RIASSUNTO` → `Config.soglia_riassunto` | T1 |
| `src/assistente/revisore.py` | `_bozza_scartata` resa pubblica come `e_bozza_scartata` (refactoring senza cambi); `componi_prompt(..., riassunto="")` | T2, T7 |
| `src/assistente/riassunto.py` (nuovo) | costanti, `ISTRUZIONI`, `CORNICE_AGENTE`, `inizi_turni`, `indice_taglio`, `trascrivi_turni`, `componi_prompt`, `crea_nodo_riassunto` | T2, T4 |
| `src/assistente/modello.py` | `crea_riassuntore` | T3 |
| `src/assistente/router.py` | `riassunto_presente`, `sezione_riassunto` (testo B.2), segnaposto `{sezione_riassunto}` nel template; `componi_prompt(..., riassunto="")`; il nodo legge `stato.get("riassunto", "")` | T7 |
| `src/assistente/grafo.py` | `Stato.riassunto`; nodo `riassunto`; `costruisci_grafo(..., riassuntore, soglia_riassunto)`; `SystemMessage` nell'agente | T5, T7 |
| `src/assistente/terminale.py` | `PASSAGGI_RIASSUNTO`, formula, `main` (T5); `Sessione`, `esegui_turno` con sessione e copie, `esegui_chat` con firma invariata (T6) | T5, T6 |
| `tests/finti.py` | `RiassuntoreSimulato`, `riassuntore_inerte()` | T4, T5 |
| `tests/test_riassunto.py` (nuovo) | test dello Step 3 | T2–T7 |
| test esistenti | adattamenti meccanici (T5, T6) e i cambiamenti M2/M5 | T5, T6 |
| `README.md`, `prove_reali/PROVE.md` | documentazione e prove | T8, T9 |
| `CLAUDE.md` | riga «Struttura» con `riassunto` (solo con autorizzazione) | T10 |

---

## Task 0 — Specifica e piano su `dev` (solo con autorizzazione)

- [ ] **Step 1:** chiedere all'utente l'autorizzazione al commit di specifica e piano. Senza autorizzazione ci si ferma qui.
- [ ] **Step 2:** cambiare la riga «Stato» della specifica in «approvata il 2026-11-15». È l'unica modifica alla specifica.
- [ ] **Step 3:** `git switch dev; git status`. Devono comparire solo i due file in `docs/superpowers/` e `../LLM_Lez_6.pdf`, da non aggiungere.
- [ ] **Step 4:** `git add` di specifica e piano; commit `docs: aggiunge specifica e piano del riassunto della cronologia`.
- [ ] **Step 5:** `git switch -c feat/riassunto`. Suite completa: **543 verdi**.

---

## Task 1 — Configurazione `SOGLIA_RIASSUNTO` (spec §6.4)

**Files:** Modify `src/assistente/config.py`, `.env.example`, `tests/test_config.py`.

**Interfaces — Produces:** `SOGLIA_RIASSUNTO_PREDEFINITA = 20`; `Config.soglia_riassunto: int = SOGLIA_RIASSUNTO_PREDEFINITA`, con predefinito, dopo `max_revisioni`. Così `test_config_valida` resta invariato.

- [ ] **Step 1: test che falliscono** in `tests/test_config.py`:
  - `test_soglia_riassunto_predefinita`: valore assente, `""` o `"   "` → `20`;
  - `test_soglia_riassunto_valori_validi`: `"1"` → `1`, `" 6 "` → `6`;
  - `test_soglia_riassunto_non_valida`: parametri `"0"`, `"-3"`, `"2.5"`, `"venti"` → `ErroreConfigurazione` il cui messaggio contiene `"SOGLIA_RIASSUNTO"` e il valore ricevuto.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_config.py -v` → i nuovi test FALLISCONO.
- [ ] **Step 3:** implementare in `carica_config`, come `_max_revisioni`. Messaggio: `f"SOGLIA_RIASSUNTO deve essere un intero positivo, ricevuto: {grezzo!r}"`.
- [ ] **Step 4:** `.env.example`: dopo `#MAX_REVISIONI=1` aggiungere un commento («Messaggi oltre i quali i turni più vecchi vengono riassunti; si conservano sempre gli ultimi 2 turni») e `#SOGLIA_RIASSUNTO=20`.
- [ ] **Step 5:** suite completa verde. Commit `feat(config): aggiunge la variabile SOGLIA_RIASSUNTO`.

---

## Task 2 — Funzioni pure del riassunto (spec §6.1–§6.3, §7.1–§7.2, Appendice A)

**Files:** Create `src/assistente/riassunto.py`, `tests/test_riassunto.py`; Modify `src/assistente/revisore.py` (solo la ridenominazione).

**Interfaces — Consumes:** `router.e_osservazione`, `router.testo_rifiuto`, `revisore.e_bozza_scartata`.

**Interfaces — Produces** (in `riassunto.py`):
- costanti `TURNI_CONSERVATI = 2`, `MAX_TOKENS_RIASSUNTO = 768`, `MAX_RISULTATO_TRASCRITTO = 1000`;
- `ISTRUZIONI: str`, l'Appendice A **copiata dal file della specifica** con uno script che estrae il blocco `text`, non a mano;
- `inizi_turni(messaggi: Sequence[BaseMessage]) -> list[int]`: indici delle domande reali, in ordine;
- `indice_taglio(messaggi: Sequence[BaseMessage], turni_conservati: int = TURNI_CONSERVATI) -> int`: indice del primo messaggio da conservare, cioè l'inizio del turno che apre gli ultimi `turni_conservati` turni completi prima della domanda attuale. Vale `0` se non ci sono turni eliminabili. La domanda attuale è l'ultimo `inizi_turni`; i messaggi prima della prima domanda reale appartengono al primo turno (§6.3);
- `trascrivi_turni(messaggi: Sequence[BaseMessage], ambito: str) -> str`: formato del §7.2, ordine cronologico, intestazioni `Turno k`, risultato subito sotto la chiamata con lo stesso `tool_call_id`;
- `componi_prompt(riassunto_precedente: str, messaggi_da_togliere: Sequence[BaseMessage], ambito: str) -> str`: `ISTRUZIONI.format(riassunto=riassunto_precedente or "(nessuno)", turni=trascrivi_turni(...))`.

- [ ] **Step 1: ridenominazione** di `revisore._bozza_scartata` in `e_bozza_scartata`, pubblica e con la stessa firma, aggiornando l'unico uso interno. Suite verde: nessun test la usa direttamente.
- [ ] **Step 2: test che falliscono** in `tests/test_riassunto.py`.

  **Segmentazione e taglio**
  - `inizi_turni` salta le osservazioni: `[H, AI, H, AI(bozza), Oss, AI, H]` → `[0, 2, 6]`.
  - `indice_taglio` per 3 turni completi più la domanda → l'inizio del 2° turno.
  - Con 2 o meno turni completi → `0`.
  - Con `turni_conservati=0` → l'indice della domanda attuale.

  **Coppie degli strumenti**
  - `test_taglio_non_separa_coppie_strumento`: un turno con `AIMessage(tool_calls=[a, b])` e due `ToolMessage` resta tutto da una parte del taglio.

  **Trascrizione: formato**
  - Esempio esatto di un turno semplice:
    ```
    Turno 1
    Utente: Ciao
    Assistente: Salve
    ```
  - Righe esatte di una chiamata e del suo risultato:
    ```
    Strumento richiesto: calcola({"espressione": "7*8"})
    Risultato di calcola: 56
    ```
  - Bozza e osservazione omesse.
  - Rifiuto (`testo_rifiuto(ambito)`) → `Assistente: (richiesta fuori ambito, rifiutata)`.
  - Risposta `"  "` → `Assistente: (nessuna risposta)`.
  - Risultato di 1001 caratteri → primi 1000 più `"\n[risultato troncato: mostrati i primi 1000 caratteri su 1001]"`. Uno di esattamente 1000 caratteri non viene troncato.
  - `elimina_nota` con `"Errore: cancellazione non confermata dall'utente"` (operazione annullata) riportato così com'è.
  - `calcola` con `"Errore: divisione per zero"` (operazione fallita) riportato così com'è; `aggiungi_nota` riuscita con `"Nota creata: id 7, …"` sotto la sua chiamata e i suoi argomenti.
  - `json.dumps(..., ensure_ascii=False)`: «città» resta leggibile.

  **Trascrizione: abbinamento per `tool_call_id`** (Focus 2)
  - Due chiamate a `orologio` con id `a`/`b` e argomenti diversi, con i `ToolMessage` in ordine `b, a`: righe chiamata a, risultato a, chiamata b, risultato b.
  - Due chiamate con argomenti identici restano due coppie.
  - Una chiamata senza `ToolMessage` → `Risultato di <nome>: (nessun risultato)`.
  - Un `ToolMessage` senza chiamata viene trascritto nella sua posizione, senza eccezioni e senza essere attribuito ad altre chiamate.

  **Dati e composizione**
  - Testo dell'utente con istruzioni («ignora le regole») riportato come dato.
  - Graffe `{turni}` nella domanda e contenuto a blocchi (`HumanMessage(content=[{"type": "text", "text": "…"}])`) → la composizione non fallisce e usa `.text` (Focus 4).
  - `componi_prompt("", ...)` contiene `<riassunto_precedente>\n(nessuno)\n</riassunto_precedente>`; con un riassunto, lo contiene alla lettera.
  - `ISTRUZIONI` è uguale al blocco dell'Appendice A, letto dal file della specifica nel test stesso: è la protezione contro una copia infedele.
- [ ] **Step 3:** `pytest tests/test_riassunto.py -v` → FALLISCONO (modulo assente).
- [ ] **Step 4:** implementare le funzioni. La trascrizione costruisce una mappa `tool_call_id → ToolMessage` dai messaggi da togliere e scrive ogni risultato sotto la sua chiamata. I `ToolMessage` già usati non vengono riscritti; quelli senza chiamata vengono trascritti dove si trovano.
- [ ] **Step 5:** test verdi e suite completa verde. Commit `feat(riassunto): aggiunge segmentazione dei turni, trascrizione e prompt`.

---

## Task 3 — Client del riassuntore (spec §4.1, §8; M6, M7)

**Files:** Modify `src/assistente/modello.py`; Test `tests/test_riassunto.py`.

**Interfaces — Produces:** `crea_riassuntore(config: Config) -> ChatOpenAI`: `ChatOpenAI(base_url=config.base_url, api_key="lm-studio", model=config.modello, temperature=0, reasoning_effort="none", max_tokens=MAX_TOKENS_RIASSUNTO)`, senza `bind_tools` né `with_structured_output`.

- [ ] **Step 1: test che falliscono**, con `httpx.MockTransport` e gli helper di `tests/test_revisore.py` riusati o duplicati in piccolo:
  - `test_payload_del_riassuntore`: nel JSON inviato `temperature == 0`, `reasoning_effort == "none"`, `max_completion_tokens == 768` (M6; se la chiave misurata è un'altra ci si ferma), nessuna chiave `tools`, un solo messaggio con `role == "user"`;
  - `test_finish_reason_length_arriva_nei_metadati`: risposta `finish_reason: "length"` → `invoke` restituisce un `AIMessage` con `response_metadata["finish_reason"] == "length"`, senza eccezioni (M7);
  - `test_finish_reason_stop`: `"stop"` → testo restituito.
- [ ] **Step 2:** FALLISCONO (`crea_riassuntore` assente).
- [ ] **Step 3:** implementare.
- [ ] **Step 4:** verdi; suite verde. Commit `feat(modello): aggiunge il client del riassuntore`.

---

## Task 4 — Nodo Riassunto, fail-open e log (spec §6.2, §8, §10)

**Files:** Modify `src/assistente/riassunto.py`, `tests/finti.py`; Test `tests/test_riassunto.py`.

**Interfaces — Produces:**
- `crea_nodo_riassunto(riassuntore, soglia: int, ambito: str) -> Callable[[dict], dict]`. Il nodo:
  - legge `stato["messages"]` e `stato.get("riassunto", "")`;
  - restituisce `{}` quando non comprime;
  - quando comprime restituisce `{"riassunto": nuovo, "messages": [RemoveMessage(id=m.id) for m in tolti]}`;
- in `tests/finti.py`:
  - `RiassuntoreSimulato(risposte, ripeti_ultima=False)`: come `ModelloSimulato` (registra `chiamate`, solleva le eccezioni). Le risposte sono `AIMessage` con `response_metadata={"finish_reason": ...}`;
  - helper `riassunto_ok(testo)` e `riassunto_troncato(testo)`;
  - `riassuntore_inerte()`: un `RiassuntoreSimulato([])`, che solleva `AssertionError("riassuntore chiamato")` se invocato.

Nei test il nodo si invoca direttamente con uno stato di messaggi **con `id`**.

- [ ] **Step 1: test che falliscono.**

  **Condizioni**
  - Messaggi uguali alla soglia → `{}` e 0 chiamate; INFO «soglia non superata».
  - Soglia superata con 2 turni completi più la domanda → `{}` e 0 chiamate; INFO «nessun turno eliminabile».
  - Soglia superata con 3 turni → 1 chiamata. I `RemoveMessage` riguardano esattamente i messaggi del 1° turno, `riassunto` è il testo restituito, INFO con `messaggi N → M`.

  **Conteggio e taglio**
  - Bozza e osservazione contano per la soglia; un turno rifiutato conta come turno.
  - `test_turno_corretto_esce_intero`: il 1° turno con bozza e osservazione viene tolto per intero, e nella trascrizione inviata non compaiono né la bozza né l'osservazione (Focus 1).
  - `test_soglia_minima_comprime_solo_se_eliminabile` (Focus 5): soglia 1.
    - Con 2 turni più la domanda, nessuna chiamata.
    - Con 3 turni, una chiamata che lascia 2 turni più la domanda.
    - Applicando di nuovo il nodo allo stato risultante, nessuna chiamata.

  **Aggiornamento del riassunto**
  - Il riassunto precedente compare nel prompt inviato.
  - Il nuovo riassunto lo sostituisce, non vi si aggiunge.

  **Fail-open:** un test parametrizzato con i casi:
  - `openai.APIConnectionError`;
  - `openai.APITimeoutError`;
  - `openai.LengthFinishReasonError`, che serve solo a verificare l'ordine delle eccezioni (va intercettato prima di `OpenAIError`, con etichetta propria);
  - `riassunto_ok("")`;
  - `riassunto_ok("   \n")`;
  - `riassunto_troncato("Obiettivo: ...")`;
  - `riassunto_troncato("")`, vuoto **e** troncato insieme: vince l'etichetta `troncato (finish_reason=length)`, perché `finish_reason` si controlla per primo.

  **Costruzione delle eccezioni nei test** (verificata dalla review del piano):
  - `openai.APIConnectionError(request=httpx.Request("POST", URL))`;
  - `openai.APITimeoutError(request=…)`;
  - `openai.APIStatusError("…", response=httpx.Response(500, json=…, request=httpx.Request("POST", URL)), body=…)`: senza `request` la risposta solleva `RuntimeError`;
  - `openai.LengthFinishReasonError(completion=…)`, con l'argomento keyword obbligatorio.

  In tutti i casi il nodo restituisce `{}`: nessun `RemoveMessage` e nessun `riassunto`. C'è un solo WARNING con il nome della classe oppure l'etichetta `vuoto` / `troncato (finish_reason=length)`.

  **Errori imprevisti**
  - `RuntimeError` dal riassuntore → si propaga.
  - Un errore nella trascrizione, per esempio provocato con `monkeypatch` su `modulo_riassunto.trascrivi_turni`, si propaga senza chiamare il riassuntore.

  **Log senza contenuti** (spec §12): un contrassegno univoco, come `«SEGRETO-…»`, va messo:
  - nella domanda;
  - in un risultato di strumento;
  - nel riassunto precedente;
  - nel testo restituito;
  - in un `openai.APIStatusError` costruito con `httpx.Response(500, json={"error": "SEGRETO-..."})`.

  Si esegue un caso per ciascuno: compressione, non attivazione, fail-open per errore e fail-open per output non valido. Nessun record di `assistente.riassunto` contiene il contrassegno, a nessun livello (`caplog.at_level(logging.DEBUG)`).
- [ ] **Step 2:** FALLISCONO.
- [ ] **Step 3:** implementare.
  - Ordine nel nodo:
    1. conteggio;
    2. taglio;
    3. prompt (fuori dal `try`);
    4. `invoke` dentro il `try`, con le due `except` nell'ordine dei vincoli globali;
    5. validazione della risposta: prima `response_metadata.get("finish_reason") == "length"`, poi il testo vuoto su `risposta.text.strip()`. Si usa `.text`, non `.content`, perché il contenuto può essere a blocchi;
    6. aggiornamento con `risposta.text`, salvato così com'è.
  - Durata misurata con `time.perf_counter()`.
  - Righe di log senza testi, con `router.diagnosi` riusabile per i tipi.
- [ ] **Step 4:** verdi; suite verde. Commit `feat(riassunto): aggiunge il nodo Riassunto con fail-open`.

---

## Task 5 — Nodo nel grafo e limite di passaggi (spec §4, §5.1, §11; M1–M4)

Nodo e formula entrano **insieme**. Con il solo nodo e il limite vecchio, la review del piano ha misurato 8 fallimenti: la caratterizzazione, i valori piccoli e il rifiuto con limite 3.

**Files:** Modify `src/assistente/grafo.py`, `src/assistente/terminale.py` (`PASSAGGI_RIASSUNTO`, `limite_ricorsione`, `main`); test esistenti (adattamento meccanico, M2 e commenti di M3); Test `tests/test_riassunto.py`.

**Interfaces — Produces:**
- `Stato.riassunto: NotRequired[str]`, senza reducer;
- `costruisci_grafo(modello, strumenti=(), *, classificatore, ambito, revisore, max_revisioni, riassuntore, soglia_riassunto)`;
- arco `START → "riassunto" → "router"`;
- in `terminale.py`: `PASSAGGI_RIASSUNTO = 1` e `limite_ricorsione(max_passaggi, max_revisioni) = PASSAGGI_RIASSUNTO + PASSAGGI_ROUTER + (max_revisioni + 1) × (max_passaggi + PASSAGGI_REVISORE)`.

- [ ] **Step 1: test che falliscono.**
  - Grafo invocato direttamente con 4 turni più la domanda, soglia 6 e `RiassuntoreSimulato`:
    - `esito["messages"]` contiene solo gli ultimi 2 turni e la domanda;
    - `esito["riassunto"]` è il testo simulato;
    - il classificatore del Router ha ricevuto un prompt la cui `DOMANDA ATTUALE` è la domanda nuova;
    - `esito["inizio_turno"]` è l'indice della domanda nuova **nella lista compressa** (`esito["messages"][esito["inizio_turno"]].content` è la domanda nuova);
    - i messaggi ricevuti dal modello finiscono con la domanda nuova, preceduta dai 2 turni conservati.
  - Sotto la soglia: `riassuntore_inerte()` non viene chiamato, lo stato non ha la chiave `riassunto` oppure la ha vuota, e `messages` è completo.
  - Invocazione senza `riassunto` nell'input: nessuna `KeyError` (§5.1).
  - **Fail-open a livello di grafo** (review del piano, I4): un riassuntore che solleva `openai.APIConnectionError` con soglia superata. Il grafo arriva alla risposta dell'agente; `messages` non è compresso; c'è un WARNING di `assistente.riassunto`; il `riassunto` in ingresso (`"R0"`) resta invariato nell'output.
- [ ] **Step 2:** FALLISCONO.
- [ ] **Step 3:** implementare nodo, parametri obbligatori e nuova formula. In `main`: `riassuntore=crea_riassuntore(config)` e `soglia_riassunto=config.soglia_riassunto`.
- [ ] **Step 4: adattamento meccanico** delle 13 righe di test che chiamano `costruisci_grafo(`, con `riassuntore=riassuntore_inerte(), soglia_riassunto=SOGLIA_RIASSUNTO_PREDEFINITA`.
  - File interessati: `test_grafo.py`, `test_instradamento.py`, `test_limite.py`, `test_revisore.py`, `test_router.py`, `test_terminale.py`, `test_mcp_client.py`, `test_calcolatrice.py`, `test_unita.py`. Dove esiste un helper (`grafo_in_loop`, `grafo_revisore`, `grafo(...)`, `esegui`), si modifica solo l'helper.
  - Il riassuntore inerte dimostra anche che sotto la soglia predefinita nessun test esistente lo chiama. La review del piano ha verificato che nessun test supera 9 messaggi.
- [ ] **Step 5: misure.** Suite completa. **Deve fallire solo `test_revisore.py::test_limite_ricorsione`** (M2). Ogni altro fallimento va **fermato**: si analizza e se ne parla all'utente. In particolare devono restare verdi senza cambiare le asserzioni:
  - la caratterizzazione (M1);
  - i valori piccoli e i casi «13/15» (M3);
  - il rifiuto con limite 4 (M4).
- [ ] **Step 6: cambiamenti attesi.**
  - **M2:** `(15, 8, 5)` → `(16, 9, 6)`, con commento «spec Step 3 §11: un passaggio per il Riassunto».
  - **Commenti e nomi diventati falsi per M3**, senza toccare le asserzioni:
    - `test_limite.py:69-71`;
    - `test_revisore.py` intorno a 441-444, 466, 471, 504-505, compreso il nome di `test_turno_di_13_passaggi…` se descrive i passaggi;
    - `test_router.py:302-303` e `:536-537`.
    
    I numeri nei commenti vanno ricontati sul codice, non presi da questo piano.
- [ ] **Step 7:** `git diff --stat tests/` mostra solo:
  - costruzione dei grafi;
  - M2;
  - commenti e nomi.
  
  Suite completa verde. Commit `feat(grafo): aggiunge il nodo Riassunto prima del Router`.

---

## Task 6 — Sessione e atomicità del turno (spec §5.2, §5.3; M5)

**Files:** Modify `src/assistente/terminale.py`; test esistenti (adattamento meccanico, M5); Test `tests/test_riassunto.py`.

**Interfaces — Produces** (in `terminale.py`):
- `Sessione` (vincoli globali);
- `esegui_turno(grafo, sessione: Sessione, domanda: str, max_passaggi: int, *, max_revisioni: int) -> tuple[Sessione, str]`;
- `esegui_chat`: firma **invariata**, ma internamente parte da `Sessione()`.

Per avere una compressione servono **almeno 3 turni completi** prima della domanda, più una soglia sotto il numero dei messaggi. I test di questo task costruiscono le sessioni di conseguenza.

- [ ] **Step 1: test che falliscono.**
  1. `test_sessione_immutabile`: assegnare un campo solleva `FrozenInstanceError`; `messaggi` è una `tuple`.
  2. **Copie e `id`** (spec §5.3, test 1):
     - `test_turno_riuscito_non_modifica_la_sessione_senza_id`: sessione costruita a mano con 3 turni completi (6 messaggi) e `id` tutti `None`, soglia 4. Il turno riuscito comprime. Dopo il turno i messaggi della sessione ricevuta hanno ancora `id is None` e lo stesso contenuto, e `sessione.riassunto` è invariato.
     - `test_turno_fallito_non_modifica_la_sessione_senza_id`: la stessa sessione, con un turno in `GraphRecursionError`. `esegui_turno` restituisce **lo stesso oggetto** (`is`), con gli `id` ancora `None`.
  3. `test_sessione_reale_dopo_compressione` (spec §5.3, test 2): 3 turni riusciti tramite `esegui_turno`, poi un 4° turno che comprime con soglia 6. La sessione uscita dal 3° turno conserva tutti i suoi messaggi, nello stesso numero e con gli stessi `id`, e il suo riassunto. Vedi D1: questo test non può fallire senza copie ed è un test di regressione.
  4. `test_compressione_poi_limite_di_passaggi` e `test_compressione_poi_errore_del_server`: sessione con 3 turni e soglia 4, compressione riuscita, poi `GraphRecursionError` (modello in ciclo) oppure `openai.APIConnectionError` dall'agente. La sessione restituita è quella ricevuta: stessi messaggi e riassunto vuoto.
  5. `test_compressione_poi_errore_del_router`: come il precedente, ma con `openai.APIConnectionError` dal classificatore del Router (§5.3).
  6. `test_compressione_ripetuta_dopo_turno_fallito`: dopo il fallimento del punto 4, il turno successivo riuscito comprime di nuovo. Il riassuntore ha 2 chiamate in totale e la sessione finale è compressa.
  7. `test_seconda_compressione_usa_il_riassunto_precedente` (Focus 3): `esegui_chat` con **soglia 8**, turni da 2 messaggi e 7 domande. Secondo la review del piano le compressioni avvengono ai turni 5 e 7: le chiamate sono 2. La seconda contiene nel prompt il riassunto restituito dalla prima, e il riassunto finale è il secondo.
  8. `test_chat_usa_la_sessione_accorciata`: dopo la compressione, il modello del turno successivo riceve la cronologia accorciata.
  9. **Fail-open nel turno** (review del piano, I4): riassuntore che solleva `openai.APIConnectionError` dentro `esegui_turno`, con soglia superata. Il turno si completa con la risposta dell'agente (non con `ERRORE_SERVER`); la sessione nuova contiene tutti i messaggi precedenti più il turno, cioè nessuna compressione; c'è un WARNING; il riassunto precedente resta.
  10. `test_tool_calls_integre_dopo_la_compressione`: in ogni sessione uscita da un turno, ogni `AIMessage` con `tool_calls` è seguito dai suoi `ToolMessage` con gli stessi `tool_call_id`, e nessun `ToolMessage` è orfano.
  11. `test_chiamate_al_riassuntore_distinte`: sotto la soglia `riassuntore.chiamate == []`, mentre Router, agente e Revisore hanno le loro chiamate normali.
- [ ] **Step 2:** FALLISCONO (`Sessione` assente).
- [ ] **Step 3a: `Sessione` e nuova firma, senza copie.**
  - `esegui_turno` invoca con `{"messages": [*sessione.messaggi, HumanMessage(domanda)], "riassunto": sessione.riassunto}`;
  - dopo un turno riuscito restituisce `Sessione(tuple(esito["messages"]), esito.get("riassunto", sessione.riassunto))`;
  - se il turno fallisce restituisce `sessione` stessa.
  
  Si eseguono i test del punto 2. **`test_turno_riuscito_non_modifica_la_sessione_senza_id` deve FALLIRE perché gli `id` non sono più `None`.** È il fallimento che giustifica le copie (TDD, review del piano I2). Se non fallisce, ci si ferma.
- [ ] **Step 3b: copie.** `[*(m.model_copy() for m in sessione.messaggi), HumanMessage(domanda)]`. I test del punto 2 passano.
- [ ] **Step 4: adattamento meccanico** delle chiamate a `esegui_turno` in `test_limite.py`, `test_revisore.py`, `test_router.py` e `test_terminale.py`. Le chiamate a `esegui_chat` non cambiano.
  - `[]` diventa `Sessione()`; `precedente` diventa `Sessione(tuple(precedente))`; `cronologia, testo = …` diventa `sessione, testo = …`, con `sessione.messaggi` dove si usava la lista.
  - Le asserzioni dei turni falliti `cronologia == precedente` diventano `sessione.messaggi == tuple(precedente)`: lo stesso significato.
  - `turno()` in `test_revisore.py:316-318` e gli helper analoghi si modificano una volta sola.
- [ ] **Step 5: misura M5.** Suite completa. **Devono fallire esattamente i 6 casi di M5**: `test_router.py:226` e `:314`, più i 4 casi parametrizzati di `test_revisore.py:676`. Ogni altro fallimento va **fermato**.
- [ ] **Step 6: cambiamento atteso M5:** confronto per `[(type(m), m.content) for m in …]`, con commento «spec Step 3 §5.3: copie dei messaggi».
- [ ] **Step 7:** suite completa verde. Commit `feat(terminale): aggiunge la Sessione con turno atomico e copie dei messaggi`.

---

## Task 7 — Il riassunto in Router, agente e Revisore (spec §9, Appendice B)

**Files:** Modify `src/assistente/router.py`, `src/assistente/revisore.py`, `src/assistente/grafo.py`, `src/assistente/riassunto.py`; Test `tests/test_riassunto.py`.

**Interfaces — Produces:**
- `router.riassunto_presente(riassunto: str) -> bool`: `bool(riassunto.strip())`. È l'**unico** predicato di «riassunto vuoto», usato da `sezione_riassunto` e da `nodo_modello`;
- `router.sezione_riassunto(riassunto: str) -> str`: `""` se il riassunto non è presente; altrimenti il testo B.2 **esatto** con il riassunto, seguito da `"\n\n"`;
- **Inserimento senza un secondo `.format` sul riassunto** (review del piano, I3). Nei due template `ISTRUZIONI` si aggiunge il segnaposto `{sezione_riassunto}` subito prima di `TURNI PRECEDENTI (solo contesto):`, e il valore di `sezione_riassunto(riassunto)` viene passato in **un unico** `.format`.
  - I valori sostituiti non vengono ri-formattati, quindi graffe nel riassunto, come un JSON scritto dal modello, compaiono alla lettera.
  - Con `""` il prompt prodotto è identico, carattere per carattere, a quello dello Step 2.
  - Non si inserisce mai la sezione con `replace` sul testo già composto: l'ambito o la domanda potrebbero contenere la stessa intestazione;
- `router.componi_prompt(messaggi, ambito, riassunto: str = "")` e `revisore.componi_prompt(messaggi, inizio_turno, riassunto: str = "")`. Con il valore predefinito le chiamate esistenti non cambiano;
- i nodi Router e Revisore passano `stato.get("riassunto", "")`;
- `riassunto.CORNICE_AGENTE`: il testo B.1 **esatto**, con `{riassunto}`. È l'unico `.format` in cui il riassunto è un valore;
- `nodo_modello` invia `[SystemMessage(CORNICE_AGENTE.format(riassunto=r)), *contesto_agente(...)]` solo se `riassunto_presente(r)`.

Le cornici B.1 e B.2 si estraggono dalla specifica con lo stesso metodo di `ISTRUZIONI`, e un test le confronta con il file.

- [ ] **Step 0: prompt di riferimento dello Step 2**, **prima** di toccare `router.py` e `revisore.py`. Con il codice ancora invariato si generano i prompt di Router e Revisore per 3 input fissi:
  1. nessun turno precedente;
  2. due turni con un'osservazione;
  3. graffe nella domanda.

  Si salvano come stringhe letterali in `tests/test_riassunto.py` (`PROMPT_ROUTER_STEP2`, `PROMPT_REVISORE_STEP2`). Servono da confronto per «identico allo Step 2».
- [ ] **Step 1: test che falliscono.**

  **Riassunto vuoto**
  - Per i 3 input: `router.componi_prompt(m, A) == router.componi_prompt(m, A, riassunto="") == router.componi_prompt(m, A, riassunto="  \n") == PROMPT_ROUTER_STEP2[i]`. Lo stesso per il Revisore.
  - **Graffe nel riassunto** (I3): riassunto `'{"budget": 600} {contesto} {domanda}'`. Nessuna eccezione in Router, Revisore e agente; il testo compare alla lettera nei due prompt e nel `SystemMessage`.
  - Il modello riceve esattamente `contesto_agente(...)`, senza `SystemMessage`, verificato con `ModelloSimulato.chiamate`.

  **Riassunto non vuoto**
  - La sezione B.2 compare una volta, subito prima di `TURNI PRECEDENTI`, in entrambi i prompt; la domanda attuale resta dopo.
  - Il primo messaggio inviato all'agente è un `SystemMessage` con la cornice B.1 e il riassunto.
  - Il `SystemMessage` non compare in `esito["messages"]` né nella `Sessione` e non conta per la soglia: con soglia `k`, aggiungere un riassunto non cambia il conteggio.

  **Integrazione**
  - Turno con compressione in cui il classificatore e il Revisore simulati ricevono il riassunto appena prodotto nello **stesso** turno, e l'agente lo riceve nel `SystemMessage`.
- [ ] **Step 2:** FALLISCONO.
- [ ] **Step 3:** implementare. L'import non deve diventare circolare: `router` non importa `riassunto`; B.2 vive in `router.py`, accanto a `testo_contesto`.
- [ ] **Step 4:** verdi; suite completa verde, compresi tutti i test dei prompt dello Step 1 e dello Step 2, invariati. Commit `feat(riassunto): passa il riassunto a Router, agente e Revisore`.

---

## Task 8 — Documentazione (spec §15, §16)

**Files:** Modify `README.md`, `prove_reali/PROVE.md` (solo la struttura della sezione).

- [ ] **Step 1:** README.
  - **Configurazione:** `SOGLIA_RIASSUNTO`, con predefinito e validazione.
  - **Sezione «Riassunto della cronologia»:**
    - nodo e posizione nel grafo;
    - condizioni;
    - 2 turni conservati;
    - taglio ai confini dei turni;
    - riassunto ai tre componenti;
    - fail-open;
    - atomicità del turno;
    - log da cercare (`assistente.riassunto`, «prima → dopo»).
  - **Limite di passaggi:** formula nuova; righe 239, 244 e 256 e tabella con i valori **misurati** nel T5. Con il limite 16 il massimo è 15 passaggi e il numero dei passaggi di un turno con giudizio è pari.
  - **Limitazioni note** (spec §16):
    - soglia in messaggi;
    - A1;
    - messaggi non recuperabili;
    - fail-open ripetuto;
    - **elenchi lunghi e troncamento a 1000 caratteri**: anche un risultato intero può perdere singoli elementi;
    - risultati storici superati;
    - qualità e stile del riassunto, **nessuna verifica dei fatti, un errore entrato nel riassunto si propaga**;
    - validazione su 5 scenari;
    - latenza;
    - **prompt più lunghi per Router, agente e Revisore** quando c'è un riassunto.
  - Solo comandi verificati.
- [ ] **Step 2:** `PROVE.md`: intestazione della sezione dello Step 3 con l'elenco delle prove del T9 da compilare. Nessun esito inventato.
- [ ] **Step 3:** suite verde. Commit `docs: documenta il riassunto della cronologia`.

---

## Task 9 — Prove reali con LM Studio e Docker (spec §14)

Le prove si fanno a mano, con LM Studio attivo e `google/gemma-4-e2b`. Gli esiti vanno in `PROVE.md` per ogni prova:
- domanda o sequenza;
- log «prima → dopo»;
- esito di Router, agente e Revisore;
- latenze;
- token del server, quando disponibili, solo come diagnostica.

- [ ] **Step 1: preparazione.**
  - Avvio locale come nel README, con `SOGLIA_RIASSUNTO=6` e `NOTE_DB_PATH` su un file temporaneo nella scratchpad.
  - Le prove possono essere guidate da uno script nella scratchpad, con il metodo descritto in `PROVE.md`, Step 2.
  - Si annota l'hash di `data/note.db` prima e dopo: deve restare invariato.
- [ ] **Step 2:** prove 1–7 del §14, ciascuna con una conversazione **nuova** e in ambito. Per la prova 4 (contraddizione) e la 7 (risultato storico superato) servono sequenze in cui il valore cambia prima e dopo la compressione.
- [ ] **Step 3:** prova 8 in Docker: `docker compose build`, poi `docker compose run --rm assistente` con `SOGLIA_RIASSUNTO=6` in `.env`, **senza strumenti delle note**. Al termine si **ripristina `.env`** com'era prima della prova e si verifica che non contenga più `SOGLIA_RIASSUNTO=6`. `.env` non va mai in Git.
- [ ] **Step 4:** registrare tutto in `PROVE.md`, compresi i fallimenti e ciò che non si è riusciti a provare. Se una prova 1–5 o 8 fallisce, **fermarsi** e discuterne con l'utente prima di cambiare qualcosa.
- [ ] **Step 5:** commit `docs: registra le prove reali del riassunto`.

---

## Task 10 — Verifica finale, review, merge (CLAUDE.md «Git»)

- [ ] **Step 1:** suite completa verde. Riportare il numero dei test: 543 più i nuovi.
- [ ] **Step 2:** review indipendente dell'intero ramo (`git diff dev...feat/riassunto`), con specifica, piano e Focus della review. Correzioni con TDD e suite verde.
- [ ] **Step 3:** chiedere all'utente l'autorizzazione ad aggiornare `CLAUDE.md`: riga «Struttura» con `riassunto` e grafo `riassunto → router → …`. Solo se autorizzati, commit `docs: aggiorna CLAUDE.md con il modulo riassunto`.
- [ ] **Step 4:** resoconto all'utente:
  - che cosa è stato eseguito, con quale esito;
  - le misure M1–M7;
  - le prove reali;
  - le limitazioni;
  - che cosa resta da provare.

  Poi attendere l'**approvazione esplicita** del merge.
- [ ] **Step 5:** solo dopo l'approvazione:
  1. `git switch dev`;
  2. `git merge --no-ff feat/riassunto`;
  3. suite verde su `dev`;
  4. `git branch -d feat/riassunto`.

  Nessun push e nessun merge su `main` senza una richiesta esplicita.
