# Handoff — Strumenti locali, HTTP e MCP (assistente-laboratorio)

Aggiornato il 2026-11-09, dopo la chiusura di T15 (T0–T15 tutti fatti) e del ramo di correzione `fix/input-non-valido`. Scopo: riprendere in una nuova sessione di Claude Code senza rileggere la conversazione. Non duplica specifica e piano: li richiama.

## 1. Documenti di riferimento (approvati, definitivi)

| Documento | Percorso (da `assistente-laboratorio/`) |
|---|---|
| Specifica (approvata ed emendata il 2026-11-09) | `docs/superpowers/specs/2026-11-03-strumenti-http-mcp-design.md` |
| Piano, 16 task T0–T15 | `docs/superpowers/plans/2026-11-09-strumenti-http-mcp.md` |
| Esiti delle prove reali (simulato vs provato), compresa la tabella dei criteri di §8 | `prove_reali/PROVE.md` |
| README (strumenti, avvio locale e Docker, limitazioni) e `CLAUDE.md` (struttura e comandi, punto 5 applicato) | `README.md`, `CLAUDE.md` |

## 2. Stato (verificato il 2026-11-09)

- **Git:** branch `dev` (unico oltre a `main`), **nessun push fatto** (`dev` è molto avanti a `origin/dev`), nessun merge su `main`. Albero pulito salvo `LLM_Lez_5.pdf` non tracciato (l'utente ha deciso di **non versionarlo**). Gli ultimi commit sono `a8da141` (verifica finale, README, `CLAUDE.md`), `62c8b53` (porta 8000 occupata, seconda sessione lunga), `a478cb5` (handoff dopo T15) e il merge `c2e9cc4` di `fix/input-non-valido`, più il commit di questo aggiornamento.
- **Test:** 407 passati (`.\.venv\Scripts\python.exe -m pytest -q` da `assistente-laboratorio/`, circa 40–80 s).
- **Strumenti attivi (11):** locali `orologio`, `converti_unita`, `calcola`; HTTP `giorni_lavorativi`, `calcola_scadenza`, `cerca_catalogo`, `dettaglio_catalogo`; MCP `aggiungi_nota`, `elenca_note`, `elimina_nota`, `meteo`.
- **Docker:** nessun container né volume rimasto; immagini `assistente-laboratorio-{assistente,server-mcp,servizi-http}` costruite (identiche, tre `build: .`).

| Task | Ramo | Stato | Merge su `dev` |
|---|---|---|---|
| T0 | `dev` | fatto (`8c0911f`) | — |
| T1–T7 | `feat/mcp-note` | fatto, review, approvato | `f2ff260` |
| T8–T9 | `feat/mcp-meteo` | fatto, review, approvato | `ee87be7` |
| T10 | `feat/conversione-unita` | fatto, review, approvato | `b7eb5b4` |
| T11 | `feat/calcolatrice` | fatto, review, approvato | `dd41f49` |
| T12–T13 | `feat/http-scadenze` | fatto, review, approvato | `13a7591` |
| T14 | `feat/http-catalogo` | fatto, review, approvato | `a1866a6` |
| T15 | su `dev` | fatto (`a8da141`, `62c8b53`) | — |
| fuori piano | `fix/input-non-valido` | fatto, review, approvato | `c2e9cc4` |

## 3. Decisioni finali da non rimettere in discussione

- **6 funzionalità, 11 strumenti:** locali (`converti_unita`, `calcola`), FastAPI (`giorni_lavorativi`, `calcola_scadenza`, `cerca_catalogo`, `dettaglio_catalogo`), FastMCP (`aggiungi_nota`, `elenca_note`, `elimina_nota`, `meteo`) più `orologio`.
- **MCP:** solo Streamable HTTP; ponte sincrono sopra il client FastMCP con discovery reale (`mcp_client.py`); grafo e terminale non si riscrivono.
- **Conferma di `elimina_nota`:** chiesta dal terminale (`[s/N]`) tramite `chiedi_conferma`, in base a `destructiveHint` letto dalla discovery; non è un parametro del modello. Solo un `True` esplicito vale come sì. Gli argomenti sono validati contro lo schema **prima** di chiedere conferma. Limite accettato e documentato nel README: il server da solo non protegge dalle chiamate di altri client MCP. Provata con il modello (ID 99, `n`, `s`): nessuna cancellazione senza `s`.
- **Risultati MCP:** troncati a 4000 caratteri con avviso; un risultato vuoto o non testuale diventa `(nessun contenuto testuale nel risultato)`.
- **Avvio ridotto:** `MCP_ATTESA_AVVIO` (0 in locale, 20 in Compose); `depends_on: condition: service_started` (mai `service_healthy`) per `server-mcp` e `servizi-http`. Se un servizio non riesce a partire (porta 8001 o 8000 occupata) `docker compose run --rm assistente` fallisce: usare `docker compose run --rm --no-deps assistente` (provato per entrambe le porte). Gli strumenti HTTP sono **sempre** registrati (nessuna discovery): un servizio spento dà `Errore: servizio non raggiungibile ...` alla chiamata.
- **Controlli di salute:** `server-mcp` con vera discovery (`python -m assistente.verifica_mcp`); `servizi-http` con una richiesta HTTP reale a `/salute`.
- **Servizio HTTP:** anni coperti solo 2026–2027 (festività nazionali italiane), `giorni` 1–365, errori 422 con messaggio in italiano come testo (parametri letti come stringhe); scadenze che uscirebbero dal 2027 rifiutate; risultato indicativo, non normativo. Catalogo di 10 corsi **fittizi**, ricerca per titolo/settore/sede senza maiuscole né accenti (con più parole devono comparire tutte), `q` ≤ 100 caratteri, `max_risultati` 1–10, risultati senza durata e descrizione.
- **Wrapper HTTP:** `@tool` sincroni con `httpx` e timeout (`SERVIZI_BASE_URL`, `SERVIZI_TIMEOUT`); mai eccezioni verso il modello (risposte incomplete, `nota` non testuale, URL non valido, codice vuoto → `Errore: ...`); `client` iniettabile per i test.
- **Dipendenze fissate:** `fastmcp==4.1.6`, `fastapi==0.162.2`, `uvicorn==0.54.0`, `httpx==0.28.1`. Nessuna verifica CVE fatta.
- **Strumenti locali:** `@tool` con `handle_validation_error` assegnato dopo la creazione per dare una riga d'errore chiara; descrizione in italiano con esempio.
- **Limite del modello (decisione dell'utente il 2026-11-09):** con 11 strumenti `google/gemma-4-e2b` in una sessione lunga a volte **non chiama lo strumento**; si è scelto di **documentare il limite**, senza toccare descrizioni, grafo o prompt di sistema (vedi §6).
- **Input non valido (ramo `fix/input-non-valido`, approvato dall'utente, modifica a `terminale.py` fuori dal perimetro originario del piano):** `ripulisci_input` sostituisce con U+FFFD i byte non validi in UTF-8 letti da `input()` (surrogati di `surrogateescape`) prima di inviarli al modello; un surrogato che stdin non produce diventa `?`. Il difetto è emerso nella prova interattiva con TTY di Docker (sessione caduta con `UnicodeEncodeError: '\udcc2'`); l'origine esatta del byte (`0xC2`: per esempio `«»`, `°`, spazio non separabile incollato) resta un'ipotesi. Provato in Docker con input da pipe prima/dopo; **non** provato con una sessione TTY reale.
- **Docker:** `docker compose run` non ha `--network`; `build` può dare un errore transitorio di snapshot (rieseguirlo).
- **Esecuzione:** nativa (`superpowers:executing-plans`), review indipendente a fine ramo con subagente `general-purpose` modello `fable`, **approvazione dell'utente prima di ogni merge**. Merge `git merge --no-ff -m "..."` (**non** `-F`), nessun push, nessun merge su `main`.

## 4. Procedura che ha funzionato (per eventuali nuovi rami)

1. `git status` pulito su `dev`, `git switch -c feat/<nome>`.
2. TDD: test prima, visti fallire per il motivo giusto, poi implementazione; suite completa; commit con staging selettivo e la riga `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
3. Prove reali: servizi in processi staccati (`Start-Process` con **file di script**, non `-c` con spazi) o in Docker; agente con input da pipe (`PYTHONUTF8=1`, `LM_STUDIO_BASE_URL=http://localhost:1234/v1`, `LM_STUDIO_MODEL=google/gemma-4-e2b`); verificare nei log `strumento richiesto/eseguito`. Esiti in `PROVE.md` con conteggi riletti dai log.
4. Review indipendente (prompt mirato, sola lettura, diff piccolo).
5. Riclassificare i rilievi per effetto sull'utente; correggere solo Critical e Important, ciascuno con un test prima rosso poi verde; i Minor elencati come rimandati.
6. Fermarsi con il resoconto e **aspettare l'approvazione esplicita** (le notifiche dei subagenti non lo sono).
7. `git switch dev`, `git merge --no-ff feat/<nome> -m "..."`, suite su `dev`, `git branch -d feat/<nome>`.

## 5. Da fare / decisioni aperte con l'utente

- **Ctrl+C in Docker con tutti gli 11 strumenti:** **provato dall'utente dopo il merge di `fix/input-non-valido`: «sono passate tutte»** (al prompt, durante la risposta e alla domanda `[s/N]`; esito riferito, non riletto da log, dettaglio per prova non chiesto; vedi `PROVE.md`). La procedura usata era (richiede una sessione interattiva con TTY, a cura dell'utente, con l'immagine ricostruita dopo il merge: `docker compose build`, `docker compose up -d server-mcp servizi-http`, `docker compose run --rm assistente`; Ctrl+C al prompt `Tu:` e durante la risposta, poi `docker compose down -v`; scrivere le domande a mano). Provato in Docker nelle prove iniziali con il solo orologio. Nel primo tentativo dell'utente è emerso il difetto dell'input non valido (ora corretto).
- **Push di `dev` su `origin`:** solo su richiesta dell'utente. Nessun merge su `main` senza autorizzazione.
- **`LLM_Lez_5.pdf`:** resta fuori da Git (deciso).
- **Variante rispetto al PDF del corso** (nota nella specifica): il PDF presenta tutte le proposte come strumenti MCP e chiede una sola integrazione MCP; qui note e meteo sono via MCP, il resto locale o FastAPI. Il requisito minimo è soddisfatto; conviene confermare la variante con il docente.
- **Minori rimandati (§7):** nessuno è stato corretto. **Decisione dell'utente (2026-11-09): lasciare tutti i minori com'erano**, senza correggerli; riaprire la questione solo se l'utente lo chiede.

## 6. Osservazioni sul modello locale (`google/gemma-4-e2b`)

- **Selezione:** con 7 strumenti sceglieva sempre bene. Con 11 strumenti in una sessione di 22 domande ha saltato lo strumento su **4 domande (le stesse in due sessioni distinte)**: «Quali corsi di logistica avete?», «Quanto dura il corso di design e prototipazione 3D?», «Che note ho salvato?», «Piove a Forlì?» (risposta a parole, chiedendo il codice, dalla cronologia o dicendo di non avere informazioni). Le stesse 4 domande in sessioni nuove: 12/12 corrette. Nessuno scambio tra strumenti. La causa (cronologia lunga, contenuto, posizione) **non è isolata**.
- **Cronologia al posto dello strumento:** può rielencare le note senza chiamare `elenca_note` (elenco possibilmente obsoleto) e ripetere a memoria l'esito di una cancellazione precedente invece di richiamare `elimina_nota`.
- A volte emette **due chiamate identiche** nello stesso turno (innocuo per strumenti senza effetti collaterali); a volte risolve a parole senza chiamare lo strumento.
- Se uno strumento fallisce può rispondere di testa senza dire il motivo; non riporta l'ambiguità delle città del meteo; può aggiungere frasi non fondate (es. «non tiene conto delle festività» mentre il servizio le esclude).
- Con input da pipe, se il modello devia le righe successive si disallineano (una conferma `[s/N]` può leggere la riga sbagliata): per prove di conferma usare sequenze lineari e sessioni nuove.

## 7. Minori rimandati (nessuno corretto; l'utente ha deciso il 2026-11-09 di lasciarli com'erano)

- **Note/MCP (T1–T7):** timeout del controllo di salute 8 s contro `MCP_TIMEOUT` 10 s (impostare `MCP_TIMEOUT: "5"` nel servizio `server-mcp`); `print` con emoji può fallire con output rediretto cp1252; Ctrl+C alla domanda `[s/N]` chiude la chat; tre `build: .` costruiscono l'immagine più volte; il README non dice che la domanda mostra gli argomenti scelti dal modello.
- **Meteo (T8–T9):** `httpx.DecodingError` non intercettato (diventa errore generico dello strumento); un 3xx è «risposta non valida»; `NaN`/`Infinity` nel JSON; `name` nullo → «None: ...»; `-0.0` come «-0 °C»; il client HTTP non viene chiuso.
- **Conversione (T10):** `float()` accetta `"1_000"` e cifre non ASCII; `valore=True` dal tool diventa 1.0; piccoli valori come `5e-05`.
- **Calcolatrice (T11):** `.10g` passa alla notazione scientifica sui non interi da 1e10 in su; due casi di test rifiutati per la lunghezza e non per la sintassi; test sulle nidificazioni solo con `isinstance`; rami `bool` irraggiungibili; parser permissivo su `1_0`, `0b11`, `0x1f`.
- **Servizio date/scadenze e wrapper (T12–T13):** `RequestError` diverse dal timeout (es. `DecodingError`, `TooManyRedirects`) diventano «servizio non raggiungibile»; `int()` e `date.fromisoformat` accettano `1_0`, `+5`, `20261109`, date ISO settimanali, parametri ripetuti (vale l'ultimo); `SERVIZI_PORT=abc` dà un traceback grezzo; il `httpx.Client` non viene chiuso; nessun test verifica che `componi_strumenti` passi `servizi_base_url` e `servizi_timeout`; copertura parziale di festività (6 date su 24 controllate nei test) e del caso `2027-12-31` + 1 giorno; un'asserzione sul testo «Controlla: ...» passa anche senza `loc`.
- **Catalogo (T14):** qualsiasi 404 su `/catalogo/<codice>` diventa «corso non trovato» anche se `SERVIZI_BASE_URL` punta a un altro servizio; `max_risultati` accetta `1_0`, `+5`, cifre Unicode; una `q` di soli segni diacritici dà 200 con 0 risultati; la ricerca per sottostringa («a») restituisce tutti i corsi, non documentata né testata; il wrapper scarta le righe se arriva `totale: 0` con righe presenti; due test deboli o accoppiati ai dati (`test_cerca_catalogo_dichiara_i_risultati_non_mostrati`, `test_catalogo_ricerca`).
- **Input non valido:** in esecuzione locale su Windows con stdin redirezionato (cp1252, errori `strict`) i byte 0x81, 0x8D, 0x8F, 0x90, 0x9D fanno sollevare `UnicodeDecodeError` dentro `leggi()`, non intercettato da `esegui_chat` (preesistente); `esci` seguito da un byte non valido va al modello invece di uscire; una riga di soli byte non validi diventa `�` e viene inviata; il test del testo valido non copre emoji e manca un test su `esci` con byte non validi.
- **T15:** `test_strumenti_http.py` e `test_catalogo_http.py` ricostruiscono ciascuno il proprio helper `costruisci` (duplicazione).

## 8. Avvertenze operative

- Ambiente: Windows 11, PowerShell e Git Bash; i file scritti da Python o da Git hanno fine riga CRLF (gli avvisi «LF will be replaced by CRLF» sono innocui). **Evitare** nel comando Bash heredoc con apostrofi o `\n` dentro stringhe passate a Python: usare gli strumenti di scrittura/modifica dei file (o script in file) per testi con backslash e virgolette. `Start-Process ... -ArgumentList "-c", "<codice con spazi>"` spezza gli argomenti: usare un file di script.
- Python 3.13 nel venv `assistente-laboratorio/.venv`; Docker 29.2.0, Compose v5.0.2; LM Studio sull'host (`google/gemma-4-e2b`). Il modello è lento: una sessione di 22 domande dura circa 40 minuti; i comandi in primo piano oltre 120 s vengono spostati in background.
- Convenzioni: Conventional Commits in italiano, staging selettivo, `git status` e diff prima di ogni commit, risposte e documenti in italiano.
