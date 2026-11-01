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
| Docker: sessione interattiva con TTY (`docker compose run --rm assistente`) | da completare |
| Server LM Studio fermato davvero e ripristinato | da completare |
