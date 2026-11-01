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
| Server LM Studio fermato davvero e ripristinato | da completare |
