# Handoff — Lezione 6, Step 3 Riassunto della cronologia: implementazione (2026-11-15)

Documento per riprendere lo Step 3 in una nuova sessione Claude Code. Va letto per intero prima di qualsiasi azione.

Riassume, ma **non sostituisce**, i due documenti vincolanti:
- **specifica:** `docs/superpowers/specs/2026-11-15-riassunto-design.md`;
- **piano:** `docs/superpowers/plans/2026-11-15-riassunto.md`.

In caso di dubbio valgono specifica e piano. L'handoff precedente (`2026-11-15-riassunto-handoff.md`) riguardava l'avvio del brainstorming ed è superato.

> **Stato:** brainstorming, specifica e piano sono **approvati dall'utente**. **Solo il Task 0 è eseguito**: commit di specifica, piano e di questo handoff su `dev`, poi ramo `feat/riassunto`. **Nessun codice dello Step 3 è stato scritto.** Si riprende da **T1** con `superpowers:executing-plans`, esecuzione nativa scelta dall'utente.

## 1. Stato del repository alla consegna

- **Progetto:** `assistente-laboratorio/` nella repository `repo-lab-llm`. Le altre cartelle sono altre lezioni: non leggerle e non modificarle.
- **Base:** `dev` con l'ultimo commit precedente `d245ed8` (handoff di avvio dello Step 3). Sopra c'è il commit del T0 con specifica, piano e questo handoff; l'hash è nel resoconto di consegna e in `git log`.
- **Ramo attivo atteso:** `feat/riassunto`, creato da `dev` subito dopo il commit del T0.
- **Altri rami:** `main` invariato (`9a6c073`); `origin/dev` = `d245ed8`. Il commit del T0 **non è pushato**: push solo su richiesta.
- **Test:** **543 verdi** su `dev` (`.\.venv\Scripts\python.exe -m pytest -v`).
- **Non tracciato:** `../LLM_Lez_6.pdf`, materiale del corso, **mai** in Git.

**Prima azione della nuova sessione:** verificare tutto questo con `git status`, `git log --oneline -3`, `git branch --show-current` e la suite. Se lo stato non corrisponde, fermarsi e chiedere.

## 2. Obiettivo dello Step 3

Con un modello locale il contesto è limitato: `google/gemma-4-e2b` ha 8192 token. Un nodo **Riassunto** all'inizio di ogni turno, oltre una soglia, sostituisce i turni più vecchi con un riassunto aggiornato e conserva gli ultimi turni.

L'esigenza dell'utente è la **continuità della conversazione**. Il riassunto deve conservare:
- l'obiettivo;
- informazioni e vincoli;
- preferenze;
- decisioni aggiornate;
- risultati utili;
- questioni aperte.

Il riassunto descrive lo **stato attuale**: una decisione cambiata sostituisce la precedente. Bozze e osservazioni del Revisore non vanno conservate. Nessuna memoria persiste tra esecuzioni diverse del programma.

**Evidenze richieste dalla slide:**
- log del numero di messaggi prima → dopo;
- un'informazione data al primo turno usata dopo la compressione;
- sotto la soglia nessuna chiamata al modello riassuntore.

## 3. Le dieci decisioni (dettagli nella specifica)

| # | Decisione | Spec |
|---|---|---|
| 1 | Compressione **reale**: i turni vecchi escono dallo stato con `RemoveMessage`; il riassunto viene aggiornato, non accumulato | §1, §4 |
| 2 | Soglia in **numero di messaggi** (`SOGLIA_RIASSUNTO`), contando tutti i messaggi dello stato. Non garantisce la finestra di contesto | §6.2, §6.4 |
| 3 | **N = 2 turni completi** conservati più la domanda attuale. Taglio solo all'inizio di una domanda reale. Il modello si chiama solo se la soglia è superata **e** c'è almeno un turno eliminabile. Caso A1 accettato | §6 |
| 4 | Nodo `riassunto` tra START e `router` (4a); **turno atomico** (4b) | §4, §5.3 |
| 5 | Campo `riassunto: str` nello stato, senza reducer. `Sessione` immutabile in `terminale.py` | §5 |
| 6 | Riassunto ai tre componenti: `SystemMessage` temporaneo per l'agente, sezione B.2 nei prompt di Router e Revisore. Prompt identici allo Step 2 se il riassunto è vuoto | §9, Appendice B |
| 7 | **Fail-open** del riassuntore; aggiornamento atomico | §8 |
| 8 | Output in **testo libero** con sei sezioni fisse, senza schema; client senza strumenti | §7.3 |
| 9 | Un unico prompt di testo con la trascrizione dei soli turni che escono; risultati degli strumenti troncati a 1000 caratteri con indicatore | §7.1, §7.2 |
| 10 | Prompt v4 (Appendice A), parametri numerici scelti con gli spike | §13, Appendice A |

**Scelte confermate dopo la review della specifica:**
- copie dei messaggi sempre;
- abbinamento chiamata–risultato per `tool_call_id`;
- testo B.2 («valgono le informazioni più recenti», esteso alla domanda attuale);
- prova Docker senza strumenti delle note;
- WARNING senza contenuti.

## 4. Configurazione e costanti

| Nome | Valore | Dove |
|---|---|---|
| `SOGLIA_RIASSUNTO` | predefinito **20**, intero positivo; vuoto = 20; altrimenti `ErroreConfigurazione` con il nome della variabile | `config.py`, `.env.example`, README |
| `TURNI_CONSERVATI` | **2**, costante, distinta da `TURNI_CONTESTO` ma con lo stesso valore | `riassunto.py` |
| `MAX_TOKENS_RIASSUNTO` | **768** | `riassunto.py` / `crea_riassuntore` |
| `MAX_RISULTATO_TRASCRITTO` | **1000** caratteri, con `[risultato troncato: mostrati i primi 1000 caratteri su N]` | `riassunto.py` |
| Riassuntore | `ChatOpenAI` separato, `temperature=0`, `reasoning_effort="none"`, `max_tokens=768`, senza strumenti né output strutturato | `modello.crea_riassuntore` |
| Prove reali | `SOGLIA_RIASSUNTO=6` | `.env`, da ripristinare dopo |

## 5. Architettura LangGraph prevista

```
START → riassunto → router ─┬─ conversazione → modello ⇄ strumenti … → revisore → …   (invariato)
                            └─ fuori_ambito → rifiuto → END
```

- Il nodo `riassunto` viene attraversato a ogni turno.
- Quando comprime restituisce `{"riassunto": nuovo, "messages": [RemoveMessage(id=...) ...]}`; altrimenti `{}`.
- Il Router gira dopo e calcola `inizio_turno` sulla lista già compressa.
- **Il campo `riassunto` non si inizializza da solo** (TypedDict senza reducer):
  - `esegui_turno` lo passa sempre;
  - i nodi leggono `stato.get("riassunto", "")`.
- **Limite di passaggi:** `recursion_limit = 1 (Riassunto) + 1 (Router) + (MAX_REVISIONI+1) × (MAX_PASSAGGI+1)`. **Nodo e formula entrano insieme nel T5.**

## 6. Sessione, copie, atomicità (spec §5)

- **`Sessione`:** `@dataclass(frozen=True)` con `messaggi: tuple[BaseMessage, ...] = ()` e `riassunto: str = ""`.
- **`esegui_turno(grafo, sessione, domanda, max_passaggi, *, max_revisioni) -> tuple[Sessione, str]`:**
  - invoca con **copie** (`m.model_copy()`) più la nuova domanda, e con `riassunto`;
  - dopo un turno riuscito restituisce una nuova `Sessione` con `esito["messages"]`, eventualmente più corta, ed `esito.get("riassunto", ...)`;
  - se il turno fallisce (`GraphRecursionError`, oppure `OpenAIError` dall'agente **o dal Router**) restituisce **lo stesso oggetto** ricevuto. Una compressione fatta in quel turno si perde e si ripete al turno dopo.
- **`esegui_chat`:** firma **invariata**; internamente parte da `Sessione()`.
- **Mutazione degli id, confermata:** `add_messages` assegna gli `id` sugli oggetti ricevuti. Da qui le copie.
- **Correzione D1, approvata:**
  - solo il test con una sessione costruita a mano **senza `id`** va visto fallire prima delle copie (T6, Step 3a);
  - il test con una sessione reale uscita da un turno precedente è un **test di regressione** e non può fallire senza copie.

## 7. Riassunto in Router, agente e Revisore (spec §9)

- **Agente:** `[SystemMessage(CORNICE_AGENTE.format(riassunto=r)), *contesto_agente(...)]` solo se il riassunto è presente. Il messaggio è temporaneo: mai in `messages`, mai nella `Sessione`, mai contato per la soglia. Cornice B.1, testo esatto.
- **Router e Revisore:** sezione B.2, testo esatto, subito prima di `TURNI PRECEDENTI (solo contesto):`. Viene inserita tramite il segnaposto `{sezione_riassunto}` in un **unico** `.format`, così le graffe nel riassunto compaiono alla lettera. Non si usa mai `replace` sul testo composto.
- **Un solo predicato:** `router.riassunto_presente(r) = bool(r.strip())`.
- **Riassunto vuoto:** prompt **identici carattere per carattere** allo Step 2. Nel T7, Step 0, si salvano i prompt di riferimento **prima** di modificare `router.py` e `revisore.py`.
- **Import:** `router` non importa `riassunto`; B.2 vive in `router.py`.

## 8. Fail-open, errori e log (spec §8, §10)

- **Ordine:**
  1. intercettazione solo attorno a `invoke`: `openai.LengthFinishReasonError` (solo difensiva, irraggiungibile senza output strutturato), poi `openai.OpenAIError`;
  2. sulla risposta: prima `response_metadata["finish_reason"] == "length"`, poi `.text.strip()` vuoto.
- **Errore atteso:** `{}` (nessun `RemoveMessage`, riassunto invariato), un WARNING, il turno prosegue verso il Router. Nessun retry.
- **Errori imprevisti** (trascrizione, prompt, bug): si propagano. Composizione e trascrizione stanno fuori dal `try`.
- **Aggiornamento atomico:** prima si valida il riassunto, poi si restituiscono insieme `riassunto` e `RemoveMessage`.
- **Log** `assistente.riassunto`:
  - INFO: «soglia non superata», «nessun turno eliminabile», compressione con **messaggi prima → dopo** e durata;
  - WARNING: **solo** `type(errore).__name__` oppure l'etichetta `vuoto` / `troncato (finish_reason=length)`, più la durata. Mai `str(errore)`, testi dell'utente, degli strumenti, del riassunto o del modello. È previsto un test con contrassegni.

## 9. Spike e limitazioni accettate

Dettagli nella spec §13 e §16. Gli script dello spike erano nella scratchpad, che **non è persistente**.

- **Ruolo di sistema:** Gemma 4 lo accetta. Il riassunto viene usato e non eseguito come istruzione. Con la regola di precedenza, 3 esecuzioni su 3 hanno usato il valore recente (600 €, non 500 €).
- **Prompt del riassuntore:** v1 → v4 in 3 revisioni sugli stessi 5 scenari (S1–S5), con la checklist fissata prima delle esecuzioni. La v4 soddisfa la checklist, tranne S4.
- **Misure con la v4:**
  - token di ragionamento 0;
  - token in uscita fino a 370;
  - latenza 6–30 s, con picchi del server fino a 68 s;
  - `finish_reason == "length"` rilevato.
- **S4, elenco lungo:** la nota «certificato medico» in fondo a un `elenca_note` di 2437 caratteri **non è conservata nemmeno senza troncamento** (prova a 1000, 2000 e 3000). È un limite accettato: la fonte autorevole resta lo strumento.
- **Limitazioni da documentare nel README** (T8):
  - soglia in messaggi;
  - caso A1;
  - messaggi eliminati non recuperabili;
  - fail-open ripetuto che fa crescere la cronologia;
  - elenchi lunghi e troncamento;
  - risultati storici legati a decisioni superate;
  - qualità del riassunto (nessuna verifica dei fatti, gli errori si propagano);
  - validazione su soli 5 scenari, con output a `temperature=0` non sempre deterministico;
  - latenza;
  - prompt più lunghi.

## 10. Previsioni M1–M7 (piano, sezione «Previsioni da misurare»)

Vanno **misurate e mai adattate**. Una differenza va fermata, analizzata e riferita all'utente.

| # | Previsione | Task |
|---|---|---|
| M1 | Caratterizzazione invariata: `(2,1)→3/3`, `(6,1)→7/7`, `(2,0)→2/1`, `(6,0)→4/3` | T5 |
| M2 | `limite_ricorsione` `(6,1),(6,0),(1,1)` → `(16, 9, 6)` (era `(15, 8, 5)`): unico test che deve fallire nel T5 | T5 |
| M3 | Esiti dei valori piccoli e dei casi «13/15» invariati; solo commenti e nomi da correggere (i turni durano 14/16; con il limite 16 il massimo è 15 e un turno con giudizio ha un numero pari di passaggi) | T5 |
| M4 | Il rifiuto usa 3 passaggi e si completa con qualunque valore | T5 |
| M5 | Con le copie falliscono **esattamente 6 casi**: `test_router.py:226`, `:314` e i 4 parametrizzati di `test_revisore.py:676`. Si correggono confrontando `(type, content)` | T6 |
| M6 | Payload del riassuntore: `max_completion_tokens: 768`, `reasoning_effort: "none"`, `temperature: 0.0`, senza `tools` | T3 |
| M7 | `finish_reason: "length"` arriva in `response_metadata` senza eccezioni | T3 |

## 11. Task T0–T10

| Task | Contenuto | Stato |
|---|---|---|
| T0 | Specifica e piano su `dev`, ramo `feat/riassunto` | **eseguito** in questa sessione |
| T1 | `SOGLIA_RIASSUNTO` | da fare |
| T2 | Funzioni pure: turni, taglio, trascrizione per `tool_call_id`, `ISTRUZIONI` estratte dalla specifica; ridenominazione `e_bozza_scartata` | da fare |
| T3 | `crea_riassuntore` (M6, M7) | da fare |
| T4 | Nodo con fail-open e log; `RiassuntoreSimulato`, `riassuntore_inerte` in `finti.py` | da fare |
| T5 | Nodo nel grafo **più la nuova formula** (M1–M4); adattamento delle 13 righe `costruisci_grafo(` nei test | da fare |
| T6 | `Sessione`, copie in due passi (3a senza, 3b con), atomicità, fail-open nel turno (M5) | da fare |
| T7 | Riassunto ai tre componenti; prompt di riferimento dello Step 2 salvati prima | da fare |
| T8 | README e `PROVE.md` (solo struttura) | da fare |
| T9 | Prove reali locali (`SOGLIA_RIASSUNTO=6`, `NOTE_DB_PATH` temporaneo) e Docker (senza note, `.env` da ripristinare) | da fare |
| T10 | Suite, review indipendente del ramo, permesso per `CLAUDE.md`, resoconto, merge **solo con approvazione** | da fare |

## 12. Vincoli

- **Regole del progetto:** `CLAUDE.md`, da leggere per intero. TDD: ogni test va visto fallire prima dell'implementazione. Incrementi piccoli, un commit per task come indicato nel piano.
- **Test** senza rete né modello; client reale solo con `httpx.MockTransport`. Prove reali separate, con esiti in `prove_reali/PROVE.md`. Una risposta simulata non dimostra il comportamento del modello.
- **Mai cambiare un'asserzione per far passare un test.** Gli unici cambiamenti attesi sono M2, M5 e i commenti di M3, ciascuno con un commento che rimanda alla specifica. Gli adattamenti meccanici (`costruisci_grafo`, `Sessione`) non cambiano il significato.
- **Database delle note:** `data/note.db` non va mai toccato; per le prove si usa `NOTE_DB_PATH` temporaneo, solo in locale. Non modificare `compose.yaml`.
- **Git:**
  - lavorare su `feat/riassunto`; Conventional Commits in italiano;
  - prima di ogni commit `git status`, diff e staging selettivo;
  - mai `.env`, `../LLM_Lez_6.pdf`, cache o `data/`;
  - ogni messaggio termina con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
  - **niente push**;
  - merge `--no-ff` su `dev` **solo con approvazione esplicita**, poi suite verde ed eliminazione del ramo; mai `main`.
- **`CLAUDE.md`** si modifica solo nel T10 e solo con autorizzazione esplicita.
- **Fermarsi e chiedere** se una misura differisce da M1–M7, se fallisce una prova reale 1–5 o 8, o se emerge una differenza rispetto alla specifica approvata.
- Non anticipare gli Step 4–9. Nessuna dipendenza nuova.
- **PowerShell 5.1:** un `git push` può restituire il codice 255 solo perché git scrive su stderr; va verificato con `git fetch`. I file scritti da PowerShell vanno salvati in UTF-8 senza BOM.

## 13. Come riprendere

1. Leggere per intero `CLAUDE.md`, questo handoff, la specifica e il piano.
2. Verificare lo stato effettivo: ramo `feat/riassunto`, commit del T0 in cima, albero pulito salvo `../LLM_Lez_6.pdf`, 543 test verdi. Se qualcosa non corrisponde, fermarsi.
3. Avviare `superpowers:executing-plans` sul piano.
   - Il ledger di esecuzione **non esiste ancora**: va creato nel workspace del piano, come prevede la skill.
   - Il T0 è già eseguito: registrarlo nel ledger come completato in questa sessione (commit del T0), **senza rifarlo**.
4. Eseguire da **T1** in poi, un task alla volta, rispettando le fermate indicate sopra.
