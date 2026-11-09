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
