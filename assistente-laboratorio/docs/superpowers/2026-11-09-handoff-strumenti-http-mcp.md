# Handoff — Strumenti locali, HTTP e MCP (assistente-laboratorio)

Aggiornato il 2026-11-09, dopo il merge di `feat/calcolatrice` (T0–T11 chiusi). Scopo: riprendere in una nuova sessione di Claude Code senza rileggere la conversazione. Non duplica specifica e piano: li richiama.

## 1. Documenti di riferimento (approvati, definitivi)

| Documento | Percorso (da `assistente-laboratorio/`) |
|---|---|
| Specifica (approvata ed emendata il 2026-11-09) | `docs/superpowers/specs/2026-11-03-strumenti-http-mcp-design.md` |
| Piano, 16 task T0–T15 | `docs/superpowers/plans/2026-11-09-strumenti-http-mcp.md` |
| Esiti delle prove reali (simulato vs provato) | `prove_reali/PROVE.md` |

Il piano contiene vincoli globali, focus della review, «Divergenze dalla specifica» e la «Procedura di ramo» P1–P6. Leggerlo per intero prima di agire, in particolare i task T12–T15 e «Vincoli globali».

## 2. Stato (verificato il 2026-11-09)

- **Git:** branch `dev` (unico oltre a `main`), ultimo commit `dd41f49` (merge di `feat/calcolatrice`), **21 commit avanti a `origin/dev`, nessun push fatto**. Albero pulito salvo `LLM_Lez_5.pdf` non tracciato (l'utente ha deciso di **non versionarlo**).
- **Test:** 309 passati (`.\.venv\Scripts\python.exe -m pytest -q` da `assistente-laboratorio/`, circa 30 s).
- **Strumenti attivi (7):** locali `orologio`, `converti_unita`, `calcola`; MCP `aggiungi_nota`, `elenca_note`, `elimina_nota`, `meteo`.
- **Docker:** nessun container né volume rimasto; immagini `assistente-laboratorio-assistente` e `-server-mcp` costruite (identiche, due `build: .` senza `image:` condiviso).

| Task | Ramo | Stato | Merge su `dev` |
|---|---|---|---|
| T0 | `dev` | fatto (`8c0911f`) | — |
| T1–T7 | `feat/mcp-note` | fatto, review, approvato | `f2ff260` |
| T8–T9 | `feat/mcp-meteo` | fatto, review, approvato | `ee87be7` |
| T10 | `feat/conversione-unita` | fatto, review, approvato | `b7eb5b4` |
| T11 | `feat/calcolatrice` | fatto, review, approvato | `dd41f49` |
| **T12–T13** | `feat/http-scadenze` | **da fare (prossimo)** | — |
| T14 | `feat/http-catalogo` | da fare | — |
| T15 | su `dev` | da fare (verifica finale, README completo, punto 5 di `CLAUDE.md`) | — |

## 3. Decisioni finali da non rimettere in discussione

- **6 funzionalità, 11 strumenti:** locali (`converti_unita`, `calcola`), FastAPI (`giorni_lavorativi`, `calcola_scadenza`, `cerca_catalogo`, `dettaglio_catalogo`), FastMCP (`aggiungi_nota`, `elenca_note`, `elimina_nota`, `meteo`) più `orologio`.
- **MCP:** solo Streamable HTTP; ponte sincrono sopra il client FastMCP con discovery reale (`mcp_client.py`); grafo e terminale non si riscrivono.
- **Conferma di `elimina_nota`:** chiesta dal terminale (`[s/N]`) tramite `chiedi_conferma`, in base a `destructiveHint` letto dalla discovery; non è un parametro del modello. Solo un `True` esplicito vale come sì. **Dopo la review di T7:** gli argomenti vengono validati contro lo schema **prima** di chiedere conferma (niente `id=True` letto come 1). Limite accettato e documentato nel README: il server da solo non protegge dalle chiamate di altri client MCP.
- **Risultati MCP:** troncati a 4000 caratteri con avviso; un risultato vuoto o non testuale diventa `(nessun contenuto testuale nel risultato)`.
- **Avvio ridotto:** garantito dal programma con attesa limitata `MCP_ATTESA_AVVIO` (0 in locale, 20 in Compose); Compose usa `depends_on: condition: service_started` (mai `service_healthy`). Se il server MCP non riesce a partire (porta occupata) `docker compose run --rm assistente` fallisce: usare `docker compose run --rm --no-deps assistente` (verificato, nel README). Stesso schema da applicare a `servizi-http` in T13: gli strumenti HTTP sono **sempre** registrati (nessuna discovery) e un servizio spento dà `Errore: servizio non raggiungibile ...` alla chiamata.
- **Controlli di salute:** `server-mcp` con vera discovery (`python -m assistente.verifica_mcp`); `servizi-http` dovrà fare una richiesta HTTP reale a `/salute`, non una semplice connessione TCP.
- **Dipendenze fissate:** `fastmcp==4.1.6`, `fastapi==0.162.2`, `uvicorn==0.54.0`, `httpx==0.28.1` (già in `requirements.txt`; FastAPI e uvicorn sono installati ma non ancora usati). Nessuna verifica CVE fatta.
- **Strumenti locali:** `@tool` con `handle_validation_error` assegnato dopo la creazione (`tool.handle_validation_error = funzione`) per dare una riga d'errore chiara invece del messaggio lungo di pydantic; descrizione in italiano con esempio.
- **Docker:** `docker compose run` non ha `--network` (usare `docker run --network none` sull'immagine); `build` può dare un errore transitorio di snapshot: rieseguirlo.
- **Esecuzione:** nativa (`superpowers:executing-plans`), review indipendente a fine ramo (P4) con subagente `general-purpose` modello `fable`, **approvazione dell'utente prima di ogni merge** (P5). Merge `git merge --no-ff -m "..."` (**non** `-F`: non funziona), nessun push, nessun merge su `main`.

## 4. Procedura che ha funzionato (ripeterla per T12–T14)

1. **P1:** `git status` pulito su `dev`, `git switch -c feat/<nome>`.
2. **TDD:** scrivere i test, vederli fallire per il motivo giusto, implementare, vederli passare; suite completa; commit con staging selettivo e la riga `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
3. **Prove reali (P3):** server MCP locale in un processo staccato con PowerShell (`Start-Process ... -WindowStyle Hidden`, PID salvato in un file nella scratchpad, fermato con `Stop-Process`); agente con input da pipe dalla shell bash (`PYTHONUTF8=1`, `LM_STUDIO_BASE_URL=http://localhost:1234/v1`, `LM_STUDIO_MODEL=google/gemma-4-e2b`); verificare nei log `strumento richiesto/eseguito`. Più formulazioni per strumento, controlli sugli altri strumenti, casi d'errore forzati. Poi regressione in Docker (`docker compose build`, `up -d server-mcp`, un'esecuzione dell'agente con `-T`, `down -v`) e pulizia (nessun container né volume né processo sulla 8001). Esiti in `prove_reali/PROVE.md` distinguendo **provato con il modello** da **solo simulato**, con conteggi riletti dai log.
4. **P4:** review con un subagente (prompt mirato, sola lettura, diff piccolo): il primo revisore di T9 si è bloccato per 600 s e la review è stata rifatta; se succede, dirlo all'utente.
5. **Giro di correzioni:** riclassificare i rilievi in base all'effetto sull'utente; correggere solo Critical e Important, ciascuno con un test prima rosso poi verde; i Minor vanno elencati come rimandati.
6. **P5:** fermarsi con il resoconto (esito della review, correzioni, minori rimandati, decisioni prese, cosa non è stato provato) e **aspettare l'approvazione esplicita**. Le notifiche automatiche di fine lavoro dei subagenti **non** sono approvazione.
7. **P6:** `git switch dev`, `git merge --no-ff feat/<nome> -m "..."`, suite su `dev`, `git branch -d feat/<nome>`.

## 5. Da fare — dettagli

- **T12 (`feat/http-scadenze`):** `servizi_http/{__init__,app,scadenze,__main__}.py`, `dati/festivita.json`, `tests/test_scadenze.py`, `tests/test_servizi_http.py`. Logica pura `giorni_lavorativi` / `calcola_scadenza`, API FastAPI `GET /giorni-lavorativi`, `GET /scadenza`, `GET /salute`; festività nazionali italiane 2026–2027; date non valide, fuori anni, intervalli invertiti, `giorni` fuori 1–365 → 422 con messaggio in italiano. Punto d'ingresso `python -m assistente.servizi_http` (`SERVIZI_HOST` 127.0.0.1, `SERVIZI_PORT` 8000). Vedi piano T12 per le interfacce esatte.
- **T13 (stesso ramo):** `strumenti_http.py` con `giorni_lavorativi` e `calcola_scadenza` (wrapper `@tool` sincroni con `httpx`, timeout), `Config.servizi_base_url`/`servizi_timeout` (`SERVIZI_BASE_URL`, `SERVIZI_TIMEOUT`), `componi_strumenti` li aggiunge sempre, servizio Compose `servizi-http` con healthcheck HTTP reale e `depends_on: service_started`, `SERVIZI_DOCKER_URL`. Prove reali: «quanti giorni lavorativi tra il 2 e il 20 novembre 2026?», «scadenza a 10 giorni lavorativi dal 9 novembre», «che ora è?» deve restare `orologio`; servizio spento → errore alla chiamata.
- **T14 (`feat/http-catalogo`):** catalogo di ~10 corsi **fittizi** (dichiarato nel README), `GET /catalogo`, `GET /catalogo/{codice}`, strumenti `cerca_catalogo` e `dettaglio_catalogo`; ricerca senza risultati → il modello dice che non ha trovato nulla, senza inventare.
- **T15 (su `dev`):** regressione completa, tre servizi da zero, discovery MCP vera in Docker, avvio ridotto con `server-mcp` fermo e con `servizi-http` fermo, criteri di spec §8 uno per riga in `PROVE.md` con più formulazioni per tutti gli 11 strumenti, README completo, punto 5 di `CLAUDE.md` (struttura e comandi). Se il modello sbaglia lo strumento in due o più domande-tipo, **fermarsi** e riformulare le descrizioni con l'utente.

## 6. Osservazioni sul modello locale (`google/gemma-4-e2b`)

- Sceglie sempre lo strumento giusto nelle prove (nessuno scambio tra orologio, meteo, conversione, calcola, note) con 7 strumenti registrati.
- A volte emette **due chiamate identiche** nello stesso turno (innocuo per strumenti senza effetti collaterali); a volte risolve a parole senza chiamare lo strumento.
- Se uno strumento fallisce può rispondere di testa senza dirlo all'utente; non riporta nelle risposte l'ambiguità delle città dichiarata dal risultato del meteo.
- Con input da pipe, se il modello devia le righe successive si disallineano (una conferma `[s/N]` può leggere la riga sbagliata): per prove di conferma usare sequenze lineari.

## 7. Minori rimandati (nessuno è stato corretto; l'utente decide)

- **Note/MCP (T1–T7):** timeout del controllo di salute 8 s contro `MCP_TIMEOUT` 10 s (impostare `MCP_TIMEOUT: "5"` nel servizio `server-mcp`); `print` con emoji può fallire con output rediretto cp1252; Ctrl+C alla domanda `[s/N]` chiude la chat; due `build: .` costruiscono l'immagine due volte; il README non dice che la domanda mostra gli argomenti scelti dal modello.
- **Meteo (T8–T9):** `httpx.DecodingError`/`InvalidURL` non intercettati (diventano errore generico dello strumento); un 3xx è «risposta non valida»; `NaN`/`Infinity` nel JSON; `name` nullo → «None: ...»; `-0.0` come «-0 °C»; il client HTTP non viene chiuso.
- **Conversione (T10):** `float()` accetta `"1_000"` e cifre non ASCII; `valore=True` dal tool diventa 1.0; piccoli valori come `5e-05`; nota sui conteggi in `PROVE.md`.
- **Calcolatrice (T11):** `.10g` passa alla notazione scientifica sui non interi da 1e10 in su; due casi di test rifiutati per la lunghezza e non per la sintassi; `"2**100".replace(...)`; test sulle nidificazioni solo con `isinstance`; rami `bool` irraggiungibili; parser permissivo su `1_0`, `0b11`, `0x1f`.

## 8. Decisioni aperte con l'utente

- `LLM_Lez_5.pdf`: resta fuori da Git (deciso).
- Variante rispetto al PDF del corso (nota nella specifica): il PDF presenta tutte le proposte come strumenti MCP e chiede una sola integrazione MCP; qui note e meteo sono via MCP, il resto locale o FastAPI. Il requisito minimo è soddisfatto; conviene confermare la variante con il docente.
- Push di `dev` su `origin`: solo su richiesta dell'utente.

## 9. Avvertenze operative

- Ambiente: Windows 11, PowerShell e Git Bash; i file scritti da Python o da Git hanno fine riga CRLF (gli avvisi «LF will be replaced by CRLF» sono innocui). Evitare di scrivere file con `\n` dentro stringhe passate a script Python via shell: usare gli strumenti di modifica dei file per testi con backslash.
- Python 3.13 nel venv `assistente-laboratorio/.venv`; Docker 29.2.0, Compose v5.0.2; LM Studio sull'host (`google/gemma-4-e2b`).
- Convenzioni: Conventional Commits in italiano, staging selettivo, `git status` e diff prima di ogni commit, risposte e documenti in italiano.
