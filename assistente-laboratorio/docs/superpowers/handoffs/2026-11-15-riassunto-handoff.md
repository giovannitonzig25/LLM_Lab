# Handoff — Lezione 6, Step 3 Riassunto della cronologia (2026-11-15)

Documento per avviare lo Step 3 in una nuova sessione Claude Code. Va letto per intero prima di qualsiasi altra azione.

> **Lo Step 3 non è iniziato.** Non ci sono ancora brainstorming, specifica, piano né codice. Si parte dal brainstorming con Superpowers (`superpowers:brainstorming`). Niente codice, ramo o commit prima che l'utente abbia approvato la specifica e poi il piano.

## 1. Stato del progetto (verificato alla scrittura)

- **Repository:** `repo-lab-llm`, progetto in `assistente-laboratorio/`. Le altre cartelle sono altre lezioni: non leggerle per copiarne il codice e non modificarle.
- **Ramo:** **`dev`**, allineato a `origin/dev` (push eseguito su richiesta dell'utente). Nessun ramo di lavoro aperto. `main` è invariato (`9a6c073`).
- **Ultimo commit:** **`086228c` Merge branch 'feat/revisore' into dev**.
- **Non tracciati:** `../LLM_Lez_6.pdf` (materiale del corso, **mai** da aggiungere a Git) e questo handoff, se non è ancora stato committato.
- **Test:** **543 verdi** su `dev` (`.\.venv\Scripts\python.exe -m pytest -v`).
- **Step completati della Lezione 6:**
  - **Step 1 Router di ambito:** merge `8f7f9b8`. Specifica `docs/superpowers/specs/2026-11-15-router-ambito-design.md`, piano `docs/superpowers/plans/2026-11-15-router-ambito.md`.
  - **Step 2 Revisore:** merge `086228c`. Specifica `docs/superpowers/specs/2026-11-15-revisore-design.md`, piano `docs/superpowers/plans/2026-11-15-revisore.md`, handoff `docs/superpowers/handoffs/2026-11-15-revisore-handoff.md`.
  - Prove reali di entrambi in `prove_reali/PROVE.md`.
- **`CLAUDE.md`:** aggiornato con i moduli `router` e `revisore`. Va modificato di nuovo solo con un'autorizzazione esplicita, a fine Step.

## 2. Obiettivo: Step 3 «Riassunto della cronologia» (livello Avanzato)

Dal PDF della lezione (`../LLM_Lez_6.pdf`, slide «Step 3 — Riassunto della cronologia»).

Con un modello locale il contesto è limitato e ogni turno aggiunge messaggi. Un nodo LLM sostituisce i messaggi più vecchi con un riassunto e lascia intatti gli ultimi turni. **Obiettivo:** la conversazione resta utilizzabile su molti turni senza perdere le informazioni importanti.

**Che cosa realizzare** (testo delle slide):
1. Soglia configurabile, in numero di messaggi o in stima dei token, oltre la quale si riassume.
2. Nodo riassunto all'inizio del turno: comprime i messaggi vecchi e conserva gli ultimi N.
3. Il riassunto è un campo dello stato che viene aggiornato, non accumulato.
4. Il taglio non separa mai una richiesta di tool dal relativo `ToolMessage`.

**Evidenze richieste:**
- log con il numero di messaggi prima e dopo il riassunto;
- un'informazione data al primo turno, come il nome dell'utente, viene usata dopo la compressione;
- sotto la soglia il nodo non chiama il modello.

**Posizione nel grafo secondo la slide:** `START → Riassunto → Router → (Agente ⇄ strumenti → Revisore | Rifiuto) → END`. Il riassunto viene **prima** del Router.

**Non anticipare** gli Step 4–9: resource e prompt MCP, agente come servizio HTTP, back-end con salvataggio delle chat, front-end, Compose per componente.

## 3. Architettura attuale rilevante per lo Step 3 (verificata su `086228c`)

```
START → router ─┬─ conversazione → modello ─┬─ tool_calls → strumenti → modello
                │                           ├─ risposta vuota → END
                │                           └─ risposta → revisore ─┬─ coerente / fail-open / limite → END
                │                                                   └─ da correggere → modello (osservazione)
                └─ fuori_ambito → rifiuto → END
```

- **`Stato`** (`grafo.py`): `messages` (`add_messages`), `categoria`, `motivo`, `inizio_turno`, `revisioni`, `esito_revisione`.
- **Lo stato non persiste tra i turni.** Il grafo è compilato senza checkpointer (`grafo.compile()`). La cronologia vive nel terminale: `esegui_turno(grafo, cronologia, domanda, max_passaggi, *, max_revisioni)` invoca il grafo con `[*cronologia, HumanMessage(domanda)]` e restituisce `esito["messages"]` (oppure la cronologia invariata se il turno fallisce). Per un «campo dello stato aggiornato, non accumulato» bisogna quindi decidere come il riassunto sopravvive da un turno all'altro: è un punto **da discutere nel brainstorming**.
- **`inizio_turno`** è scritto dal nodo Router come `len(messages) - 1`. Se il riassunto toglie messaggi prima del Router, l'indice va calcolato **dopo** la compressione: va verificato con un test.
- **Messaggi interni dello Step 2:** la cronologia contiene anche bozze scartate e osservazioni del Revisore (`HumanMessage` con `additional_kwargs={"revisione": True}`, riconosciute **solo** dal contrassegno, con `router.e_osservazione`).
  - `revisore.contesto_agente` le toglie dai turni precedenti prima di chiamare l'agente.
  - `router.turni_precedenti` le salta.

  Il riassunto deve tenerne conto: per esempio, non devono finire nel riassunto come domande dell'utente.
- **Coppie strumenti:** lo Step 2 conserva già le coppie `tool_calls`/`ToolMessage` intatte e in ordine (`test_coppie_strumento_integre_e_ordinate`, `test_payload_del_contesto_filtrato`). Il requisito 4 dello Step 3 va nella stessa direzione.
- **Limite di passaggi:** `recursion_limit = PASSAGGI_ROUTER + (MAX_REVISIONI + 1) × (MAX_PASSAGGI + PASSAGGI_REVISORE)` (`terminale.limite_ricorsione`), con le costanti a 1. Un nodo riassunto aggiunge un passaggio a ogni turno.
  - La formula e la caratterizzazione cambieranno di nuovo: `test_caratterizza_il_limite_di_passaggi` in `tests/test_limite.py`, `test_caratterizza_valori_piccoli` e gli altri test del limite in `tests/test_revisore.py`, oltre alla tabella del README.
  - Lezione degli Step 1–2: i valori si **misurano** sulla LangGraph installata (1.2.19) e si spiegano, **mai** si adattano per far passare i test.
- **Schemi già usati per i nodi LLM**, da riutilizzare se servono:
  - client `ChatOpenAI` separato senza strumenti, `temperature=0`, `reasoning_effort="none"` (`modello.crea_client_router`);
  - output strutturato `with_structured_output(..., method="json_schema", include_raw=True)`;
  - fail-open con eccezioni intercettate **solo** attorno a `invoke`, con `ValidationError`/`LengthFinishReasonError` prima di `OpenAIError`;
  - log su logger dedicato, senza contenuti dell'utente;
  - `router.motivo_per_log`, `router.diagnosi`.
- **Configurazione** (`config.py`): interi letti con validazione e messaggio che nomina la variabile (`MAX_PASSAGGI`, `MAX_REVISIONI`). Una nuova soglia andrebbe trattata allo stesso modo, in `.env.example` e nel README.
- **Doppi di test:** `tests/finti.py` contiene `ModelloSimulato`, `ClassificatoreSimulato` (forma `include_raw`), `in_ambito()`, `approva_sempre()`, `rifiuta_sempre()`. Per il client reale senza rete: `httpx.MockTransport` (helper in `tests/test_revisore.py` e `tests/test_router.py`).

## 4. Fatti dalle prove reali utili per lo Step 3

- **Contesto del modello:** `google/gemma-4-e2b` è caricato in LM Studio con **8192 token** (`lms ps`).
- **Dimensione delle richieste:** una richiesta all'agente dopo 9 turni, con 11 strumenti registrati, misurava **2396 token** di prompt. Gli schemi degli strumenti occupano una parte fissa e rilevante.
- **Errore 400 dopo 902 s:** nello Step 2 si è visto una volta, alla nona domanda di una sessione, e non è stato riprodotto. Un'ipotesi non verificata è il ragionamento del modello che riempie il contesto, perché il client dell'agente non ha `reasoning_effort="none"`. Se lo Step 3 misura i token, può dare indizi, ma **non** è un obiettivo dello Step.
- **Latenze attuali** per ogni turno in ambito, con mediane: Router circa 34 s, Revisore 9,7 s, turno completo 99 s. Un nodo riassunto LLM aggiunge latenza solo quando scatta la soglia, ma il costo va misurato.
- **Prove guidate da script:** lo script che pilota la chat (invia una riga quando compaiono «Tu: » o «[s/N]: » e misura la durata del turno dall'esterno) stava nello scratchpad della sessione precedente, che **non è persistente**. Il metodo è descritto in `prove_reali/PROVE.md`, sezione dello Step 2.
- **Archivio delle note:** per le prove sulle note usare un SQLite temporaneo tramite `NOTE_DB_PATH`, così `data/note.db` non viene toccato. È una preferenza espressa dall'utente nello Step 2.

## 5. Limitazioni accettate dall'utente nello Step 2 (non riaprire senza motivo)

- **Falsi rifiuti del Revisore** sulla domanda «Che ore sono a Tokyo e che tempo fa a Roma?»: 3 su 3 in locale. Un miglioramento del prompt va affrontato **separatamente**, con un nuovo spike: non fa parte dello Step 3.
- **Correzione vuota:** l'utente vede l'avviso di risposta vuota e la bozza non viene mostrata. Comportamento della specifica, accettato.
- **Minore rimandato:** un motivo del Revisore fatto di soli spazi viene accettato, come già nello schema del Router.
- **Altre limitazioni** (latenza, Revisore che non verifica i dati, possibile ripetizione degli strumenti durante una correzione, `MAX_PASSAGGI` come budget nominale per tentativo): nel README, «Limitazioni note».

## 6. Domande aperte per il brainstorming (da decidere con l'utente, non qui)

Sono elencate solo per non dimenticarle; nessuna è decisa.

- **Soglia:** numero di messaggi o stima dei token? Come si contano bozze, osservazioni e `ToolMessage`?
- **Valore di N:** in messaggi o in turni? Come lo si allinea ai confini dei turni e alle coppie strumenti?
- **Persistenza del riassunto tra i turni**, dato che lo stato non persiste: dove vive e come lo restituisce `esegui_turno`?
- **Come il riassunto arriva a ciascun nodo:**
  - agente: messaggio di sistema o altra forma;
  - Router e Revisore: oggi vedono solo gli ultimi 2 turni.
- **Messaggi tolti:** la cronologia salvata viene davvero accorciata (con `RemoveMessage`) o si filtra solo il contesto, come con `contesto_agente`? Quale si accorda con «comprime i messaggi vecchi» e con la cronologia della sessione?
- **Errori del nodo riassunto:** fail-open (si prosegue senza comprimere?) e log, coerenti con Router e Revisore.
- **Contenuti del riassunto:** come si evita che entrino osservazioni del Revisore e bozze scartate? Come si conservano informazioni come il nome dell'utente (evidenza richiesta)?
- **Limite di passaggi:** nuova formula con il passaggio del riassunto e caratterizzazione da rimisurare.
- **Prove reali:** una sessione lunga che superi la soglia, con il nome dell'utente dato al primo turno e richiesto dopo la compressione; poi Docker.

## 7. Vincoli

- **Regole del progetto in `CLAUDE.md`**, da leggere per intero:
  - Superpowers: brainstorming → specifica approvata → piano approvato → implementazione;
  - incrementi piccoli verificati;
  - comandi documentati anche per PowerShell;
  - nessun `.env`, cache, pesi o PDF in Git.
- **Salvataggio:** specifica e piano in `docs/superpowers/specs/` e `docs/superpowers/plans/`.
- **Flusso Git:** `dev` → `feat/<nome>` → review indipendente → **approvazione esplicita dell'utente** → `git merge --no-ff` su `dev` → suite verde → eliminazione del ramo. Mai merge su `main`; push solo su richiesta. Conventional Commits in italiano; `git status`, diff e staging selettivo prima di ogni commit.
- **Test automatici** senza rete né modello. Prove reali con LM Studio e Docker separate e registrate in `prove_reali/PROVE.md`. Una risposta simulata non dimostra il comportamento del modello. Nessuna asserzione cambiata per far passare un test: ogni cambiamento atteso va spiegato e approvato.
- **Da preservare:**
  - Router: rifiuti senza agente, fail-open, `AMBITO_AGENTE` obbligatoria;
  - Revisore: limite di revisioni, osservazioni contrassegnate, contesto filtrato, fail-open distinto dall'approvazione;
  - strumenti e conferma di `elimina_nota` nel terminale.
- **Differenze dalla specifica:** se durante l'implementazione emergono differenze rispetto alla specifica approvata, fermarsi e discuterne con l'utente.
- **Dipendenze:** nessuna nuova senza accordo. Restano esclusi RAG, workflow e tecnologie non richieste.

## 8. Prossima azione

1. Leggere questo handoff, `CLAUDE.md` e, per il contesto, le specifiche degli Step 1 e 2. Verificare `git status`, `git log -1` (atteso `086228c`) e la suite (atteso 543 verdi).
2. Rileggere la slide dello Step 3 in `../LLM_Lez_6.pdf`.
3. Avviare `superpowers:brainstorming` con l'utente sulle domande del §6, una decisione alla volta.
4. Solo dopo l'approvazione della specifica: piano con `superpowers:writing-plans`, da sottoporre all'utente. Poi ramo `feat/riassunto` da `dev`, con autorizzazione.
