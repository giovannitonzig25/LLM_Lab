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
