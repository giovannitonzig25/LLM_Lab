# Handoff — Lezione 6, Step 2 Revisore (2026-11-15)

Documento per riprendere in una nuova sessione Claude Code **senza ripetere il brainstorming**. Leggerlo per intero, poi leggere la specifica indicata al §5.

> **La specifica NON è ancora approvata dall'utente.** Il brainstorming è concluso (sette decisioni approvate una per una), la specifica è scritta e rivista, ma l'approvazione finale del documento non c'è ancora. Niente piano, niente codice, niente ramo prima di quella approvazione.

## 1. Stato del progetto (verificato alla scrittura)

- Repository: `repo-lab-llm`, progetto in `assistente-laboratorio/` (le altre cartelle sono altre lezioni: non leggerle per copiarne il codice, non modificarle).
- Ramo: **`dev`**, allineato a `origin/dev` (l'utente ha fatto il push dopo lo Step 1). Nessun ramo di lavoro aperto.
- Ultimo commit: **`8f7f9b8` Merge branch 'feat/router' into dev**.
- Non tracciati (da `git status`):
  - `../LLM_Lez_6.pdf`: materiale del corso, **fuori da Git** (non aggiungerlo);
  - `docs/superpowers/specs/2026-11-15-revisore-design.md`: la specifica dello Step 2, non committata;
  - questo file di handoff, non committato.
- Test: **457 verdi** su `dev` dopo il merge dello Step 1 (`.\.venv\Scripts\python.exe -m pytest -v`).
- Step 1 Router: **completato e mergiato** (`--no-ff`). Specifica `docs/superpowers/specs/2026-11-15-router-ambito-design.md`, piano `docs/superpowers/plans/2026-11-15-router-ambito.md`, prove reali in `prove_reali/PROVE.md` (sezione «Ramo `feat/router`»). Limiti lasciati documentati per scelta dell'utente: latenza del Router (mediana 40,5 s), l'agente a volte risponde sulla data senza `orologio`, healthcheck MCP a volte `unhealthy` sotto carico, due minori della review (nessun test sulla richiesta HTTP del classificatore; indice della domanda attuale calcolato due volte).
- `.env` locale: contiene `AMBITO_AGENTE` (obbligatoria dallo Step 1). Servirà aggiungere `MAX_REVISIONI` solo se si vuole un valore diverso dal predefinito.

## 2. Obiettivo attuale

**Step 2 — Revisore** della Lezione 6 (`../LLM_Lez_6.pdf`, slide «Step 2 — Revisore: la risposta è coerente con la domanda?»). Requisiti del corso:
1. nodo revisore che riceve la domanda dell'utente e la risposta proposta dall'agente;
2. output strutturato: coerente (sì/no) e motivo;
3. se non coerente, il motivo entra nella cronologia come indicazione per l'agente;
4. limite di revisioni nello stato: al limite si restituisce l'ultima risposta e lo si segnala nei log.

Evidenze richieste: domanda in due parti con risposta parziale → rifiuto motivato e nuova risposta completa; risposta coerente approvata al primo passaggio; limite rispettato con un revisore simulato che rifiuta sempre.

Non anticipare gli Step 3–9 (riassunto della cronologia, MCP resource/prompt, agente come servizio HTTP, back-end, front-end, Compose per componente).

## 3. Decisioni approvate dall'utente (brainstorming concluso)

Dettagli completi nella specifica; qui il riepilogo operativo.

1. **Posizione e correzione.** Revisore **dopo la risposta finale** dell'agente (nodo `modello` senza `tool_calls`). Coerente → END; non coerente → torna a `modello` con il motivo; l'agente corregge e **può riusare gli strumenti**. Il Revisore non sceglie né esegue strumenti e non riscrive la risposta. Il rifiuto del Router non passa dal Revisore.
2. **Che cosa riceve.** Domanda **originale** del turno (identificata in modo stabile, mai un'osservazione), **ultima risposta proposta**, **ultimi 2 turni** come contesto «solo dati» ricostruiti con la funzione del Router (`router.turni_precedenti`, troncamenti 300/500). Niente risultati o richieste di strumenti, niente cronologia completa, niente data di sistema. Prompt e responsabilità separati dal Router. Criterio: **coerenza e completezza rispetto alla domanda**, non esattezza dei dati.
3. **Output strutturato.** Pydantic `Valutazione(coerente: bool, motivo: str non vuoto)`; client `ChatOpenAI` separato senza strumenti, stesso modello, `temperature=0`, `reasoning_effort="none"`, `with_structured_output(..., method="json_schema", include_raw=True)`. Istruzioni = **variante B** dello spike (§4). Tolleranza nei casi dubbi, ma risposte evasive o incomplete non approvate.
4. **Limite di revisioni.** Campo di stato `revisioni` = **numero di correzioni richieste** (non di chiamate al Revisore), **azzerato esplicitamente a ogni turno**. `MAX_REVISIONI` variabile d'ambiente, **predefinito 1**, intero ≥ 0. Con 1: una correzione, Revisore al massimo 2 volte. Con 0: Revisore **chiamato comunque** (aggiunge latenza), nessuna correzione. Giudizio negativo a limite raggiunto → ultima risposta + `WARNING`; il `WARNING` **solo se l'ultimo giudizio è negativo**. Nessun avviso nel testo per l'utente.
5. **`MAX_PASSAGGI` (delicata).** `recursion_limit = PASSAGGI_ROUTER + (MAX_REVISIONI + 1) × (MAX_PASSAGGI + PASSAGGI_REVISORE)`, con entrambe le costanti = 1 → **15** con i predefiniti (8 con `MAX_REVISIONI=0`). `MAX_PASSAGGI` diventa un **budget nominale per tentativo, non un limite rigido**: il limite LangGraph è globale e un ciclo infinito di strumenti si ferma più tardi (compromesso **accettato esplicitamente**, nessun secondo contatore). Limiti distinti: `MAX_REVISIONI` raggiunto → ultima risposta + `WARNING`; `GraphRecursionError` → turno scartato, cronologia invariata, messaggio esistente. **Cambiano** (da misurare con test sulla LangGraph installata 1.2.19 e spiegare, mai adattare per farli passare): `test_caratterizza_il_limite_di_passaggi` (previsione 6 → 7/7, 2 → 3/3, `MAX_REVISIONI=0` e 6 → 4/3), `test_rifiuto_con_max_passaggi_1_fissa_il_limite` (con `MAX_PASSAGGI=1` ora il rifiuto si completa), README sul limite.
6. **Messaggi e cronologia (delicata).**
   - Il motivo arriva all'agente come **`HumanMessage` con testo fisso** (motivo troncato a 300) e **contrassegno strutturale `additional_kwargs={"revisione": True}`**, applicato dal programma, mai cercato nel testo. Verificato con `langchain-openai` 1.7.3 e richiesta HTTP simulata: `additional_kwargs`, `response_metadata`, `id` **non** arrivano a LM Studio; **`name` sì → escluso**.
   - **Cronologia completa** salvata (domanda, strumenti, bozze, osservazioni, risposta finale): nessuna potatura.
   - **Contesto filtrato per l'agente**: funzione pura `contesto_agente(messages, inizio_turno)`. Turno in corso intatto (bozza + osservazione corrente visibili); nei turni precedenti tolte le osservazioni contrassegnate e le **bozze**, definite **solo** come `AIMessage` senza `tool_calls` seguito **immediatamente** da un'osservazione. Coppie `tool_calls`/`ToolMessage` intatte e in ordine; senza osservazioni il contesto è identico alla cronologia.
   - Router e Revisore ricostruiscono i turni saltando le osservazioni.
7. **Errori e log.** Fail-open (ultima risposta, nessuna correzione, `esito_revisione="senza_revisione"`) per output non valido (`pydantic.ValidationError` e `openai.LengthFinishReasonError` sollevate da `invoke` — lezione dello Step 1 —, `parsing_error`, `parsed=None`) **e** per `openai.OpenAIError` del Revisore; intercettazioni **solo attorno a `invoke`** (composizione del prompt fuori dal `try`); eccezioni impreviste propagate; nessun `except Exception`; nessun retry applicativo. Il fail-open **non** va registrato come `coerente=true`. Compromesso dichiarato: l'utente può ricevere una risposta non verificata. Errori dell'agente e `GraphRecursionError` invariati. Logger `assistente.revisore`, `INFO` per giudizi validi, `WARNING` per errori/fail-open/limite, `durata` sempre, motivo ≤ 120 caratteri su una riga, mai domanda/risposta/contesto/output grezzo.

**Rilievo D1 della review (approvato, opzione A) — rischio di duplicare operazioni.** Durante una correzione l'agente può rieseguire strumenti; `aggiungi_nota` potrebbe creare un duplicato. Soluzione: **avvertenza nel testo dell'osservazione** («non ripetere le azioni già eseguite in questo turno…»), **nessun blocco o deduplicazione**; rischio residuo documentato; test sulla presenza dell'avvertenza; prova reale 6bis con nota temporanea e archivio ripristinato. **Se nelle prove emergono duplicati: registrarli e discuterne con l'utente prima di chiudere lo Step 2.**

## 4. Spike con Gemma (usa-e-getta, fuori dalla repository)

Modello `google/gemma-4-e2b`, risposte scritte a mano, giudizi attesi fissati prima di ogni esecuzione e mai modificati.

| Esperimento | 8 casi originali | Note |
|---|---|---|
| 1 regole iniziali | 15/24 | falsi rifiuti sistematici: data «futura», chiarimento, servizio non disponibile |
| 2 regole riviste | 20/24 | caso data ancora 0/3 |
| 3 riviste + data di sistema (A) + esempio data/ora (B) | 24/24 | solo A sui casi critici: 6/9 (la data non basta); solo B: 9/9 |
| 4 **solo B (approvata)** | 24/24 + 3 casi nuovi 9/9 | 0 errori |

False approvazioni: 0 in tutti gli esperimenti. Limiti: 11 casi distinti (le ripetizioni a `temperature=0` danno motivi identici: non sono campioni indipendenti); risposte brevi scritte a mano; motivi a volte imprecisi con giudizio corretto; latenza mediana molto variabile (22,9 / 30,9 / 34,0 / 5,5 s), la 5,5 s **non** è rappresentativa.

**Prompt finale approvato: Appendice A della specifica** (`docs/superpowers/specs/2026-11-15-revisore-design.md`), con la descrizione del campo `motivo`. Gli script degli spike erano nello scratchpad della sessione precedente e **non sono persistenti**: non cercarli; la specifica contiene tutto ciò che serve.

## 5. Specifica

- Percorso: **`docs/superpowers/specs/2026-11-15-revisore-design.md`** (non committata).
- Stato: **bozza in attesa di approvazione dell'utente**. Le sette decisioni sono approvate; il documento nel suo insieme no.
- Review indipendente (builder check) fatta: rilievi **D1** (azioni ripetute → opzione A dell'utente), **D2** (risposta vuota salta il Revisore, comportamento invariato), **D3** (`max_revisioni` passato sia a `costruisci_grafo` sia a `esegui_turno`, dallo stesso `Config`), **D4** (suffisso di log `→ limite`), **I1** (spiegato il massimo di 14 passaggi con limite 15), **I2** (test 18: campo `coerente`, non `categoria`). L'utente ha accettato le soluzioni di tutti e sei.
- **Scelte marcate [Scelta mia] da far confermare all'utente nella revisione finale:**
  - modulo dedicato `revisore.py`; riconoscimento del contrassegno in `router.py` (evita import circolare);
  - il **nodo Router** inizializza `inizio_turno` e `revisioni = 0` a ogni turno (un nodo dedicato costerebbe un passaggio e cambierebbe la formula approvata);
  - campo di stato `esito_revisione` (`approvata` / `da_correggere` / `limite` / `senza_revisione`);
  - formulazione esatta del testo dell'osservazione (l'avvertenza D1 è decisione dell'utente);
  - D2, D3, D4 come sopra (già accettate dall'utente).

## 6. Vincoli

- Regole del progetto in `CLAUDE.md` (leggerlo). **Non modificare CLAUDE.md** senza autorizzazione esplicita (a fine Step: riga «Struttura» con `revisore`, solo se autorizzato).
- Workflow Superpowers: specifica approvata → piano (`superpowers:writing-plans`) approvato → implementazione (nello Step 1: esecuzione **nativa**, `superpowers:executing-plans`, review indipendente finale sull'intero ramo). Chiedere all'utente il metodo di esecuzione al momento del piano.
- Git: nessun ramo, commit, merge o push senza autorizzazione. Flusso: `dev` → `feat/revisore` → review indipendente → **approvazione esplicita dell'utente** → `git merge --no-ff` su `dev` → suite verde → eliminazione del ramo. Mai merge su `main`, push solo su richiesta. Conventional Commits in italiano; `git status`, diff e staging selettivo prima di ogni commit; mai `.env`, cache, `../LLM_Lez_6.pdf`.
- Router dello Step 1 da preservare: rifiuti senza agente, fail-open per output non valido (`ValidationError`/`LengthFinishReasonError` intercettate solo attorno a `invoke`), log senza dati superflui, `AMBITO_AGENTE` obbligatoria.
- Test automatici senza rete né modello (client reale con `httpx.MockTransport` ammesso); prove reali con LM Studio e Docker separate e registrate in `prove_reali/PROVE.md`; una risposta simulata non dimostra il comportamento del modello. Non modificare asserzioni per farle passare: ogni cambiamento atteso va spiegato.
- Se emergono differenze rispetto alla specifica approvata durante l'implementazione: fermarsi e discuterne con l'utente.
- Comandi documentati anche per PowerShell; caricamento di `.env` con `Get-Content .env -Encoding UTF8 | …` (vedi README).

## 7. Prossima azione

1. Leggere questo handoff, `CLAUDE.md` e la specifica `docs/superpowers/specs/2026-11-15-revisore-design.md`; verificare `git status` e `git log -1`.
2. Riprendere dalla **revisione finale della specifica** con l'utente: raccogliere le sue correzioni e la conferma delle voci [Scelta mia] (§5 di questo documento).
3. Solo dopo l'**approvazione esplicita della specifica**: preparare il piano con `superpowers:writing-plans` in `docs/superpowers/plans/2026-11-15-revisore.md`, sottoporlo all'utente e attendere l'approvazione.
4. Nessun codice, ramo o commit prima di specifica **e** piano approvati (il commit di specifica e piano su `dev` avviene solo con autorizzazione, come nello Step 1).
