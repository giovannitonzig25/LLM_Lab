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
