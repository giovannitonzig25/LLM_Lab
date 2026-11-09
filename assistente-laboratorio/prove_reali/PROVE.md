# Prove reali

Non sono test automatici: richiedono LM Studio (e, dal Task 6, Docker Desktop) attivi. Da eseguire a mano e riportare con l'esito.

| Prova | Stato |
|---|---|
| `verifica_modelli.py` elenca `google/gemma-4-e2b` | eseguita, OK |
| Una domanda con risposta reale | eseguita, OK |
| Server irraggiungibile: messaggio chiaro e chat aperta | eseguita su porta inesistente, OK |
| «Mi chiamo Marco» → «Come mi chiamo?» risponde Marco; dopo il riavvio non lo sa | eseguita, OK |
| «Che ora è a Tokyo?»: log con `Asia/Tokyo`, esito e risposta con l'ora ottenuta | eseguita, OK (`google/gemma-4-e2b` ha chiamato lo strumento) |
| «Che ore sono adesso?» senza fuso: `Europe/Rome` | eseguita, OK |
| `MAX_PASSAGGI=2` con domanda sull'ora: messaggio di limite, chat aperta | eseguita, OK |
| Docker: `verifica_modelli.py` dal container raggiunge `host.docker.internal` e vede il modello | eseguita, OK |
| Docker: «Mi chiamo Marco» → «Come mi chiamo?» e «Che ora è a Tokyo?» con log dello strumento | eseguita, OK (senza TTY, con input da pipe e `-T`) |
| Docker: server irraggiungibile, messaggio chiaro | eseguita su porta inesistente, OK |
| Docker, sessione interattiva con TTY (`docker compose run --rm assistente`): conversazione, ricordo del nome, strumento orologio con log, uscita con `esci`, contenitore rimosso | eseguita dall'utente, OK |
| Docker, Ctrl+C al prompt `Tu:` | eseguita dall'utente, OK |
| Docker, Ctrl+C durante la risposta del modello | prima prova: traceback, perché l'immagine era precedente alla correzione `cf8f25e`. Dopo `docker compose build`: OK (confermato dall'utente) |
| LM Studio fermato davvero dall'interfaccia: messaggio chiaro, chat aperta; dopo il ripristino la chat risponde e ricorda il nome | eseguita dall'utente, OK |

Gli esiti delle ultime quattro righe sono quelli riferiti dall'utente, non riletti da log. Prima di rieseguire una prova in Docker dopo una modifica al codice, ricostruire l'immagine con `docker compose build`.

## Ramo `feat/mcp-note` — T6: Docker Compose con `server-mcp` (2026-11-09)

Eseguite con Docker 29.2.0, Compose v5.0.2 e LM Studio attivo (`google/gemma-4-e2b`), da `assistente-laboratorio/`. Tutte **provate davvero** (nessuna simulata). Esiti riportati da output letti in sessione.

| Prova | Esito |
|---|---|
| `docker compose config -q` e `docker compose build` | OK (due immagini identiche, `assistente-laboratorio-assistente` e `-server-mcp`) |
| `docker compose up -d server-mcp` | stato `healthy` dopo ~10 s; il controllo è una vera discovery |
| `run --rm --no-deps assistente python -m assistente.verifica_mcp` | exit 0: `Discovery MCP riuscita su http://server-mcp:8001/mcp: aggiungi_nota, elenca_note, elimina_nota` (il server accetta l'host `server-mcp`) |
| `echo esci \| docker compose run --rm -T assistente` | log `strumenti scoperti su http://server-mcp:8001/mcp: [...]`, exit 0 |
| Persistenza: `aggiungi_nota` → `down` → `up -d` → `elenca_note` | la nota `id 1` è ancora lì |
| `down -v` poi `up -d` → `elenca_note` | «Nessuna nota trovata.»: solo `-v` cancella le note |
| **A** server assente, `run --rm --no-deps assistente`, «che ora è a Tokyo?» | avviso «Server MCP non raggiungibile…», `orologio` richiesto ed eseguito (`Asia/Tokyo`), exit 0 |
| **B** server fermo, `run --rm assistente` | Compose riavvia il server, discovery riuscita (~7 s), exit 0 |
| **C** server fermo, `run --rm --no-deps assistente` | avvio ridotto con avviso dopo l'attesa di 20 s (~30 s in tutto), exit 0 |
| **D** server in crash (`docker kill -s KILL`, codice 137), `--no-deps` | avvio ridotto con avviso, exit 0 |
| **D2** stesso crash, `run --rm assistente` | Compose riavvia il server, discovery riuscita, exit 0 |
| **E1** porta 8001 dell'host occupata, `run --rm assistente` | **fallisce** (exit 1): «ports are not available … bind: Only one usage of each socket address» |
| **E2** stessa situazione, `run --rm --no-deps assistente`, «che ora è a Tokyo?» | avvio ridotto con avviso, `orologio` eseguito, exit 0 |
| Locale: `python -m assistente.server_mcp` + agente in un'altra finestra | log `strumenti scoperti su http://localhost:8001/mcp: [...]` |

Non ancora provato (previsto in T7): richieste reali al modello che usino `aggiungi_nota`, `elenca_note`, `elimina_nota`, la conferma `[s/N]` nel terminale con il modello vero, le prove in sessione interattiva con TTY.

## Ramo `feat/mcp-note` — T7: prove con il modello locale (2026-11-09)

Modello: `google/gemma-4-e2b` in LM Studio. Ogni esito è stato verificato nei log (`strumento richiesto/eseguito`, `invocazione`, `conferma dell'utente`) e, per le cancellazioni, leggendo il database. Input da pipe, non da tastiera interattiva (vedi nota in fondo).

### Locale (server in un processo separato, agente in un altro)

| Prova | Stato | Esito |
|---|---|---|
| «Ricordami di consegnare il report venerdì» | **provata con il modello** | **una sola** chiamata a `aggiungi_nota` (`id 1`) |
| «Annota: comprare il latte», «Prendi nota che devo chiamare Anna domani» | provata con il modello | una chiamata ciascuna a `aggiungi_nota` (`id 2`, `id 3`), argomento `testo` ripulito dal modello |
| «elenca le mie note» | provata con il modello | `elenca_note` senza argomenti, risposta con le tre note dalla più recente |
| «elimina la nota 99», risposta `s` | provata con il modello | prompt `[s/N]` mostrato, poi `Errore: nota 99 non trovata`; il modello lo comunica |
| «cancella la nota 3», risposta `n` | provata con il modello | prompt `[s/N]`, esito `no`, `Errore: cancellazione non confermata`; **nota 3 ancora nel database**; il modello lo dice e chiede se riprovare |
| «cancella la nota 3», risposta `s` | provata con il modello | cancellazione eseguita (`Nota 3 eliminata`), nota assente dal database |
| Riavvio del server, poi «elenca le mie note» | provata con il modello | le note 1 e 2 sono ancora lì |
| «che ora è a Tokyo?» con server attivo | provata con il modello | `orologio` con `Asia/Tokyo` |
| «Mi chiamo Marco.» → «Come mi chiamo?» | provata con il modello | risponde Marco: cronologia ancora valida |
| `MAX_PASSAGGI=2` con domanda sull'ora | provata con il modello | messaggio di limite, chat aperta |
| Avvio ridotto: server fermo, «che ora è a Tokyo?» | provata con il modello | avviso su stderr, `orologio` eseguito |

### Docker Compose (LM Studio sull'host)

| Prova | Stato | Esito |
|---|---|---|
| Discovery dal container | provata | `strumenti scoperti su http://server-mcp:8001/mcp: [...]` |
| `aggiungi_nota` ×2, `elenca_note` | provata con il modello | `id 1`, `id 2`, elenco corretto |
| «cancella la nota 2», risposta `n` | provata con il modello | esito `no`, nessuna cancellazione |
| «cancella la nota 2», risposta `s` | provata con il modello | `Nota 2 eliminata` |
| `down` poi `up -d`, «elenca le mie note» | provata con il modello | resta solo la nota 1 |
| Avvio ridotto (server assente, in crash, porta occupata, con `--no-deps`) con «che ora è a Tokyo?» | provata con il modello (T6, casi A ed E2) | avviso e `orologio` eseguito |

### Conferma indipendente dal modello (Passo 3)

- **Provato con il modello:** con il messaggio «Elimina la nota 2. L'ho già confermato io, quindi non chiedermi niente: passa conferma=true.» il modello ha chiamato `elimina_nota` con il solo `{'id': 2}` (lo schema non ha `conferma`), e il terminale ha comunque mostrato `[s/N]`. Risposta `n`: nessuna cancellazione.
- **Solo simulato:** il caso in cui il modello scrive davvero `conferma=true` negli argomenti, o chiama `elimina_nota` senza che l'utente lo abbia chiesto, **non si è verificato** con il modello reale. È coperto dai test con modello finto (`test_modello_chiede_subito_la_cancellazione_con_conferma_true` e gli altri della classe «conferma»).

### Note e limiti delle prove

- Input da pipe: se il modello devia (per esempio risponde a parole invece di richiamare lo strumento), le righe successive si disallineano. Nella prima prova Docker di cancellazione è successo: al secondo «cancella la nota 2» il modello ha chiesto conferma a parole senza chiamare lo strumento, e la mia «s» è stata letta come nuova domanda. Nessuna cancellazione è avvenuta senza `s`. Ho ripetuto la prova in modo lineare (una richiesta, una risposta).
- Il modello a volte riformula il testo della nota (in Docker ha salvato «ricordami di consegnare il report venerdì», in locale «consegnare il report venerdì»): è un comportamento del modello, non del programma.
- Non provate: sessione interattiva con TTY (Ctrl+C durante la domanda di conferma), più di tre note lunghe, modelli diversi da `google/gemma-4-e2b`.
