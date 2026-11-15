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

## Ramo `feat/mcp-meteo` — T9: prove del meteo (2026-11-09)

Modello `google/gemma-4-e2b` in LM Studio, Open-Meteo **reale** (nessuna simulazione), Docker 29.2.0. Ogni esito verificato nei log (`strumento richiesto/eseguito`). Input da pipe.

### Locale (server MCP in un processo separato)

| Domanda | Stato | Strumento scelto e risultato |
|---|---|---|
| «Che tempo fa a Bologna?» | **provata con il modello** | `meteo {'citta': 'Bologna'}` → `10.4 °C, coperto, rilevato il 2026-11-09 11:30`; il modello riferisce temperatura, condizioni e ora |
| «Piove a Forlì?» | provata con il modello | `meteo {'citta': 'Forlì'}` (accento corretto); la risposta riporta temperatura e «coperto» ma **non dice esplicitamente se piove** |
| «Com'è il meteo a San Donà di Piave?» | provata con il modello | `meteo {'citta': 'San Donà di Piave'}` (nome con spazi e accento), nessun altro candidato |
| «Serve l'ombrello oggi a Bologna?» | provata con il modello | `meteo`; il modello nota l'assenza di precipitazioni e suggerisce prudenza |
| «Dimmi la temperatura a Roma.» | provata con il modello | `meteo {'citta': 'Roma'}` |
| «Che ora è a Tokyo?», «Che ore sono adesso?» | provata con il modello | `orologio`, **mai** `meteo` (nessuno scambio tra i due) |
| «Che tempo fa ad Atlantideville123?» | provata con il modello | `Errore: città non trovata: 'Atlantideville123'`; il modello lo dice e chiede se il nome è sbagliato, senza inventare dati |
| Rete assente (server avviato con `HTTPS_PROXY` su una porta chiusa), «Che tempo fa a Bologna?» | provata con il modello | `Errore: rete non disponibile: impossibile raggiungere il servizio meteo` (distinto da «città non trovata»); il modello parla di problema di connessione; `orologio` funziona ancora |

Totale: 9 domande sul meteo (7 con rete, 1 città inesistente, 1 senza rete), 3 sull'ora; nessuna scelta di strumento sbagliata.

### Docker

| Prova | Stato | Esito |
|---|---|---|
| Open-Meteo raggiungibile dal container `server-mcp` | provata | `leggi_meteo('Bologna')` → risultato reale |
| Container **senza rete** (`docker run --network none`) | provata | `rete non disponibile: impossibile raggiungere il servizio meteo` |
| Agente in Docker con il modello: «Che tempo fa a Bologna?», «Piove a Forlì?», «Che ora è a Tokyo?» | provata con il modello | `meteo`, `meteo`, `orologio`; discovery con 4 strumenti |
| Regressione note in Docker: «Ricordami di comprare il pane», «elenca le mie note» | provata con il modello | `aggiungi_nota` (`id 1`), `elenca_note` |

### Note

- Il risultato dichiara le città ambigue («Altri luoghi con lo stesso nome: almeno 4 (ho usato il primo)»), ma il modello **non lo riporta all'utente** nelle sue risposte: l'informazione è nel risultato dello strumento e nei log, non nel testo finale.
- Con `count=5` il numero di candidati è un minimo («almeno N»): il messaggio è stato corretto dopo averlo visto con l'API vera.
- `docker compose run` non ha `--network`: per il container senza rete si è usato `docker run --network none` sull'immagine già costruita. Un primo `docker compose build` ha dato un errore transitorio di snapshot di Docker; il secondo è andato a buon fine.
- Non provato: Ctrl+C durante una chiamata al meteo, risposte molto lente di Open-Meteo (il timeout è coperto solo dai test simulati), altri modelli.

## Ramo `feat/conversione-unita` — T10: `converti_unita` (2026-11-09)

Modello `google/gemma-4-e2b`, con **tutti** gli strumenti registrati (orologio, converti_unita e i quattro MCP, server attivo). Esiti verificati nei log. Input da pipe.

| Domanda | Stato | Strumento e risultato |
|---|---|---|
| «Quanti chilometri sono 10 miglia?» | **provata con il modello** | `converti_unita {valore: 10, da: 'mi', a: 'km'}` → `10 mi = 16.0934 km` |
| «100 gradi Fahrenheit in Celsius» | provata con il modello | `{100, 'F', 'C'}` → `100 F = 37.7778 C` |
| «Converti 5 libbre in chilogrammi» | provata con il modello | `{5, 'lb', 'kg'}` → `5 lb = 2.268 kg` |
| «Quanti litri sono 2 galloni?» | provata con il modello (due volte) | `{2, 'gal', 'l'}` → `2 gal = 7.5708 l` |
| «Quanti centimetri sono 6 piedi?» | provata con il modello | `{6, 'ft', 'cm'}` → `6 ft = 182.88 cm` |
| «Quanti gradi Celsius sono 300 Kelvin?» | provata con il modello | `{300, 'K', 'C'}` → `300 K = 26.85 C` |
| «Che ora è a Tokyo?» (controllo) | provata con il modello | `orologio`, non `converti_unita` |
| «Che tempo fa a Bologna?» (controllo) | provata con il modello | `meteo`, non `converti_unita` |
| «Usa lo strumento converti_unita per convertire 10 km in kg.» | provata con il modello | `Errore: unità incompatibili: km è lunghezza, kg è massa. Unità ammesse - ...`; il modello lo spiega correttamente |
| «Quanti gradi Fahrenheit sono -300 Celsius?» | provata con il modello | `Errore: temperatura sotto lo zero assoluto: -300 C`; il modello lo spiega |
| Docker: «Quanti chilometri sono 10 miglia?», «Che ora è a Tokyo?», «Ricordami di comprare il pane» | provata con il modello | `converti_unita`, `orologio`, `aggiungi_nota`; regressione nulla |

Totale: 11 domande di conversione poste, di cui 9 con chiamata a `converti_unita` (7 riuscite, 2 con errore atteso) e 2 risolte a parole senza chiamata (vedi note); 2 controlli su altri strumenti; nessuna scelta di strumento sbagliata.

### Note

- **Due chiamate identiche:** in una sessione «Quanti litri sono 2 galloni?» ha prodotto **due** richieste di `converti_unita` con gli stessi argomenti (stesso risultato); nella ripetizione una sola. Comportamento del modello, non del programma; innocuo (strumento senza effetti collaterali).
- **Il modello a volte non chiama lo strumento:** «Quanti chilogrammi sono 10 chilometri?» e «Converti 5 parsec in chilometri» sono state risolte a parole, senza chiamata, con risposte corrette (unità incompatibili / non supportata). I percorsi d'errore reali sono stati esercitati chiedendo esplicitamente lo strumento o con la temperatura sotto lo zero assoluto.
- Il modello riporta il risultato con la precisione dello strumento (4 decimali).
- Non provato: unità scritte in forme non previste (es. «chilometri», «celsius», «litro»): lo strumento le rifiuta elencando quelle ammesse; il modello ha sempre usato i simboli corretti nelle prove, ma con altri modelli potrebbe non farlo.

## Ramo `feat/calcolatrice` — T11: `calcola` (2026-11-09)

Modello `google/gemma-4-e2b`, con tutti gli strumenti registrati (orologio, converti_unita, calcola e i quattro MCP, server attivo). Esiti verificati nei log. Input da pipe.

| Domanda | Stato | Strumento e risultato |
|---|---|---|
| «Quanto fa 17 per 23 più 5?» | **provata con il modello** | `calcola {'espressione': '17*23+5'}` → `396` |
| «Calcola (12+8)*3» | provata con il modello | `calcola '(12+8)*3'` → `60` (la chiamata è comparsa **due volte** identica) |
| «Quanto fa 2 elevato alla 10?» | provata con il modello | `calcola '2**10'` → `1024` (il modello ha scritto `**`) |
| «Quanto fa 15 diviso 4?» | provata con il modello | `calcola '15/4'` → `3.75` |
| «Quanto fa il 20% di 350?» | provata con il modello | `calcola '0.20*350'` → `70` |
| «Quanto fa 7 per 6?» | provata con il modello | `calcola '7*6'` → `42` |
| «Usa lo strumento calcola per calcolare 100/0» | provata con il modello | `Errore: divisione per zero`; il modello lo riferisce |
| «Quanto fa 2 elevato alla 1000?» | provata con il modello | `Errore: esponente troppo grande (al massimo 100)`; il modello lo spiega |
| «Calcola il valore assoluto di -5 e poi la radice quadrata di 16» | provata con il modello | 4 chiamate tutte in errore: `'valore assoluto di -5'` e `'radice quadrata di 16'` (testo, «espressione non valida»), poi `abs(-5)` e `sqrt(16)` («le funzioni non sono ammesse»); alla fine il modello risponde **a mente** (5 e 4, corretti) **senza dire che lo strumento non ci è riuscito** |
| «Che ora è a Tokyo?» / «Quanti km sono 10 miglia?» / «Che tempo fa a Bologna?» (controlli) | provata con il modello | `orologio` / `converti_unita` / `meteo`, mai `calcola` |
| Docker: «Quanto fa 17 per 23 più 5?», «Quanti km sono 10 miglia?», «Ricordami di comprare il pane» | provata con il modello | `calcola` → `396`, `converti_unita`, `aggiungi_nota`; regressione nulla |

Totale: 10 domande di calcolo in due sessioni, 9 con chiamata a `calcola` (6 riuscite, 2 con errore atteso, 1 senza risultato per sintassi non ammessa) e 1 risolta a parole senza chiamata («Quanto fa 100 diviso 0?»: «La divisione per zero è indefinita»). Nessuna scelta di strumento sbagliata.

### Note

- **Chiamata doppia:** come per `converti_unita`, una domanda ha prodotto due chiamate identiche in uno stesso turno. Innocuo (nessun effetto collaterale), ma è la seconda volta che accade con questo modello.
- **Funzioni non ammesse:** la calcolatrice rifiuta `abs()`, `sqrt()` e simili per scelta (solo numeri, `+ - * / **`, parentesi). Il modello le prova comunque e, se falliscono, tende a rispondere di testa senza avvisare l'utente. È un limite noto del piano, non un difetto del codice.
- **Percentuali:** il modello ha tradotto «20% di 350» in `0.20*350` da solo.
- Il modello a volte non chiama lo strumento (100/0 la prima volta): risposta corretta, ma il percorso d'errore dello strumento è stato esercitato chiedendolo esplicitamente.
- Non provato: operazioni con numeri molto grandi (oltre 1e15) tramite il modello, espressioni lunghe vicine ai 200 caratteri, altri modelli.

## Ramo `feat/http-scadenze` — T12–T13: servizio FastAPI e strumenti HTTP (2026-11-09)

Modello `google/gemma-4-e2b`, strumenti registrati: orologio, converti_unita, calcola, `giorni_lavorativi`, `calcola_scadenza` (HTTP, sempre presenti) e, in Docker, i quattro MCP. Esiti riletti dai log (`strumento richiesto/eseguito`, `assistente.http`). Input da pipe, una domanda per riga. Nei log una sola richiesta di strumento per domanda (conteggio riletto: 4 richieste per 4 domande nella prima sessione, 7 per 7 nella seconda).

### Locale (servizio con `python -m assistente.servizi_http` in un processo separato, MCP spento)

| Domanda | Stato | Strumento e risultato |
|---|---|---|
| «Quanti giorni lavorativi ci sono tra il 2 e il 20 novembre 2026?» | **provata con il modello** | `giorni_lavorativi` (2026-11-02, 2026-11-20) → 15 |
| «Calcola la scadenza a 10 giorni lavorativi dal 9 novembre 2026.» | provata con il modello | `calcola_scadenza` (2026-11-09, 10) → 2026-11-23 |
| «Che ora è?» | provata con il modello | `orologio`, non `giorni_lavorativi` |
| «Tra il 24 dicembre 2026 e il 28 dicembre 2026 quanti giorni lavorativi ci sono?» | provata con il modello | `giorni_lavorativi` → 2 (Natale e Santo Stefano esclusi) |
| «Dal 1 al 31 gennaio 2027 quanti giorni si lavora, escluse le feste?» | provata con il modello | `giorni_lavorativi` → 19 (1 e 6 gennaio esclusi) |
| «Se un documento va consegnato entro 5 giorni lavorativi dal 24 dicembre 2026, quando scade?» | provata con il modello | `calcola_scadenza` → 2027-01-04 (verificato a mano) |
| «Che giorno e che ora è a Tokyo?» (controllo) | provata con il modello | `orologio` Asia/Tokyo |
| «Quanto fa 17 per 23 più 5?» / «Quanti chilometri sono 10 miglia?» (controlli) | provata con il modello | `calcola` → 396 / `converti_unita` → 16.0934 km |
| «Quanti giorni lavorativi tra il 20 febbraio 2025 e il 3 marzo 2025?» (anno non coperto) | provata con il modello | `Errore: Parametro 'da' fuori dagli anni coperti: sono ammessi solo il 2026 e il 2027.`; il modello lo riferisce e dice di non poter calcolare |
| «Scadenza a 400 giorni lavorativi dal 9 novembre 2026» | provata con il modello | `Errore: Parametro 'giorni' fuori intervallo: sono ammessi da 1 a 365.`; il modello lo riferisce |
| Servizio spento: «Quanti giorni lavorativi tra il 2 e il 20 novembre 2026?» | provata con il modello | `Errore: servizio non raggiungibile su http://localhost:8000`; il modello risponde con scuse generiche («errore durante l'esecuzione») senza dire il motivo; la chat prosegue («Che ora è?» → `orologio`) |

Totale: 8 domande sulle date, tutte con la chiamata allo strumento HTTP giusto (5 riuscite, 2 con errore atteso del servizio, 1 con servizio spento, quest'ultima in una sessione a parte), più 4 controlli su altri strumenti (`orologio` due volte, `calcola`, `converti_unita`) sempre con lo strumento giusto. Nessuna scelta sbagliata.

### Docker Compose (LM Studio sull'host)

- `docker compose build` ok (tre immagini identiche, `build: .` ripetuto); `up -d server-mcp servizi-http`: entrambi `healthy` dopo ~25 s (il controllo di `servizi-http` è una richiesta HTTP reale a `/salute`).
- `docker compose run --rm -T assistente` con input da pipe: discovery `['aggiungi_nota', 'elenca_note', 'elimina_nota', 'meteo']`; «giorni lavorativi tra il 2 e il 20 novembre 2026» → `giorni_lavorativi` → 15; «scadenza a 10 giorni lavorativi dal 9 novembre 2026» → `calcola_scadenza` → 2026-11-23. Regressione MCP: solo la discovery è stata verificata, nessuno strumento MCP è stato invocato in questa prova. La terza domanda («Che ora è?») non ha avuto risposta perché ho interrotto la prova a 110 s (il modello è lento): non è un errore.
- `docker compose stop servizi-http` poi `docker compose run --rm --no-deps -T assistente`: `giorni_lavorativi` → `Errore: servizio non raggiungibile su http://servizi-http:8000`. Prova interrotta a 110 s dopo l'esito dello strumento: la risposta finale del modello non è stata letta in Docker (letta nella prova locale equivalente).
- Pulizia: `docker compose down -v`; nessun container, volume o processo in ascolto su 8000/8001.

### Note

- **Simulato, non provato con il modello:** timeout del servizio (solo `httpx.MockTransport`), risposte non valide, 404/500, argomenti di tipo sbagliato; `python -m assistente.servizi_http` con `SERVIZI_HOST`/`SERVIZI_PORT` non predefiniti fuori da Docker (in Docker `SERVIZI_HOST=0.0.0.0` provato).
- **Servizio spento:** il modello non dice all'utente che il servizio non è raggiungibile (scusa generica); già osservato con altri strumenti (handoff, §6).
- **Anni coperti:** il servizio rifiuta date fuori 2026–2027 e scadenze che uscirebbero dal 2027 (festività non note): scelta di progetto, non un difetto.
- Non provato: altri modelli; invocazione di strumenti MCP in questo ramo (provata in T7–T9); avvio ridotto con `server-mcp` fermo in questo ramo (provato in T7); `servizi-http` fermo con `run` senza `--no-deps` (Compose lo riavvia come dipendenza).

## Ramo `feat/http-catalogo` — T14: catalogo di corsi fittizi (2026-11-09)

Modello `google/gemma-4-e2b`, 11 strumenti HTTP+locali+MCP nel caso Docker (orologio, converti_unita, calcola, giorni_lavorativi, calcola_scadenza, cerca_catalogo, dettaglio_catalogo e i quattro MCP); in locale 7 strumenti (MCP spento). Esiti riletti dai log (`strumento richiesto/eseguito`). Input da pipe, una domanda per riga.

### Locale (servizio con `python -m assistente.servizi_http` in un processo separato)

| Domanda | Stato | Strumento e risultato |
|---|---|---|
| «Che corsi ci sono a Udine?» | **provata con il modello** | `cerca_catalogo {'query': 'Udine'}` → 4 corsi (ITS-001, 003, 005, 010); elenco riportato fedelmente |
| «Dimmi la durata del corso ITS-003.» | provata con il modello | `dettaglio_catalogo {'codice': 'ITS-003'}` → 1600 ore |
| «Cerca corsi di meccatronica.» | provata con il modello | `cerca_catalogo 'meccatronica'` → 2 corsi (ITS-004, 005) |
| «Che corsi di informatica ci sono a Pordenone e quanto dura quello?» | provata con il modello | **due passaggi nei log:** `cerca_catalogo 'informatica Pordenone'` (1 corso) poi `dettaglio_catalogo 'ITS-002'`; risposta: 1800 ore |
| «Ci sono corsi di astrofisica?» | provata con il modello | `cerca_catalogo 'astrofisica'` → `Nessun corso trovato per 'astrofisica'.`; il modello: «Non sono stati trovati corsi relativi a "astrofisica" nel catalogo», **senza inventare** |
| «Dammi i dettagli del corso ITS-999.» | provata con il modello | `Errore: corso ITS-999 non trovato`; il modello dice che il corso non esiste |
| «Quanti giorni lavorativi ci sono tra il 2 e il 20 novembre 2026?» / «Che ora è?» (controlli) | provata con il modello | `giorni_lavorativi` → 15 / `orologio`; mai gli strumenti del catalogo |
| «Quali corsi di logistica avete?» | provata con il modello | `cerca_catalogo 'logistica'` → ITS-006 |
| «Parlami del corso ITS-007.» | provata con il modello | `dettaglio_catalogo 'ITS-007'`; dati riportati fedelmente (Agroalimentare, Gorizia, 1600 ore) |
| «Quanto dura il corso di design e prototipazione 3D?» | provata con il modello | **due passaggi:** `cerca_catalogo 'design e prototipazione 3D'` poi `dettaglio_catalogo 'ITS-010'` → 1700 ore |
| «Elencami i corsi che ci sono a Trieste.» | provata con il modello | `cerca_catalogo 'Trieste'` → ITS-006, ITS-008 |
| «Quanto fa 17 per 23 più 5?» (controllo) | provata con il modello | `calcola '17*23+5'` → 396 |

Totale: 10 domande sul catalogo in due sessioni (6 + 4) e 3 controlli su altri strumenti. Richieste al catalogo rilette dai log: 7 nella prima sessione e 5 nella seconda, cioè una per domanda più il secondo passo dei due casi a due tempi. Tutte allo strumento giusto, nessuna scelta sbagliata tra catalogo, date, orologio e calcola. I due casi d'errore (nessun risultato, codice inesistente) sono stati riferiti correttamente dal modello. Nessun tentativo di inventare corsi.

### Docker Compose

- `docker compose build` ok; `up -d server-mcp servizi-http`: entrambi `healthy`.
- `docker compose run --rm -T assistente`: discovery MCP `['aggiungi_nota', 'elenca_note', 'elimina_nota', 'meteo']`; «Che corsi ci sono a Udine?» → `cerca_catalogo` (4 corsi); «Dimmi la durata del corso ITS-003.» → `dettaglio_catalogo` (1600 ore); regressione MCP: «Ricordami di preparare la lezione di venerdì» → `aggiungi_nota` (id 1), «Elenca le mie note» → `elenca_note`. Le 4 domande hanno avuto risposta.
- Pulizia: `docker compose down -v`; nessun container, volume o processo in ascolto su 8000/8001.

### Note

- **Simulato, non provato con il modello:** servizio spento e risposte non valide per gli strumenti del catalogo (solo `httpx.MockTransport`; con il modello il servizio spento era stato provato in T13 per gli strumenti delle date), `max_risultati` oltre il limite, `q` troppo lungo, codice con caratteri speciali (`../salute`, codificato nel percorso), accenti nella ricerca (testato su dati finti).
- **Dichiarazione «fittizi»:** il servizio la include in ogni risposta e il wrapper la riporta; nelle risposte del modello compare di solito («i corsi sono fittizi»), ma in una risposta (Docker) è stata abbreviata in «Il catalogo è di esempio».
- **Il modello a volte aggiunge commenti propri** (per esempio «Ti consiglio di verificare i dettagli di questo corso»): innocui, non inventano dati.
- Non provato: altri modelli, catalogo con molti più corsi, `max_risultati` scelto dal modello.

## T15 — Verifica finale dell'agente completo, su `dev` (2026-11-09)

`dev` all'ultimo merge `a1866a6`, 403 test automatici verdi. Modello `google/gemma-4-e2b`, LM Studio sull'host, Docker 29.2.0, Compose v5.0.2. Tutte le prove di questa sezione sono in **Docker Compose**, con **tutti gli 11 strumenti registrati insieme** (orologio, converti_unita, calcola, giorni_lavorativi, calcola_scadenza, cerca_catalogo, dettaglio_catalogo, aggiungi_nota, elenca_note, elimina_nota, meteo). Esiti riletti dai log (`strumento richiesto/eseguito`, `strumenti scoperti`). Input da pipe con `docker compose run --rm -T assistente`.

### Preparazione da zero

`docker compose down -v`, `docker compose build`, `up -d server-mcp servizi-http`: entrambi `healthy` dopo ~25 s. `docker compose run --rm --no-deps assistente python -m assistente.verifica_mcp` → exit 0, `Discovery MCP riuscita su http://server-mcp:8001/mcp: aggiungi_nota, elenca_note, elimina_nota, meteo`.

### Batteria da 22 domande in una sessione (due formulazioni per strumento)

| Strumento | Domande | Esito con il modello |
|---|---|---|
| `orologio` | «Che ore sono a Tokyo?», «Che ora è a New York?» | 2/2 (`Asia/Tokyo`, `America/New_York`) |
| `converti_unita` | «Quanti chilometri sono 10 miglia?», «Quanti gradi Celsius sono 100 gradi Fahrenheit?» | 2/2 |
| `calcola` | «Quanto fa 17 per 23 più 5?», «Calcola (12+8)*3.» | 2/2 |
| `giorni_lavorativi` | 2–20 novembre 2026; gennaio 2027 | 2/2 (15 e 19) |
| `calcola_scadenza` | 10 giorni dal 9 novembre 2026; 5 giorni dal 24 dicembre 2026 | 2/2 |
| `cerca_catalogo` | «Che corsi ci sono a Udine?»; «Quali corsi di logistica avete?» | 1/2: **la seconda non ha chiamato nessuno strumento** |
| `dettaglio_catalogo` | «Dimmi la durata del corso ITS-003.»; «Quanto dura il corso di design e prototipazione 3D?» | 1/2: **la seconda non ha chiamato nessuno strumento** (ha chiesto il codice) |
| `aggiungi_nota` | «Ricordami di consegnare il report venerdì.»; «Segna questa nota: chiamare il fornitore.» | 2/2 |
| `elenca_note` | «Elenca le mie note.»; «Che note ho salvato?» | 1/2: **la seconda risolta dalla cronologia, senza chiamare lo strumento** |
| `meteo` | «Che tempo fa a Bologna?»; «Piove a Forlì?» | 1/2: **la seconda senza chiamata** («non ho informazioni sul meteo») |

Totale: 22 domande, 18 con lo strumento giusto, **4 senza alcuna chiamata** (le domande 14, 16, 20 e 22 della sessione), **0 scambi tra strumenti** (nessuno strumento sbagliato chiamato). 16 richieste di strumento nella sessione.

**Ripetizione delle 4 domande mancate** (3 volte ciascuna, ogni volta in una **sessione nuova** con una sola domanda, 11 strumenti, due note preparate nel server): logistica → `cerca_catalogo` 3/3; design 3D → `cerca_catalogo` poi `dettaglio_catalogo` (ITS-010) 3/3; «Che note ho salvato?» → `elenca_note` 3/3; «Piove a Forlì?» → `meteo` 3/3. **12/12.**

**Seconda sessione lunga** (stessa sequenza di 22 domande, sessione nuova, servizi ricreati): 18 corrette e **le stesse 4 domande senza chiamata** (logistica, design 3D, «Che note ho salvato?», «Piove a Forlì?»); 16 richieste di strumento, 0 scambi. Il difetto è quindi **riproducibile** nella sessione lunga e non casuale; resta non isolato se dipenda dalla lunghezza della cronologia, dal suo contenuto o dalla posizione delle domande.

Lettura (decisione dell'utente il 2026-11-09: **limite documentato**, nessuna modifica a descrizioni, grafo o prompt): con le stesse descrizioni il modello sceglie lo strumento giusto in sessioni nuove, mentre in una sessione lunga ha saltato lo strumento 4 volte su 22 e anche altrove (vedi sotto). I dati (due sessioni lunghe con le stesse 4 mancanze, 12/12 corrette in sessioni nuove) sono coerenti con un effetto della cronologia lunga, ma **non è stato isolato** (non è stata variata la lunghezza né l'ordine delle domande).

### Conferma di `elimina_nota` con il modello (sequenza lineare di input)

| Passo | Esito |
|---|---|
| «Elimina la nota 99.» → `[s/N]` → `s` | `elimina_nota {'id': 99}` → `Errore: nota 99 non trovata`; il modello: «Non ho trovato la nota con l'ID 99.» |
| «Cancella la nota 2.» → `[s/N]` → `n` | la chiamata al server non parte: `Errore: cancellazione non confermata dall'utente`; la nota esiste ancora («Elenca le mie note» le mostra entrambe) |
| «Elimina la nota 2.» (stessa sessione, dopo il rifiuto) | **il modello non ha chiamato lo strumento**: ha ripetuto a memoria «Non sono riuscito a eliminare la nota 2 perché non è stata confermata»; il successivo `s` è stato letto come domanda normale (disallineamento già noto con l'input da pipe). Nessuna cancellazione senza conferma |
| Sessione nuova: «Elimina la nota 2.» → `[s/N]` → `s` | `elimina_nota {'id': 2}` → `Nota 2 eliminata`; «Elenca le mie note» mostra solo la nota 1 |

La conferma è sempre arrivata dal terminale, mai dal modello; nessuna cancellazione è avvenuta senza `s`.

### Avvio ridotto sul Compose a tre servizi

- **A. `server-mcp` in crash** (`docker kill -s KILL`, exit 137), `servizi-http` attivo, `docker compose run --rm --no-deps -T assistente`: avviso «Server MCP non raggiungibile su http://server-mcp:8001/mcp ... Riavvia l'agente quando il server è attivo»; «Che ora è a Tokyo?» → `orologio`; «giorni lavorativi tra il 2 e il 20 novembre 2026» → `giorni_lavorativi` → 15 (gli strumenti HTTP restano utilizzabili). Il modello ha aggiunto una frase **sbagliata**: «questo calcolo ... non tiene conto delle festività nazionali italiane», mentre il risultato del servizio dice il contrario.
- **B. `servizi-http` fermo**, `server-mcp` riavviato, `--no-deps`: discovery MCP riuscita; «Che corsi ci sono a Udine?» → `cerca_catalogo` → `Errore: servizio non raggiungibile su http://servizi-http:8000`, il modello: «non sono riuscito a trovare i corsi ... a causa di un errore del servizio»; «Elenca le mie note.» → `elenca_note` ok; «Che ora è a Tokyo?» → `orologio`.
- **Porta 8001 occupata e `server-mcp` non avviabile:** provato in T6 (casi E1 `run` fallisce, E2 `--no-deps` avvio ridotto con `orologio`) e non ripetuto in T15.
- **Porta 8000 occupata da un altro processo dell'host (`servizi-http` non avviabile):** `docker compose run --rm -T assistente` → **exit 1**, «ports are not available: exposing port TCP 127.0.0.1:8000 ... bind: Only one usage of each socket address»; `docker compose run --rm --no-deps -T assistente` → exit 0, avviso «Server MCP non raggiungibile ...» (il server MCP non era avviato), «Che ora è a Tokyo?» → `orologio`, «Che corsi ci sono a Udine?» → `cerca_catalogo` → `Errore: servizio non raggiungibile su http://servizi-http:8000`. Pulizia: listener e container rimossi.

### Criteri di verifica finale (spec §8), uno per riga

| # | Criterio | Stato | Evidenza |
|---|---|---|---|
| 1 | Tutte le nuove funzionalità disponibili e utilizzabili | **provato con il modello** | tutti e 11 gli strumenti chiamati almeno una volta nella batteria o nella prova di conferma (`elimina_nota` solo dopo la sessione nuova) |
| 2 | L'orologio continua a funzionare | provato | Tokyo, New York in batteria; Tokyo anche in avvio ridotto A e B |
| 3 | Selezione corretta con formulazioni diverse | **parziale, limite documentato** | due sessioni lunghe: 18/22 corrette ciascuna, con le stesse 4 domande senza chiamata, 0 scambi; ripetizione in sessioni nuove 12/12; l'utente ha scelto di documentare il limite (nessun intervento sulle descrizioni) |
| 4 | Discovery e invocazioni MCP reali nei log | provato | `strumenti scoperti su http://server-mcp:8001/mcp: [...]`; `verifica_mcp` exit 0 con i quattro nomi; invocazioni di `aggiungi_nota`, `elenca_note`, `elimina_nota`, `meteo` |
| 5 | Risultati associati al `tool_call_id` corretto | **solo simulato** | test automatici (`test_instradamento.py::test_due_richieste_nello_stesso_messaggio`, `test_mcp_client.py::test_due_richieste_nello_stesso_messaggio`, `test_due_turni_del_grafo_con_finto_modello`); con il modello i log di testo non mostrano gli identificativi, le risposte sono coerenti con i risultati degli strumenti |
| 6 | Errori gestiti in modo chiaro | provato (timeout: simulato) | servizio spento (T13, T15-B); input non valido (anno 2025, 400 giorni: T13; codice ITS-999: T14); ID inesistente (nota 99, T15); timeout solo con `httpx.MockTransport`/server finto nei test |
| 7 | Cronologia, limite passaggi e interruzioni | provato (Ctrl+C con 11 strumenti: riferito dall'utente) | cronologia: «Mi chiamo Marco.» → «Come mi chiamo?» → «Ti chiami Marco.» (T15); `MAX_PASSAGGI=2` e Ctrl+C (al prompt e durante la risposta) provati nelle prove iniziali (tabella in testa a questo file, Ctrl+C riferito dall'utente) e coperti da test (`test_limite.py`, `test_terminale.py`) |
| 8 | Docker Compose come da istruzioni, vera discovery, avvio ridotto | provato | build, tre servizi da zero, `healthy`, `verifica_mcp` exit 0 con i nomi, agente con log; avvio ridotto con `server-mcp` in crash (A) e `servizi-http` fermo (B); porta 8000 occupata provata in T15, server fermo e porta 8001 occupata provati in T6 |
| 9 | Test e prove documentati, simulato vs provato | questo file | 403 test automatici verdi; sezioni per ramo con la distinzione |

### Altre osservazioni sul modello (T15)

- **Cronologia al posto dello strumento:** oltre alle 4 mancanze della batteria, nella prova di conferma il modello ha ripetuto a memoria l'esito di una cancellazione precedente invece di richiamare `elimina_nota`; senza conferma dell'utente non cancella comunque nulla.
- **Frasi aggiunte non fondate:** in A il commento sulle festività contraddice il risultato dello strumento.
- **Servizio spento:** il modello riferisce «un errore del servizio» ma non il motivo preciso (già osservato).
- Non provato: altri modelli; la causa del salto dello strumento nelle sessioni lunghe; il timeout reale dei servizi; Ctrl+C con tutti gli strumenti in Docker (provato dopo, vedi la sezione «Ctrl+C in Docker con 11 strumenti»).

## Ramo `fix/input-non-valido` — input con byte non validi in Docker (2026-11-09)

**Come è emerso:** durante la prova interattiva con TTY di Ctrl+C (variante `[s/N]`) l'utente ha scritto «elimina la nota 1» e la sessione si è interrotta con `UnicodeEncodeError: 'utf-8' codec can't encode character '\udcc2' ... surrogates not allowed`, senza premere Ctrl+C. Ciò che l'utente ha digitato esattamente non è noto (ipotesi: carattere speciale incollato, per esempio `«»`, `°` o uno spazio non separabile, che in UTF-8 iniziano con il byte `0xC2`; un Backspace su una lettera accentata è meno plausibile, perché le accentate italiane iniziano con `0xC3`).

| Prova | Stato | Esito |
|---|---|---|
| Prima della correzione: `printf 'elimina la nota \xc2\n' \| docker compose run --rm --no-deps -T assistente` | **provata** | stesso traceback, `\udcc2` nella richiesta al modello (`stdin utf-8 surrogateescape` in Docker) |
| Prima: input valido con `«»` e accenti | provata | nessun errore: il difetto riguarda solo i byte non validi |
| Dopo la correzione e `docker compose build`: lo stesso input | **provata** | exit 0, nessun traceback; il modello risponde («fornisci l'ID della nota») |
| Test automatici (`test_terminale.py`) | simulati | byte isolato `\udcc2`, sequenza troncata `caff\udcc3`, surrogato isolato `\ud800`: la sessione continua e il testo inviato al modello è codificabile (contiene U+FFFD per i primi due casi, `?` per il surrogato isolato fuori intervallo, che stdin non produce); testo valido con accenti, `«»` ed `€` resta invariato |

Non provato: una sessione interattiva con TTY reale con incolla di caratteri speciali (l'origine esatta del byte nella sessione dell'utente resta un'ipotesi). La correzione sostituisce i byte non validi con U+FFFD in `ripulisci_input`, quindi il modello vede il carattere sostitutivo.

## Ctrl+C in Docker con 11 strumenti, su `dev` dopo il merge di `fix/input-non-valido` (2026-11-09)

Prova **interattiva con TTY** (`docker compose run --rm assistente`, immagine ricostruita, `server-mcp` e `servizi-http` attivi), eseguita **dall'utente**: Ctrl+C al prompt `Tu:`, Ctrl+C durante la risposta del modello e la variante facoltativa alla domanda `[s/N]` di `elimina_nota`, secondo la guida data. Esito riferito dall'utente: **«sono passate tutte»**. L'esito è quello riferito dall'utente, **non riletto da log** da me; non ho chiesto il dettaglio per singola prova né se sia rimasto qualche container `...assistente-run-...`.

Il primo tentativo dell'utente (prima del ramo `fix/input-non-valido`) era invece caduto per un byte non valido nell'input, non per Ctrl+C: vedi la sezione di quel ramo.

## Ramo `feat/router` — Step 1 Lezione 6: Router di ambito (2026-11-15)

Prove reali con LM Studio (`google/gemma-4-e2b`) e Docker Desktop, **distinte dai test simulati** di `tests/test_router.py`. Le domande sono state passate da file o da uno script che pilota la chat; esiti riletti dai log su stderr. Le durate sono quelle registrate dal Router (`durata=`).

### Locale, sessione da 11 domande (server MCP e servizio HTTP attivi)

| # | Domanda | Router | Agente / strumenti | Esito |
|---|---|---|---|---|
| 1 | Che ore sono a Tokyo? | conversazione, 43,6 s | `orologio(Asia/Tokyo)` | OK |
| 2 | Scrivimi una poesia sull'autunno | fuori_ambito, 35,4 s | nessuna riga `agente:` né `strumento richiesto` | OK, rifiuto |
| 3 | Che tempo fa a Roma? | conversazione, 43,9 s | `meteo(Roma)` via MCP | OK |
| 4 | E a Trieste? | conversazione («continuazione di una domanda precedente»), 48,6 s | `meteo(Trieste)` | OK, continuazione |
| 5 | Che giorno è oggi? | conversazione, 36,2 s | nessuno strumento (vedi sotto) | Router OK |
| 6 | E domani? | conversazione («continuazione di una richiesta temporale»), 46,3 s | nessuno strumento (vedi sotto) | Router OK |
| 7 | Raccontami nel dettaglio la storia della Rivoluzione francese (dopo il meteo) | fuori_ambito, 36,5 s | nessuna riga `agente:` | OK, rifiuto |
| 8 | Scrivimi una canzone sul mare | fuori_ambito, 6,9 s | nessuna riga `agente:` | OK, rifiuto |
| 9 | Quanto fa 17 per 23 più 5? (dopo due rifiuti) | conversazione, 43,8 s | `calcola` → 396 | OK, non influenzato dai rifiuti |
| 10 | Ciao, cosa sai fare? | conversazione, 46,3 s | risposta descrittiva | OK |
| 11 | Quanto costa un corso? (ambigua) | conversazione, 48,7 s | chiede di quale corso si tratta | OK, tolleranza |

Il rifiuto compare nel formato fisso, con «attività» e «unità» corretti.

**Agente senza orologio (domande 5 e 6), limitazione già nota, non del Router.** L'agente ha risposto «Oggi è il 15 novembre 2026» e «Domani sarà il 16 novembre 2026» **senza chiamare `orologio`**, ricavando la data dalla risposta della domanda 1 presente in cronologia. Le date erano corrette, ma solo grazie a quella cronologia. È la limitazione del modello piccolo già documentata nel README («Limitazioni note»). Non è stata modificata in questo Step.

### Conferma di `elimina_nota` attraverso il Router (nota temporanea)

Sequenza: aggiunta della nota temporanea, richiesta di eliminarla con risposta `n`, elenco, nuova richiesta con risposta `s`. Ogni domanda è stata classificata `conversazione` (38,3–61,3 s).
- Con `n`: `conferma dell'utente: … esito=no`, risultato `Errore: cancellazione non confermata dall'utente`; l'elenco successivo mostra ancora la nota.
- Con `s`: `Nota 1 eliminata`; l'archivio è tornato vuoto, verificato con una lettura diretta di `data/note.db`.

Esito: OK. In precedenza l'archivio non esisteva: il file vuoto è stato creato da una lettura di controllo, e il server crea la tabella al primo uso.

### Server di LM Studio fermato e riavviato (`lms server stop` / `lms server start`)

Uno script ha pilotato la chat. Prima «Che ore sono a Tokyo?» con il server attivo: Router 36,4 s, `orologio`. Poi `lms server stop` e «Scrivimi una poesia sulla neve»: in 13,6 s, dopo i 2 tentativi automatici dell'SDK `openai`, compare «Non riesco a ottenere una risposta dal server del modello (Connection error.)…»; nessuna riga del Router né `agente:`. Dopo `lms server start` il modello è di nuovo raggiungibile (`GET /v1/models`). Infine «E a Londra?»: classificata come continuazione (35,9 s), `orologio(Europe/London)`. Il turno fallito non è rimasto in cronologia.

Esito: OK.

### Accenti con il comando PowerShell del README

`.env` caricato con `Get-Content .env -Encoding UTF8 | …`, poi «Scrivimi una poesia sul mare». Nel rifiuto «attività» arriva con il codice `E0`, cioè corretto. Senza `-Encoding UTF8` lo stesso valore diventa «attivitÃ » (verificato su una copia di `.env.example`).

Esito: OK.

### Docker Compose

- `docker compose build`: OK.
- `docker compose run --rm -T assistente` con «Che ore sono a Tokyo?» e «Scrivimi una poesia sull'autunno»:
  - discovery da `server-mcp`;
  - prima domanda: Router `conversazione` (33,2 s), `orologio(Asia/Tokyo)`;
  - seconda domanda: Router `fuori_ambito` (38,0 s), rifiuto senza riga `agente:`, accenti corretti (`env_file` legge UTF-8).

  Esito: OK.
- `AMBITO_AGENTE` tolta temporaneamente da `.env`, poi `docker compose run --rm -T --no-deps assistente`: uscita con codice 1 e il messaggio «Variabile d'ambiente mancante o vuota: AMBITO_AGENTE». `.env` ripristinato e confrontato byte per byte con la copia. Esito: OK.
- **Osservazione, non legata al Router.** Durante la sessione `docker compose ps` ha mostrato `server-mcp` come `unhealthy`: i controlli di salute superavano il limite di 8 s, pur con una discovery riuscita. Il comando del controllo (`verifica_mcp`) non importa moduli di questo ramo. Rieseguito a modello fermo, ha richiesto 4,3–4,6 s e il servizio è tornato `healthy`. Che la causa sia il carico della macchina durante l'elaborazione di LM Studio è un'ipotesi, non verificata. L'agente non ne risente, perché dipende da `server-mcp` con `service_started`.

### Latenza del Router (19 classificazioni reali)

Le 19 classificazioni sono: 11 della sessione locale, 4 della conferma, 2 della prova con il server fermato, 2 in Docker.

| | Valore |
|---|---|
| minimo | 6,9 s |
| massimo | 61,3 s |
| mediana | 40,5 s |
| media | 40,3 s |
| senza il 6,9 s | 33,2–61,3 s, mediana 42,1 s |

Il valore di 6,9 s (domanda 8) è arrivato subito dopo un altro rifiuto. La causa non è stata verificata. Lo spike aveva stimato 26–46 s; nelle prove reali la gamma è più ampia. La latenza resta accettata solo provvisoriamente: non è una prestazione adeguata per l'applicazione finale.

### Non verificati dal vivo

Fail-open per output non valido e timeout del Router: coperti solo dai test simulati, perché non si possono provocare in modo affidabile con il modello reale.

## Ramo `feat/revisore` — Step 2 Lezione 6: Revisore della risposta (2026-11-15)

Prove reali con LM Studio (`google/gemma-4-e2b`, contesto 8192 token) e Docker Desktop, **distinte dai test simulati** di `tests/test_revisore.py`. Le domande sono state passate da uno script che pilota `python -m assistente.terminale`: invia una riga quando compare «Tu: » o «[s/N]: ». Gli esiti sono stati riletti dai log su stderr.
- **Durata del Revisore:** il campo `durata=` dei suoi log.
- **Durata del turno:** misurata dall'esterno dallo script, tra l'invio della domanda e il prompt successivo. Nessun log del programma la registra.

In locale il server MCP usava un **archivio SQLite temporaneo** (`NOTE_DB_PATH` nello scratchpad della sessione), quindi `data/note.db` non è stato toccato: hash SHA-256 uguale prima e dopo le prove.

### Locale, sessione 1 (9 domande, server MCP e servizio HTTP attivi)

| # | Domanda | Revisore | Strumenti | Esito |
|---|---|---|---|---|
| 1 | Che ore sono a Tokyo e che tempo fa a Roma? | **false** (11,4 s) su una risposta completa, poi true (7,1 s) | `orologio`, `meteo` | falso rifiuto (vedi sotto), correzione approvata; turno 177 s |
| 2 | Che ore sono a Londra? | true (7,2 s) | `orologio` ×2 | OK |
| 3 | Quanto fa 17 per 23 più 5? | true (32,9 s) | `calcola` → 396 | OK |
| 4 | Che giorno è oggi? | true (6,5 s) | `orologio` | OK, data con strumento |
| 5 | E domani? | true (26,8 s) | nessuno | OK, continuazione; data ricavata dalla cronologia |
| 6 | Elenca i corsi del catalogo | true (8,2 s) | nessuno | richiesta di chiarimento giudicata coerente |
| 7 | Che tempo fa? | — | — | **Router `fuori_ambito`**: rifiuto, Revisore non eseguito (errore di classificazione del Router, non del Revisore) |
| 8 | Converti 10 miglia in chilometri e dimmi che ore sono a Sydney. | true (8,3 s) | `converti_unita`, `orologio` | OK, due parti al primo giudizio |
| 9 | Grazie! E a Parigi che ore sono? | — | `orologio` | **errore HTTP 400** di LM Studio dopo 902 s alla seconda chiamata dell'agente (vedi sotto) |

### Locale, sessione 5 (ripetizione, 4 domande)

| # | Domanda | Revisore | Strumenti | Esito |
|---|---|---|---|---|
| 1 | Che ore sono a Tokyo e che tempo fa a Roma? | **false** (9,7 s) su una risposta completa, poi true (8,6 s) | `orologio`, `meteo`, **rieseguiti** nella correzione | falso rifiuto; turno 204 s |
| 2 | Dimmi quanto fa 15 per 7, che tempo fa a Milano e quanti giorni lavorativi ci sono tra il 1 e il 10 dicembre 2026. | true (9,7 s) | `calcola('15/7')`, `meteo`, `giorni_lavorativi` | tre parti affrontate; **calcolo sbagliato approvato** (2,14 invece di 105): il Revisore non verifica i dati, come previsto |
| 3 | Grazie! E a Parigi che ore sono? (dopo un turno corretto) | true (40,5 s) | `orologio` | OK: nuova domanda pertinente, nessun effetto della vecchia osservazione; nessun 400 |
| 4 | Cerca nel catalogo un corso di inglese e dimmi che ore sono a New York. | true (57,8 s) | `cerca_catalogo`, `orologio` | OK, nessun risultato nel catalogo segnalato in modo concreto |

### Prove mirate

- **Servizio HTTP fermo (prova 4).** Domanda «Quanti giorni lavorativi ci sono tra il 1 e il 15 dicembre 2026?»: `giorni_lavorativi` → `Errore: servizio non raggiungibile`. La risposta «non sono riuscito… errore del servizio» è stata giudicata true (42,7 s, «indisponibilità concreta del servizio»). Esito: OK.
- **`MAX_REVISIONI=0` (prova 7)**, impostata dopo il caricamento di `.env`:
  - Tokyo + Roma, risposta completa: false (9,1 s), `→ limite` e `WARNING … limite di revisioni raggiunto (0)`; restituita la risposta, nessuna correzione;
  - «Quanto fa 12 per 12?»: l'agente ha chiamato `calcola('12/12')` e ha risposto «fa 1». Il Revisore ha dato false (45,4 s) con il motivo «matematicamente errata», cioè **fuori dal suo criterio**, anche se nel merito corretto. `WARNING` di limite.

  Esito: comportamento di `MAX_REVISIONI=0` OK.
- **Conferma di `elimina_nota` (prova 6, archivio temporaneo):**
  - con `n`: `esito=no`, `Errore: cancellazione non confermata dall'utente`, nota ancora presente; risposta giudicata coerente;
  - una seconda richiesta «Elimina la nota 1» non ha chiamato lo strumento (risposta a parole), quindi la riga `s` successiva è arrivata come domanda (limitazione nota dell'input da file);
  - ripetuta in una sessione breve («Elimina la nota con id 1», poi `s`): `esito=sì`, «Nota 1 eliminata», elenco successivo vuoto, verificato anche con una lettura diretta dell'archivio temporaneo.

  Esito: OK.
- **Azioni ripetute (prova 6bis, rilievo D1, archivio temporaneo):** «Aggiungi una nota "prova duplicati revisore" e dimmi che ore sono a Tokyo» → `aggiungi_nota` chiamato **una volta**, risposta approvata al primo giudizio (51,3 s); nell'archivio una sola nota. **Nessun duplicato**, ma la prova **non ha messo alla prova la correzione**: il modello ha risposto subito in modo completo e non era forzabile. Il rischio resta documentato. Nella sessione 5, in un'altra correzione, l'agente ha rieseguito `orologio` e `meteo` (strumenti di lettura): la ripetizione degli strumenti durante una correzione è quindi osservata dal vivo.

### Docker Compose

- `docker compose build`: OK.
- `docker compose run --rm -T assistente`:
  - discovery da `server-mcp`;
  - «Che ore sono a Tokyo?» approvata (8,1 s);
  - «Che ore sono a Tokyo e che tempo fa a Roma?» (`orologio`, `meteo` via MCP) **approvata al primo giudizio** (43,0 s), con l'orario scritto per esteso («le ore 01:08:13 del 16 novembre 2026»);
  - turni da 90 e 142 s; `server-mcp` e `servizi-http` `healthy`.

  Esito: OK. Poi `docker compose down`, senza `-v`.

### Requisiti del corso: che cosa è stato visto dal vivo

- **Risposta coerente approvata al primo passaggio:** sì, in molti casi (Londra, calcolo, date, due e tre parti, Docker).
- **Domanda in due parti con risposta parziale → rifiuto motivato e risposta completa:** **non ottenuta con una risposta davvero parziale**. In 8 domande in più parti (7 in locale, 1 in Docker) l'agente ha sempre risposto a tutte le parti. Il percorso rifiuto → osservazione → correzione → approvazione è stato eseguito dal vivo 2 volte, ma partendo da falsi rifiuti. L'evidenza con una risposta parziale resta coperta dai test simulati (`test_risposta_parziale_rifiutata_e_corretta`).
- **Limite rispettato con un revisore che rifiuta sempre:** coperto dai test simulati; dal vivo osservato con `MAX_REVISIONI=0`.

### Falsi rifiuti sugli orari (osservazione importante)

La stessa domanda «Che ore sono a Tokyo e che tempo fa a Roma?» con risposta **completa** è stata respinta **3 volte su 3** in locale:
- sessione 1 (`MAX_REVISIONI=1`): motivo «attuale o futuro» riferito all'orario di Tokyo, poi approvata dopo la correzione;
- sessione con `MAX_REVISIONI=0` (sezione «Prove mirate»): motivo «informazioni specifiche e datate», risposta restituita con il `WARNING` di limite;
- sessione 5 (`MAX_REVISIONI=1`): motivo «informazioni specifiche e datate», poi approvata dopo la correzione.

In Docker la stessa domanda è stata approvata, con l'orario scritto per esteso invece che in formato `2026-11-16 00:02:48`. Il legame con il formato è un'**ipotesi non verificata**.

È il rischio annotato nella specifica (§14: esempio B sugli orari, possibile adattamento eccessivo dello spike). Con il limite predefinito costa una correzione: la risposta corretta arriva comunque, ma il turno si allunga (177–204 s) e l'agente riesegue gli strumenti. Le istruzioni **non** sono state modificate: la specifica chiede di ripetere lo spike per qualunque cambiamento (§5.2). **Decisione dell'utente (2026-11-15):** limitazione accettata per lo Step 2; un eventuale miglioramento andrà affrontato separatamente, con nuovi esperimenti e test.

### Errore HTTP 400 alla domanda 9 della sessione 1 (non riprodotto)

- **Che cosa è successo:** dopo `orologio(Europe/Paris)`, la chiamata all'agente è rimasta senza risposta per circa 900 s e poi LM Studio ha restituito `Error code: 400`. Il programma ha mostrato il messaggio di errore del server e ha scartato il turno, con la cronologia invariata. La chat è proseguita. È la gestione degli errori dell'agente, invariata in questo Step.
- **Indagine:**
  - la stessa richiesta, ricostruita dai log (2396 token di prompt, 11 strumenti), ha avuto risposta normale in 9,4 s, quindi il contesto non era pieno in partenza;
  - il client dell'agente lascia ragionare il modello (`reasoning` nei token di uscita);
  - un ragionamento andato in ciclo fino a riempire il contesto spiegherebbe tempo ed errore, ma **non è verificato**;
  - nella ripetizione (sessione 5) la stessa domanda dopo un turno corretto è andata a buon fine.
- **Causa:** non determinata. Il log del server di LM Studio di oggi è vuoto e la richiesta originale non è registrata.

### Latenze

| | Giudizi del Revisore (27) | Turni completi (23, misura esterna) |
|---|---|---|
| minimo | 5,6 s | 32,3 s (rifiuto del Router) |
| massimo | 57,8 s | 203,9 s (turno con correzione) |
| mediana | 9,7 s | 99,3 s |

Le sessioni sono sette: 1 e 5 in tabella; nella sezione «Prove mirate» le due delle note, quella con `MAX_REVISIONI=0` e quella con il servizio HTTP fermo; infine la sessione Docker. I giudizi contano tutte le righe `revisore:` con `durata=` di queste sessioni. I turni sono quelli conclusi con una risposta. Sono esclusi:
- le righe `esci`;
- le risposte `s`/`n` alla conferma;
- le domande che hanno aperto la conferma;
- il turno da 902 s con l'errore 400. Il Revisore è in genere più rapido del Router (mediana di quest'ultimo nelle stesse sessioni: circa 34 s). La latenza complessiva resta il limite principale dell'ambiente locale.

### Non verificati dal vivo

- Revisore non raggiungibile e giudizio non valido (fail-open): non provocabili in modo affidabile solo per il Revisore, coperti dai test simulati.
- Correzione dopo una risposta davvero parziale (vedi sopra).
- Duplicazione di una nota durante una correzione: non osservata, perché nessuna correzione ha coinvolto `aggiungi_nota`.
