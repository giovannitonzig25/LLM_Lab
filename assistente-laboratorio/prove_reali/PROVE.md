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

## Ramo `feat/riassunto` — Step 3 Lezione 6: Riassunto della cronologia (2026-11-15/16)

Prove reali con LM Studio (`google/gemma-4-e2b`, contesto 8192 token) e Docker Desktop, **distinte dai test simulati** di `tests/test_riassunto.py`, con `SOGLIA_RIASSUNTO=6`. Le domande sono state passate da uno script nella scratchpad che pilota `python -m assistente.terminale` (una riga a ogni «Tu: », «n» a «[s/N]: »); gli esiti sono stati riletti dai log su stderr. Durata del turno misurata dallo script; durate di Router, riassuntore e Revisore dal campo `durata=` dei log.

- **Dati:** in locale il server MCP usava un archivio SQLite temporaneo (`NOTE_DB_PATH` nella scratchpad, con 25 note precaricate per la prova 6); hash SHA-256 di `data/note.db` uguale prima e dopo tutte le prove (`5fa44468…`). `.env` salvato prima della prova Docker e ripristinato dopo: hash identico, nessuna riga `SOGLIA_RIASSUNTO`.
- **Esecuzione:** 4 sessioni locali una dopo l'altra (nessuna contesa fra sessioni); nei primi turni della sessione 1 girava in parallelo una `docker compose build`, quindi quei tempi vanno letti con cautela.
- **Prompt:** le prove 1–7 sono state eseguite con le cornici del 2026-11-15; dopo il fallimento delle prove 1 e 5 la cornice dell'agente (B.1) è stata rivista (spike in specifica §13.4) e la prova 8 è stata eseguita con la cornice rivista. Le prove 1–7 non sono state ripetute (regola di sviluppo pragmatico dell'utente): la prova 8 ne copre la parte principale.

| # | Atteso | Effettivo | Esito |
|---|---|---|---|
| 1 | Nome dato al turno 1, «Come mi chiamo?» dopo la compressione → risposta corretta | Compressione `messaggi 11 → 9` (7,7 s), poi Router `fuori_ambito` («richiesta informazione personale»): rifiuto fisso, agente non eseguito | **fallita** (Router) |
| 2 | Sotto la soglia nessuna chiamata al riassuntore | Log «soglia non superata (messaggi=1, 3, 5)» e, oltre la soglia senza turni da togliere, «nessun turno eliminabile (messaggi=7, turni completi=2)»: nessuna chiamata | **riuscita** |
| 3 | Informazione presente solo nel riassunto usata in una continuazione | «E se fossimo 10 persone…?» → Router `conversazione`, `calcola("400 / 10")`, Revisore coerente. Ma «400» era anche nel turno 2 conservato («Quanto fa 400 diviso 8?»): la memoria riassunta non è isolata | **verifica incompleta** (isolata poi nello spike, scenario C1: 3/3) |
| 4 | Valore cambiato di recente prevale sul riassunto in Router, agente e Revisore | Router `conversazione`; agente `calcola("500 / 10")` = 50 (valore recente); **Revisore `coerente=false` sulla risposta corretta**, correzione, poi approvata | **parziale** (Revisore) |
| 5 | Informazione del turno 1 sopravvive a due compressioni | Tre compressioni (`11 → 9`, `11 → 7`, `11 → 7`), poi «Ricordami come mi chiamo e qual è il mio obiettivo» rifiutata dal Router | **fallita** (Router), poi **riuscita** in Docker con la B.1 rivista (prova 8) |
| 6 | Osservazione: elemento di un `elenca_note` lungo dopo la compressione | La nota 6 («certificato medico») era oltre i 1000 caratteri del risultato troncato. L'agente ha risposto correttamente **senza richiamare lo strumento**: la nota compariva nella sua risposta testuale del turno 1, trascritta per intero. Non è una garanzia: con una risposta riassuntiva il dato sarebbe perso | osservazione (corretta, ma non per il motivo giusto) |
| 7 | Osservazione: risultato storico legato a una decisione superata | Scadenza 18 → 22 dicembre; alla domanda finale l'agente usa il 22 e ricalcola con `giorni_lavorativi` (15), senza riusare il vecchio 13 | osservazione: non confuso |
| 8 | Docker, sessione oltre la soglia senza strumenti delle note | `docker compose run --rm -T assistente` con `SOGLIA_RIASSUNTO=6` da `.env`: nome e obiettivo al turno 1, calcolo, conversione, giorni lavorativi; compressioni `11 → 9` e `15 → 11`; «Ricordami come mi chiamo e qual è il mio obiettivo» → «Il tuo nome è Marta e il tuo obiettivo è preparare il piano di studio per il corso di Python», Revisore coerente | **riuscita** |

### Comportamenti inattesi (registrati, non nascosti)

- **Router, falsi rifiuti senza riassunto:** «Sto organizzando una cena aziendale per 8 persone con un budget di 400 euro» e «Quanto fa 400 diviso 8?» classificate `fuori_ambito` (sessione 2, turni 1–2, prima di qualsiasi riassunto): limite del Router dello Step 1.
- **Router e «Come mi chiamo?»:** con il nome solo nel riassunto `fuori_ambito` in tutte le esecuzioni (prove 1 e 5, spike V0–V3 §13.4); con il nome nei turni recenti `conversazione` 3/3. Tre formulazioni della cornice B.2 non lo cambiano: limite documentato.
- **Revisore:** respinge risposte corrette (prova 4; 13 giorni lavorativi respinti due volte fino al limite, sessione 4; in Docker respinge «10 giorni lavorativi» perché «non è possibile determinare le festività» e approva una correzione **senza il numero**). Agente: in sessione 4 calcola 15/4 invece di 15×4, e il Revisore approva dopo la correzione. Limiti dello Step 2, non introdotti dal riassunto.
- **Router, ciclo di ragionamento:** in una variante di cornice scartata (spike V1) il Router ha generato 7676 token di ragionamento con `reasoning_effort="none"` fino a esaurire il contesto (12–16 min, poi fail-open). Con le cornici adottate non si è ripetuto (nessun timeout a 120 s).
- **Docker:** il primo `docker compose build` è fallito per un errore della cache di Docker («parent snapshot … does not exist»); `docker compose run` ha ricostruito le immagini e l'immagine usata conteneva la cornice rivista (verificato importando `assistente.riassunto` nel container).

### Latenze (sessioni locali)

| Componente | Chiamate | Minimo | Mediana | Massimo |
|---|---|---|---|---|
| Router | 22 | 27,2 s | 36,3 s | 58,8 s |
| Riassuntore (compressioni) | 10 | 7,7 s | 9,7 s | 33,2 s |
| Revisore | 21 | 6,1 s | 9,7 s | 50,8 s |

Turni completi da 33 a 250 s. In Docker: riassuntore 6,8 e 7,2 s, Router 26,5–43,2 s, Revisore 6,4–48,9 s. Token del server non registrati nei log del programma.

### Non verificati dal vivo

- Fail-open del riassuntore (server non raggiungibile, output vuoto o troncato) e turno fallito dopo una compressione: coperti dai test simulati.
- Prove 1–7 con la cornice B.1 rivista: non ripetute; la prova 8 copre ricordo del nome e due compressioni.
- Prove con le note in Docker: escluse per scelta (archivio su volume persistente).

## Ramo `feat/preferenze` — Step 4 Lezione 6: Resource MCP, preferenze dell'utente (2026-11-16)

Prove reali con LM Studio (`google/gemma-4-e2b`) e Docker Desktop, **distinte dai test simulati** (`tests/test_preferenze.py`, `test_server_mcp.py`, `test_mcp_client.py`, `test_strumenti.py`, `test_grafo.py`, `test_terminale.py`). In locale le domande sono state passate da uno script nella scratchpad che avvia server MCP e servizio HTTP e pilota `python -m assistente.terminale` via stdin; gli esiti sono stati riletti dai log su stderr.

- **Dati:** `NOTE_DB_PATH` e `PREFERENZE_PATH` puntavano a file temporanei nella scratchpad. Hash di `data/note.db` (`5fa44468…`) e di `.env` (`3ea91290…`) uguali prima e dopo; `.env` non è stato modificato.
- **R2 senza riavviare il server:** il server MCP è stato avviato una volta con le preferenze di R1; il file è stato cambiato prima della sessione R2, e la stessa istanza del server ha servito R2, il confronto sugli stili, R3 e R4.

| # | Atteso | Effettivo | Esito |
|---|---|---|---|
| R1 | `italiano`, `Europe/Rome`, `sintetico`: «Che ore sono?» senza chiedere il fuso; domanda in ambito in italiano e breve; lettura visibile nei log, separata dai tool | Log: `resource utente://preferenze letta da http://localhost:8001/mcp` e `preferenze della sessione: lingua=italiano (resource), fuso_orario=Europe/Rome (resource), stile=sintetico (resource)` **prima** di qualunque `strumento richiesto`; lato server `resource utente://preferenze letta da <file>`. `orologio` chiamato **senza argomenti** → «Sono le 19:48:40 del 16 novembre 2026 (Europe/Rome).»; «Converti 25 gradi Celsius in Fahrenheit.» → «25 gradi Celsius sono 77 gradi Fahrenheit.» | **riuscita** |
| R2 | File cambiato in `inglese`, `America/New_York`, `dettagliato`; nuova sessione senza toccare codice né server | Riga `preferenze della sessione` con i tre valori `(resource)`. `orologio` **senza argomenti** → «The current time is 13:52:41 on November 16, 2026, in the America/New_York timezone (UTC-05:00).»; conversione → «25 degrees Celsius is equal to 77 degrees Fahrenheit.» Revisore coerente su entrambe le risposte in inglese | **riuscita** per fuso e lingua; stile non osservabile su una conversione (risposta di una frase) |
| R2b | Confronto degli stili su una domanda che si presta a spiegazioni: «Che cos'è il fuso orario UTC?» (italiano, Europe/Rome) | `dettagliato`: definizione, elenco in 4 punti (che cos'è, funzione, relazione con l'ora locale, misurazione) e sintesi finale. `sintetico`: 2 frasi. Revisore coerente in entrambi i casi | **riuscita** |
| R3 | `"stile": "dettagliatissimo"`: WARNING sul campo, gli altri due dal file | `WARNING … preferenza stile non valida (ammessi solo sintetico o dettagliato: 'dettagliatissimo'): uso sintetico`; `lingua=italiano (resource), fuso_orario=Europe/Rome (resource), stile=sintetico (predefinito)` | osservazione: come previsto |
| R4 | File mancante: WARNING con la causa, tre predefiniti, conversazione con gli strumenti MCP | `WARNING … preferenze non disponibili (lettura di utente://preferenze impossibile su http://localhost:8001/mcp: <file>: No such file or directory): uso i valori predefiniti`; tre `(predefinito)`. «Salva una nota: comprare il latte» → `aggiungi_nota` via MCP, «Nota salvata.» Nel log del server compare anche il traceback di FastMCP con `ResourceError` | **riuscita** |
| R5 | Server MCP spento: due avvisi distinti, conversazione con strumenti locali e HTTP | Con il file che chiedeva New York: `WARNING assistente.strumenti: discovery MCP fallita, avvio ridotto …` e `WARNING assistente.preferenze: preferenze non disponibili (… Client failed to connect …)`, più l'avviso su stderr del terminale. «Che ore sono?» → `orologio` senza argomenti, Europe/Rome (predefinito) | **riuscita** |
| R6 | Docker: file creato con i comandi del README, `docker compose build`, sessione; poi modifica sull'host e nuova sessione senza build | `New-Item … data` + `Copy-Item preferenze.example.json data\preferenze.json`, `docker compose build`, `docker compose run --rm -T assistente`: lettura da `http://server-mcp:8001/mcp`, server `resource … letta da /preferenze/preferenze.json`, «Sono le 20:19:22 (Europe/Rome).» Poi `Set-Content -Encoding utf8` (scrive il **BOM**) con inglese/New York/dettagliato, `server-mcp` lasciato acceso, nuova `docker compose run --rm -T assistente` → «The current time is 14:20:30 on November 16, 2026, in the America/New_York timezone.» | **riuscita** (anche con BOM) |

Dopo R6: `docker compose down` (senza `-v`), `data/preferenze.json` riportato al contenuto dell'esempio.

### Comportamenti inattesi (registrati, non nascosti)

- **Router, anomalia già nota:** nella sessione R2b con stile `dettagliato` il Router ha impiegato **1004,9 s** e si è chiuso con `LengthFinishReasonError` (fail-open: la domanda è arrivata all'agente, che ha risposto correttamente). È l'anomalia osservata negli step precedenti, con migliaia di token di ragionamento nonostante `reasoning_effort="none"`. Il Router non cambia in questo Step e il suo prompt non contiene le preferenze; la stessa domanda con `sintetico` è stata classificata in 34,1 s.
- **Traceback nel log del server:** con il file mancante FastMCP registra il traceback di `ResourceError`, anche se il messaggio che arriva al client è pulito. Documentato nel README (Diagnosi).

### Latenze (sessioni locali)

Router 28,2–51,8 s (escluso il caso anomalo), Revisore 5,9–13,5 s; sessioni da 2 domande circa 220 s. In Docker: sessione da 1 domanda 66–67 s. La lettura della resource all'avvio non ha latenza percepibile (avvio di R3 e R4 senza domande: 6–9 s complessivi, incluso l'avvio dei servizi).

### Non verificati dal vivo

- Server che accetta la connessione ma non risponde: coperto dal test con `porta_muta()`.
- JSON non valido o non oggetto, chiavi sconosciute, `lingua` non valida: coperti dai test simulati.

## Ramo `feat/prompt-mcp` — Step 5 Lezione 6: Prompt MCP, comandi riusabili nella CLI (2026-11-16/17)

Prove reali con LM Studio (`google/gemma-4-e2b`), **distinte dai test simulati** (`tests/test_server_mcp.py`, `test_mcp_client.py`, `test_comandi.py`, `test_terminale.py`). Le righe sono state passate da uno script nella scratchpad che avvia server MCP e servizio HTTP e pilota `python -m assistente.terminale` via stdin; gli esiti sono stati riletti da stdout e dai log su stderr.

- **Dati:** `NOTE_DB_PATH` e `PREFERENZE_PATH` puntavano a file temporanei nella scratchpad (preferenze dell'esempio: italiano, Europe/Rome, sintetico). Hash di `data/note.db` (`5fa44468…`) e `data/preferenze.json` (`7b80d855…`) uguali prima e dopo.
- **`.env` modificato con l'autorizzazione dell'utente:** dopo la prima R2 l'ambito di `AMBITO_AGENTE` è stato esteso (in `.env` e `.env.example`) con «; spiegazioni introduttive di concetti informatici, come i protocolli usati dagli assistenti.».

| # | Atteso | Effettivo | Esito |
|---|---|---|---|
| R1 | `/prompts`: nome, descrizione e argomenti dei due prompt dal server | `Prompt disponibili:` con `spiega` (`argomento` obbligatorio, `livello` facoltativo) e `riassumi_conversazione` (`stile` facoltativo), descrizioni del server | **riuscita** |
| R2 | `/prompt spiega argomento="Model Context Protocol" livello=base`: risposta adeguata al livello; log con prompt, argomenti e messaggi | Log `prompt richiamato: nome=spiega argomenti={'argomento': 'Model Context Protocol', 'livello': 'base'}` e `prompt ottenuto: … messaggi=[('user', "Spiega l'argomento «Model Context Protocol» a livello base. …")]`; il terminale mostra `[prompt spiega] …`. **Con l'ambito precedente il Router ha rifiutato** (`fuori_ambito`, «richiesta di spiegazione tecnica», 79,8 s). Con l'ambito esteso: Router `conversazione` (47,4 s), agente, Revisore coerente (11,3 s); risposta con linguaggio semplice ed esempio concreto, più lunga dello stile `sintetico` (il livello prevale). **Contenuto inesatto:** MCP descritto come «regole per gestire il contesto della conversazione» | **riuscita** per il percorso e il livello; contenuto limitato dalla conoscenza del modello |
| R3 | `riassumi_conversazione` dopo 2 turni (ora a Tokyo, 10 km in miglia), senza compressione | Router `conversazione` («richiesta di riassunto», 51,4 s), nessuno strumento, Revisore coerente (10,1 s): «La conversazione è consistuta nella richiesta dell'ora a Tokyo e nella conversione di 10 chilometri in miglia.» | **riuscita** |
| R4 | Come R3 con `SOGLIA_RIASSUNTO=4`, dopo una compressione: il riassunto comprende anche il turno compresso | 3 turni (saluto con nome e obiettivo, 5 miglia in km, giorni lavorativi), poi `/prompt riassumi_conversazione stile="elenco puntato"`: il Riassunto comprime 1 turno (13 → 11 messaggi, 16,0 s), Router e Revisore accettano, elenco puntato rispettato. **Il turno compresso (nome Giulia, obiettivo) manca** dal riassunto finale. Ripetuta dopo il primo tentativo sul testo di A.2 (commit `2d868e9`, «Includi sia i turni compresi nel riassunto…»): stesso esito | **non riuscita** per il turno compresso; limite documentato. Secondo tentativo non eseguito per decisione dell'utente |
| R5 | Argomento obbligatorio mancante; argomento sconosciuto; livello non ammesso | `/prompt spiega` → «Argomenti obbligatori mancanti: argomento.» + riga d'uso; `argomento=x pippo=1` → «Argomenti sconosciuti: pippo. Argomenti accettati: argomento, livello.»; due `WARNING assistente.comandi: richiesta respinta …`, nessuna riga di Router o agente. `livello=esperto` → «Prompt non eseguito: … livello non valido: esperto (valori ammessi: base, intermedio, avanzato)» | **riuscita** |
| R6 | Server MCP spento: avvio ridotto, comandi con messaggio | Avvisi di avvio ridotto e preferenze predefinite; `/prompts` e `/prompt spiega argomento=MCP` → «Prompt MCP non disponibili: discovery dei prompt impossibile su http://localhost:8001/mcp: Client failed to connect …»; nessun turno | **riuscita** |
| R7 | Docker Compose: `/prompts` e `/prompt spiega` nel container | Non eseguita per decisione dell'utente (tempi delle prove) | **non verificata** |

### Comportamenti inattesi (registrati, non nascosti)

- **Durata della prima R4:** 2339 s, mentre le durate registrate di Router, Revisore e Riassunto sommano circa 520 s; il resto è andato in chiamate all'agente, che non hanno una durata nel log. La ripetizione della stessa sessione ha richiesto 780 s. Probabile l'anomalia di ragionamento lungo già osservata negli step precedenti.
- **Falso rifiuto del Revisore** sul turno dei giorni lavorativi della prima R4: risposta corretta (10 giorni) respinta due volte, `WARNING` di limite. Comportamento già documentato negli step precedenti.
- **Refuso del modello** in R3 («consistuta»).

### Latenze (sessioni locali)

Router 42,5–79,8 s, Revisore 7,9–71,8 s, Riassunto (compressione) 16,0 s. Sessioni: R1+R2+R5 (prima R2 rifiutata) 91 s; R2 con ambito esteso 130–155 s; R3 304 s; R4 780–2339 s; R6 30 s. Discovery e compilazione dei prompt senza latenza percepibile.

### Non verificati dal vivo

- R7 in Docker (Compose non è cambiato; i prompt viaggiano sullo stesso server MCP).
- Server che accetta la connessione ma non risponde: coperto dal test con `porta_muta()`.
- Messaggio non testuale, ruoli non riconosciuti, apostrofi e barre rovesciate nei valori: coperti dai test simulati.

## Ramo `feat/agente-http` — Step 6 Lezione 6: l'agente come servizio HTTP (2026-11-17)

Controllo funzionale essenziale con LM Studio (`google/gemma-4-e2b`), una volta per evidenza, distinto dai test simulati (`tests/test_servizio_agente.py`, `test_terminale.py`). Server MCP, servizio HTTP e agente avviati in locale come processi separati con le variabili di `.env`; chiamate con `Invoke-RestMethod`.

- **Dati:** server MCP sul `data/note.db` reale; per la prova di cancellazione è stata aggiunta la nota 2 («nota di prova Step 6»), poi cancellata dalla prova stessa.

| # | Atteso | Effettivo | Esito |
|---|---|---|---|
| H1 | `GET /stato` con tutto attivo: 200; `/docs` consultabile | `{"agente":"ok","mcp":"ok","modello":"ok"}`; `/docs` 200 | **riuscita** |
| H2 | `POST /chat` «Che ore sono a Tokyo?»: risposta, `strumenti_usati`, traccia nel log | Risposta «Attualmente sono le 08:33:02 del 17 novembre 2026 a Tokyo.», `strumenti_usati=[{"nome":"orologio","argomenti":{"timezone":"Asia/Tokyo"}}]`, cronologia di 4 messaggi. Log: `router … → agente`, `strumento richiesto: nome=orologio …`, `strumento eseguito: … (Asia/Tokyo, UTC+09:00)`, `revisore: coerente=true`, `turno: esito=risposta strumenti=['orologio'] … durata=107.6s` | **riuscita** |
| H3 | Server MCP spento: codice e messaggio comprensibili | `/stato` → 503 `{"agente":"ok","mcp":"non raggiungibile: discovery impossibile su http://localhost:8001/mcp: …","modello":"ok"}`; `/prompts` → 503 `{"errore":"discovery dei prompt impossibile su …"}` | **riuscita** |
| H4 | Modello non raggiungibile (secondo agente sulla porta 8003 con `LM_STUDIO_BASE_URL=http://localhost:1/v1`) | `POST /chat` → 503 `{"errore":"Non riesco a ottenere una risposta dal server del modello (Connection error.). Controlla che LM Studio sia attivo …"}` | **riuscita** |
| H5 | CLI come client: «Elimina la nota con id 2», conferma `s` | La CLI chiede `Confermi: elimina_nota {'id': 2}? [s/N]`, ripete il turno con la conferma, stampa «Nota 2 eliminata.»; nota assente nel database. Log: primo turno `conferme_richieste=['elimina_nota']`, secondo `conferma dell'utente: strumento=elimina_nota esito=sì` e `turno: esito=risposta strumenti=['elimina_nota'] conferme_richieste=[]` | **riuscita** |

### Comportamenti inattesi (registrati, non nascosti)

- **Primo giro della cancellazione lungo (192 s):** il Revisore ha respinto la risposta «non confermata» e ha chiesto una correzione prima che la CLI potesse chiedere la conferma; il secondo giro, confermato, ha richiesto 96 s. In tutto circa 5 minuti per una cancellazione.

### Non verificati dal vivo

- Docker Compose (nuovo servizio `agente` con healthcheck e CLI con `AGENTE_URL=http://agente:8002`): solo `docker compose config` valido, nessun avvio.
- Prompt MCP dalla CLI attraverso l'API: coperti dai test con il server MCP reale (`test_main_prompt_spiega_dal_server_reale`).

## Ramo `feat/backend-chat` — Step 7 Lezione 6: back-end, API e salvataggio delle chat (2026-11-17)

Controllo funzionale essenziale con LM Studio (`google/gemma-4-e2b`), una volta per evidenza, distinto dai test simulati (`tests/test_servizio_backend.py`). PostgreSQL 17.6 in Docker (`docker compose up -d postgres`, pubblicato su `127.0.0.1:5433`); server MCP, servizio HTTP, agente e back-end avviati in locale come processi separati con le variabili di `.env`; chiamate con `Invoke-WebRequest`.

- **Archivio da solo (Task 1):** giro `prepara` → `crea_chat` → due `aggiungi_scambio` → `elenca_chat` → `leggi_chat` → `stato_agente` → `elimina_chat` sul database vero: tutto come atteso (titolo = prima domanda senza spazi ai bordi, messaggi in ordine, `ChatNonTrovata` dopo l'eliminazione, `ErroreDatabase` con porta sbagliata).
- **Avvio (Task 2):** senza `DATABASE_URL` → «DATABASE_URL mancante: impostala in .env (vedi .env.example).» e codice 1.

| # | Atteso | Effettivo | Esito |
|---|---|---|---|
| B1 | OpenAPI generata e consultabile | `/docs` 200; `/openapi.json` con `/chat`, `/chat/{id}`, `/chat/{id}/messaggi` | **riuscita** |
| B2 | Crea chat, invia un messaggio: risposta salvata e rileggibile | `POST /chat` → 201 id 4, «Nuova chat»; «Mi chiamo Giovanni. Che ore sono a Roma?» → 200 «Ora sono le 16:50:58 del 17 novembre 2026 a Roma (Europe/Rome).», `strumenti_usati=[orologio Europe/Rome]` (124 s); `GET /chat/4` con i due messaggi in ordine, titolo = domanda; `GET /chat` con `ultimo_messaggio_il` | **riuscita** |
| B3 | Riavvio del back-end e di `postgres` (`docker compose restart postgres`): chat ancora presenti | Elenco e `GET /chat/4` identici a prima del riavvio; «Come mi chiamo?» → «Ti chiami Giovanni.» (84 s): la cronologia salvata arriva all'agente | **riuscita** |
| B4 | Agente spento: errore chiaro, nulla salvato | `POST /chat/4/messaggi` → 503 `{"errore":"Agente non raggiungibile su http://localhost:8002"}` (4,5 s); `GET /chat/4` invariata | **riuscita** |

### Comportamenti inattesi (registrati, non nascosti)

- **Porta 5432 occupata** da un PostgreSQL installato su Windows: Compose pubblica il container su `127.0.0.1:5433`.
- **`localhost` lento con psycopg su Windows:** con `DATABASE_URL=…@localhost:5433/…` ogni operazione attendeva ~5 s (tentativo IPv6 su `::1`, porta pubblicata solo su IPv4); con `127.0.0.1` ~0,1 s. `.env.example` usa `127.0.0.1`. Lo stesso effetto spiega probabilmente i 4,5 s di B4 con `AGENTE_URL=http://localhost:8002`.

### Non verificati dal vivo

- Ciclo di conferma di `elimina_nota` attraverso il back-end: coperto dal test simulato `test_conferma_non_salva_poi_salva`.
- Database che cade durante l'uso (503 «Database non raggiungibile»): coperto dal test simulato.

## Ramo `feat/frontend-chat` — Step 8 Lezione 6: front-end, interfaccia di chat (2026-11-17)

Controllo funzionale essenziale con LM Studio (`google/gemma-4-e2b`), una volta per evidenza, distinto dai test simulati (`tests/test_servizio_frontend.py`). PostgreSQL in Docker (`docker compose up -d postgres`, `127.0.0.1:5433`); server MCP, servizio HTTP, agente, back-end e front-end avviati in locale come processi separati con le variabili di `.env`. Prove eseguite dall'utente nel browser su `http://127.0.0.1:8004`; esiti confermati nei log di accesso del front-end e nei log dell'agente.

- **Avvio (Task 1):** senza back-end, `GET /` → 200 e `GET /api/chat` → 503 `{"errore":"Back-end non raggiungibile su http://127.0.0.1:8003"}`.
- **Inoltro (Task 2):** tramite la porta 8004 `POST /api/chat` → 201, `GET /api/chat/5` → 200, `DELETE` → 204, poi 404 `{"errore":"Chat 5 non trovata"}`; `/static/app.js` e `/static/stile.css` → 200; `node --check app.js` (Node già presente sull'host, solo come controllo di sintassi) → 0.

| # | Atteso | Effettivo | Esito |
|---|---|---|---|
| F1 | Conversazione completa dal browser, con uso di uno strumento | «+ Nuova chat» → chat 6; «Che ore sono a Tokyo?» → «Attualmente sono le 01:22:58 del 18 novembre 2026 a Tokyo.», strumento `orologio` (Asia/Tokyo), 111 s, indicatore di attesa e invio bloccato durante il turno; titolo della chat aggiornato nell'elenco; conversazione proseguita nella stessa chat (note, sotto) | **riuscita** |
| F2 | Chat creata dall'interfaccia ancora presente dopo il riavvio | Fermati back-end e front-end, `docker compose restart postgres`, riavviati i due servizi: chat 6 «Che ore sono a Tokyo?» con 8 messaggi in `GET /api/chat/6`; nel browser, dopo Ctrl+F5, chat in elenco e messaggi visibili | **riuscita** |
| F3 | Agente spento: l'interfaccia mostra l'errore senza bloccarsi | Agente fermato; «Che ore sono a Roma?» → `POST /api/chat/6/messaggi` 503, riquadro rosso «Agente non raggiungibile su http://localhost:8002», domanda di nuovo nel campo; subito dopo aperte la chat 4 e la chat 6 (200) | **riuscita** |
| F4 | Ciclo di conferma di `elimina_nota` dal browser | «Aggiungi una nota personale con il testo: riunione del lunedì» → nota 3 creata (143 s); «Elimina la mia nota personale «riunione del lunedì»» → finestra di conferma con `elimina_nota` (183 s), **Annulla** → nulla eseguito né salvato; stessa domanda (207 s) → **Conferma** → turno ripetuto con `conferme`, log `conferma dell'utente: strumento=elimina_nota esito=sì`, «Nota 3 eliminata» (223 s). In `GET /api/chat/6` solo lo scambio confermato, nessuno dei due tentativi in attesa di conferma | **riuscita** |

### Comportamenti inattesi (registrati, non nascosti)

- **Falso rifiuto del Router:** «Aggiungi una nota: comprare il latte» → `fuori_ambito` («richiesta di azione pratica non informativa», 62 s), risposta fissa di rifiuto mostrata dalla pagina come le altre risposte. Con «Aggiungi una nota personale con il testo: …» la domanda è passata. Limitazione nota degli Step 1–4, Router non modificato.
- **Turni lunghi:** i turni con `elimina_nota` hanno richiesto da 183 a 223 s, oltre i 1–3 minuti stimati; nessun timeout è scaduto (inoltro con lettura senza limite, `fetch` senza timeout).
- **Primo giro di prove:** il primo esito comunicato non trovava riscontro nei log (nessuna richiesta dal browser alla porta 8004) per un'incomprensione sulle istruzioni; le prove sono state rifatte e verificate nei log.
- **Riavvio su Windows:** `.venv\Scripts\python.exe` avvia un processo figlio; fermare solo il processo padre lascia il servizio in ascolto. Per il riavvio di F2 sono stati fermati anche i figli.

### Non verificati dal vivo

- LM Studio spento o database non raggiungibile visti dal browser: stesso percorso di F3 (503 `{"errore": ...}` del back-end mostrato nel riquadro), non provati a mano.
- Front-end in Docker Compose: escluso, è lo Step 9.
- Una sola prova in un browser desktop; layout per schermi stretti (sotto 720 px) e tema scuro non provati.