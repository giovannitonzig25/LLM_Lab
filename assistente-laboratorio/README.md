# Assistente del laboratorio

Applicazione da terminale in Python con un grafo LangGraph esplicito. Specifica e piano: `docs/superpowers/`.

## Ambiente (PowerShell, da `assistente-laboratorio/`)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Test automatici

Non richiedono rete né modello.

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

## Configurazione

Il server di LM Studio deve essere attivo. Copia il file di esempio (il file `.env` reale resta fuori da Git) e controlla l'identificativo del modello:

```powershell
Copy-Item .env.example .env
Get-Content .env -Encoding UTF8 | Where-Object { $_ -match '^\s*[^#\s]' } | ForEach-Object { $n, $v = $_ -split '=', 2; Set-Item -Path "env:$n" -Value $v }
.\.venv\Scripts\python.exe prove_reali\verifica_modelli.py
```

`-Encoding UTF8` serve in Windows PowerShell 5.1: senza, le lettere accentate di `.env` (per esempio in `AMBITO_AGENTE`) arrivano al programma alterate («attività» diventa «attivitÃ »).

Lo script elenca gli identificativi restituiti da `GET /v1/models` ed esce con errore se `LM_STUDIO_MODEL` non è tra questi. Variabili:

| Variabile | Significato |
|---|---|
| `LM_STUDIO_BASE_URL` | indirizzo del server, per esempio `http://localhost:1234/v1` (obbligatoria) |
| `LM_STUDIO_MODEL` | identificativo del modello (obbligatoria) |
| `AMBITO_AGENTE` | ambito dell'agente in una riga, al massimo 500 caratteri (obbligatoria): lo usa il Router per classificare le domande e compare nel messaggio di rifiuto. Chi aggiorna da una versione precedente deve aggiungere la riga al proprio `.env` (il valore di esempio è in `.env.example`), altrimenti il programma non parte |
| `MAX_PASSAGGI` | budget di passaggi di ogni tentativo dell'agente, predefinito 6 (vedi «Limite di passaggi») |
| `MAX_REVISIONI` | correzioni che il Revisore può chiedere all'agente per ogni domanda, intero ≥ 0, predefinito 1. Con 0 il Revisore giudica comunque ogni risposta (e aggiunge la sua latenza), ma non chiede mai correzioni |
| `MCP_URL` | indirizzo del server MCP delle note, predefinito `http://localhost:8001/mcp` |
| `MCP_TIMEOUT` | secondi massimi per discovery e invocazione MCP (> 0), predefinito 10 |
| `MCP_ATTESA_AVVIO` | secondi di attesa all'avvio perché il server MCP risponda (≥ 0), predefinito 0 in locale e 20 in Compose |
| `MCP_DOCKER_URL` | solo Compose: indirizzo del server MCP visto dal container, predefinito `http://server-mcp:8001/mcp` |
| `SERVIZI_BASE_URL` | indirizzo del servizio HTTP di date e scadenze, predefinito `http://localhost:8000` |
| `SERVIZI_TIMEOUT` | secondi massimi per ogni richiesta al servizio (> 0), predefinito 10 |
| `SERVIZI_DOCKER_URL` | solo Compose: indirizzo del servizio visto dal container, predefinito `http://servizi-http:8000` |

Lato servizio HTTP (`python -m assistente.servizi_http`): `SERVIZI_HOST` (predefinito `127.0.0.1`), `SERVIZI_PORT` (predefinito `8000`).

Lato server MCP (`python -m assistente.server_mcp`): `NOTE_DB_PATH` (file SQLite, predefinito `data/note.db`), `MCP_HOST` (predefinito `127.0.0.1`), `MCP_PORT` (predefinito `8001`).

## Avvio

Dopo aver caricato le variabili nella stessa finestra di PowerShell:

```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.terminale
```

Uscita: `esci`, Ctrl+C o Ctrl+D.

### Server MCP delle note (uso locale)

Gli strumenti `aggiungi_nota`, `elenca_note` ed `elimina_nota` sono esposti da un server MCP (Streamable HTTP) che gira come processo separato. Avvialo in **un'altra finestra di PowerShell**, sempre da `assistente-laboratorio/`, e poi avvia l'agente come sopra:

```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.server_mcp
```

Le note stanno in `data/note.db` (cartella ignorata da Git). All'avvio l'agente fa la discovery degli strumenti: nei log compare `strumenti scoperti su http://localhost:8001/mcp: [...]`.

**Avvio ridotto.** Se il server MCP non risponde, l'agente parte lo stesso con i soli strumenti locali (`orologio`) e scrive su stderr «Server MCP non raggiungibile su …». La discovery non viene ripetuta nei turni successivi: riavvia l'agente quando il server è attivo. Con `MCP_ATTESA_AVVIO` maggiore di 0 l'agente riprova ogni secondo, ma solo all'avvio.

**Eliminazione delle note.** `elimina_nota` è dichiarato dal server con l'annotazione MCP `destructiveHint`. Prima di chiamarlo, l'agente chiede nel terminale `Confermi: elimina_nota {'id': 3}? [s/N]`: solo `s`, `si` o `sì` fanno partire la cancellazione; qualsiasi altra risposta, Ctrl+D o l'assenza della domanda la impediscono, qualunque cosa il modello scriva negli argomenti. **Limite:** la protezione riguarda l'uso tramite questo agente. Il server da solo non verifica nulla, quindi un altro client MCP collegato alla porta 8001 può cancellare le note senza conferma.

### Servizio HTTP di date e scadenze (uso locale)

Gli strumenti `giorni_lavorativi` e `calcola_scadenza` chiamano un servizio FastAPI separato. Avvialo in **un'altra finestra di PowerShell**, da `assistente-laboratorio/`:

```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.servizi_http
```

Endpoint: `GET /giorni-lavorativi?da=AAAA-MM-GG&a=AAAA-MM-GG`, `GET /scadenza?da=AAAA-MM-GG&giorni=N` (1-365), `GET /salute`. Sabato, domenica e festività nazionali italiane sono esclusi; il giorno di partenza di una scadenza non conta. Sono coperti solo gli anni **2026 e 2027**: date fuori da questi anni, non valide, intervalli invertiti, `giorni` fuori 1-365 o scadenze che uscirebbero dal 2027 danno `422` con un messaggio in italiano. Il risultato è indicativo, non normativo (nessuna festività patronale).

### Catalogo dei corsi (fittizio)

Lo stesso servizio espone un catalogo di 10 corsi **fittizi** (nessun dato reale: titoli, sedi e descrizioni sono inventati per il laboratorio, il file è `src/assistente/servizi_http/dati/catalogo.json`) e ogni risposta lo ricorda. Endpoint: `GET /catalogo?q=<testo>&max_risultati=N` (`q` obbligatorio, al massimo 100 caratteri; `max_risultati` da 1 a 10, predefinito 5) e `GET /catalogo/{codice}` (per esempio `ITS-003`, 404 se inesistente). La ricerca ignora maiuscole e accenti e cerca solo in titolo, settore e sede (con più parole devono comparire tutte); i risultati contengono codice, titolo, settore e sede, mentre durata e descrizione compaiono solo nel dettaglio. Gli strumenti sono `cerca_catalogo` (parola chiave) e `dettaglio_catalogo` (codice noto); una ricerca senza risultati dà `Nessun corso trovato ...` e un codice inesistente `Errore: corso <codice> non trovato`.

Gli strumenti HTTP sono **sempre registrati**, senza discovery: se il servizio è spento il modello riceve `Errore: servizio non raggiungibile su ...` alla chiamata e la chat continua.

La cronologia vale per la sessione: dentro la stessa esecuzione il modello ricorda i turni precedenti, al riavvio riparte da zero. Se un turno fallisce (per esempio server spento) la cronologia resta com'era prima della domanda.

## Avvio con Docker Compose

LM Studio resta sull'host; nel container l'indirizzo è `http://host.docker.internal:1234/v1` (Compose lo imposta al posto di quello di `.env`; per un'altra porta o indirizzo definisci `LM_STUDIO_DOCKER_URL` in `.env`). `LM_STUDIO_MODEL`, `MAX_PASSAGGI` e `MAX_REVISIONI` vengono da `.env`.

```powershell
docker compose build
docker compose run --rm assistente
```

Compose avvia tre servizi con la stessa immagine: `server-mcp` (porta pubblicata solo su `127.0.0.1:8001`, note nel volume `dati-note`), `servizi-http` (solo su `127.0.0.1:8000`; il controllo di salute fa una richiesta HTTP reale a `/salute`) e `assistente`. `docker compose run --rm assistente` avvia anche il server, se non è già attivo. Lo stato del server si vede con `docker compose ps`: il controllo di salute fa una vera discovery MCP (`python -m assistente.verifica_mcp`), non solo una connessione alla porta.

```powershell
docker compose up -d server-mcp                  # avvia solo il server (stato healthy dopo pochi secondi)
docker compose run --rm --no-deps assistente python -m assistente.verifica_mcp   # discovery dal container: esce con 0 e stampa gli strumenti
docker compose logs server-mcp                   # log del server
docker compose down                              # ferma tutto: le note restano nel volume
docker compose down -v                           # ferma tutto E cancella le note
```

L'agente in Compose usa `SERVIZI_BASE_URL=http://servizi-http:8000` (`SERVIZI_DOCKER_URL` per cambiarlo) e `MCP_URL=http://server-mcp:8001/mcp` (`MCP_DOCKER_URL` per cambiarlo) e aspetta fino a `MCP_ATTESA_AVVIO` secondi (20) che il server risponda.

Anche `servizi-http` è una dipendenza con `condition: service_started`: se è fermo l'agente parte lo stesso e gli strumenti HTTP rispondono `Errore: servizio non raggiungibile ...` (provato con `docker compose run --rm --no-deps assistente`).

**Avvio ridotto in Docker.** L'agente dipende da `server-mcp` con `condition: service_started`, non da `service_healthy`: se il server è fermo, in crash o non sano, l'agente parte comunque con il solo `orologio` e l'avviso. Se invece il server **non riesce nemmeno a partire** (per esempio la porta 8001 dell'host è occupata), `docker compose run --rm assistente` fallisce perché Compose non avvia la dipendenza («ports are not available»). In quel caso usa:

```powershell
docker compose run --rm --no-deps assistente
```

che non avvia il server e dà l'avvio ridotto.

Per controllare dal container che l'host sia raggiungibile e il modello presente:

```powershell
docker compose run --rm --entrypoint python assistente prove_reali/verifica_modelli.py
```

Se l'host non è raggiungibile controlla che il server di LM Studio sia attivo e la porta; se non basta, in LM Studio abilita «Serve on Local Network». Nelle prove fatte con Docker Desktop su Windows non è stato necessario aggiungere `extra_hosts`.

## Strumenti disponibili

Il modello dispone di 11 strumenti, composti all'avvio. Sono i locali, i wrapper HTTP (sempre registrati) e quelli **scoperti** dal server MCP (nome, descrizione e schema vengono dalla discovery, non sono scritti nel client).

| Strumento | Dove gira | Cosa fa |
|---|---|---|
| `orologio` | locale | data e ora in un fuso IANA |
| `converti_unita` | locale | conversione tra unità di un elenco chiuso (lunghezza, massa, volume, temperatura) |
| `calcola` | locale | espressioni con `+ - * / **` e parentesi (con `ast`, mai `eval`) |
| `giorni_lavorativi`, `calcola_scadenza` | servizio FastAPI | giorni lavorativi e scadenze (anni 2026-2027, risultato non normativo) |
| `cerca_catalogo`, `dettaglio_catalogo` | servizio FastAPI | catalogo di 10 corsi **fittizi** |
| `aggiungi_nota`, `elenca_note`, `elimina_nota` | server MCP | note in SQLite; `elimina_nota` chiede conferma nel terminale |
| `meteo` | server MCP | tempo attuale da Open-Meteo (serve Internet) |

Nei log su stderr compaiono `strumenti scoperti su ...` (discovery MCP), `strumento richiesto` e `strumento eseguito` per ogni chiamata.

## Strumento orologio e log

Il modello può chiedere lo strumento `orologio`, con un fuso orario IANA (`timezone`, predefinito `Europe/Rome`). Il grafo lo esegue davvero e restituisce il risultato al modello. Ogni richiesta e ogni esito compaiono nei log su stderr:

```
INFO assistente.strumenti: strumento richiesto: nome=orologio argomenti={'timezone': 'Asia/Tokyo'}
INFO assistente.strumenti: strumento eseguito: nome=orologio risultato=2026-11-02 01:48:55 (Asia/Tokyo, UTC+09:00)
```

Un fuso non valido o uno strumento inesistente non fanno cadere il programma: il modello riceve un risultato che inizia con `Errore:`.

## Router di ambito

Prima dell'agente un nodo **Router** chiede al modello di classificare la domanda:

```
START → router ─┬─ conversazione → modello ⇄ strumenti → revisore → … (vedi «Revisore della risposta»)
                └─ fuori_ambito  → rifiuto → END
```

- **Ambito:** viene solo da `AMBITO_AGENTE`. Nei casi ambigui il Router lascia passare la domanda (`conversazione`); rifiuta solo quelle chiaramente estranee.
- **Domande di continuazione** («E domani?», «E a Trieste?»): il Router vede gli ultimi 2 turni (domanda e risposta finale, troncate a 300 e 500 caratteri, senza i risultati degli strumenti) e classifica solo la domanda attuale.
- **Output strutturato:** client separato **senza strumenti**, `reasoning_effort="none"`, schema JSON (`categoria`, `motivo`) validato con Pydantic. Il client dell'agente non cambia.
- **Rifiuto:** testo fisso, senza chiamare il modello né gli strumenti:
  ```
  Mi dispiace, questa richiesta è fuori dal mio ambito.
  Ambito dell'assistente: «<AMBITO_AGENTE>»
  ```
  Domanda e rifiuto restano nella cronologia della sessione come un turno normale; categoria e motivo no.
- **Errori:**
  - output non valido (JSON errato, categoria sconosciuta, motivo vuoto, risposta vuota o troncata): la domanda passa all'agente (*fail-open*) con un `WARNING`;
  - server non raggiungibile o timeout: stesso messaggio di errore di sempre, cronologia invariata.
- **`MAX_PASSAGGI`** resta il margine dell'agente: il passaggio del Router è aggiunto a parte (formula completa in «Limite di passaggi»).

**Il Router è un filtro di pertinenza, non un meccanismo di sicurezza.** Nessuna protezione dipende da lui: la cancellazione delle note resta protetta dalla conferma nel terminale.

Nei log su stderr, per ogni turno:

```
INFO assistente.router: router: categoria=conversazione motivo=richiesta di orari e fusi orari durata=31.2s → agente
INFO assistente.router: agente: chiamata al modello
INFO assistente.router: router: categoria=fuori_ambito motivo=richiesta creativa durata=28.0s → rifiuto
INFO assistente.router: rifiuto: risposta fissa, agente non eseguito
WARNING assistente.router: router: classificazione non valida (ValidationError: campi categoria), inoltro all'agente durata=30.5s
```

Gli esempi mostrano il formato, non esiti misurati. L'assenza di `agente: chiamata al modello` in un turno rifiutato dimostra che l'agente non è stato eseguito. Nei log il motivo è troncato a 120 caratteri e non compaiono mai la domanda, il contesto né l'output grezzo del modello.

## Revisore della risposta

Dopo ogni risposta finale dell'agente un nodo **Revisore** chiede al modello se la risposta è coerente con la domanda:

```
START → router ─┬─ conversazione → modello ─┬─ richiesta di strumenti → strumenti → modello
                │                           ├─ risposta vuota → END
                │                           └─ risposta → revisore ─┬─ coerente / limite / errore → END
                │                                                   └─ da correggere → modello (con un'osservazione)
                └─ fuori_ambito → rifiuto → END
```

- **Criterio:** la risposta deve affrontare tutte le parti esplicite della domanda e restare pertinente. Il Revisore **non** verifica l'esattezza dei dati (orari, date, meteo, risultati dei servizi), né stile o lunghezza. Sono coerenti anche una richiesta di chiarimento quando manca un'informazione indispensabile e la segnalazione concreta che un servizio non è disponibile. Nei casi dubbi approva.
- **Che cosa vede:** la domanda originale del turno, l'ultima risposta proposta e gli ultimi 2 turni (troncati come per il Router), mai i risultati degli strumenti. Client separato **senza strumenti**, `reasoning_effort="none"`, schema JSON (`coerente`, `motivo`) validato con Pydantic.
- **Correzione:** se la risposta non è coerente, il motivo arriva all'agente come osservazione («Osservazione del revisore (non è una nuova domanda dell'utente): …»). L'agente risponde di nuovo e può usare ancora gli strumenti; l'osservazione gli chiede di non ripetere le azioni già eseguite nel turno, ma un modello può ignorarla (vedi «Limitazioni note»).
- **Limite di revisioni:** al massimo `MAX_REVISIONI` correzioni per domanda (predefinito 1, quindi il Revisore giudica al massimo 2 volte). Se l'ultimo giudizio è ancora negativo viene restituita l'ultima risposta e nei log compare un `WARNING`; all'utente non viene aggiunto nessun avviso. Il contatore riparte da zero a ogni domanda.
- **Cronologia:** la sessione conserva tutto il turno, comprese la prima risposta scartata e l'osservazione. Nelle domande successive però l'agente, il Router e il Revisore non le vedono: l'agente riceve la domanda, le richieste e i risultati degli strumenti e la risposta finale; Router e Revisore solo domanda e risposta finale.
- **Errori del Revisore:** se il giudizio non è valido (JSON errato, campo mancante, risposta vuota o troncata) o il server non risponde, viene restituita la risposta dell'agente **senza revisione** (*fail-open*), con un `WARNING`. Il caso non viene mai registrato come approvazione.
- Il rifiuto del Router e le risposte vuote non passano dal Revisore.

Nei log su stderr (esempi del formato, non esiti misurati):

```
INFO assistente.revisore: revisore: coerente=true motivo=risponde a entrambe le parti durata=12.3s → fine
INFO assistente.revisore: revisore: coerente=false motivo=manca il meteo di Roma durata=11.8s → correzione 1/1
INFO assistente.revisore: revisore: coerente=false motivo=manca ancora il meteo durata=12.0s → limite
WARNING assistente.revisore: revisore: limite di revisioni raggiunto (1), restituita l'ultima risposta
WARNING assistente.revisore: revisore: giudizio non valido (ValidationError: campi coerente), risposta restituita senza revisione durata=10.2s
WARNING assistente.revisore: revisore: non disponibile (APIConnectionError), risposta restituita senza revisione durata=2.1s
```

Il motivo nei log è troncato a 120 caratteri, su una riga; non compaiono mai la domanda, la risposta, il contesto né l'output grezzo del modello.

## Limite di passaggi

Il limite di LangGraph (`recursion_limit`) per ogni domanda è:

```
1 (Router) + (MAX_REVISIONI + 1) × (MAX_PASSAGGI + 1 (Revisore))
```

Con i valori predefiniti (6 e 1) è 15; con `MAX_REVISIONI=0` è 8. `MAX_PASSAGGI` è quindi il **budget nominale di ogni tentativo** dell'agente, non un limite rigido per tentativo: il limite è unico per tutta la domanda, e un tentativo può usare anche il margine non speso dagli altri.

Valori misurati con modelli simulati (LangGraph 1.2.19), fissati da `test_caratterizza_il_limite_di_passaggi` e dai test del limite in `tests/test_revisore.py`:

- **Ciclo infinito di strumenti** (il modello chiede sempre lo strumento): con i predefiniti il modello è chiamato 7 volte e lo strumento eseguito 7 volte prima dell'interruzione (nello Step 1 erano 3 e 3); con `MAX_PASSAGGI=2` 3 e 3; con `MAX_REVISIONI=0` 4 e 3 (`MAX_PASSAGGI=6`) oppure 2 e 1 (`MAX_PASSAGGI=2`).
- **Turni riusciti:** con il limite 15 un turno può usare al massimo 14 passaggi; un turno con giudizio finale ne usa sempre un numero dispari, quindi al massimo 13. Per esempio 3 giri di strumenti, una correzione con 1 giro e i due giudizi (13) si completano; con 2 giri nella correzione (15) il turno si interrompe, anche se il Revisore era già stato chiamato due volte.
- **Valori piccoli:**

  | `MAX_PASSAGGI` | `MAX_REVISIONI` | risposta senza strumenti | un giro di strumento | una correzione senza strumenti |
  |---|---|---|---|---|
  | 1 | 0 | interrotta | interrotta | — |
  | 1 | 1 | completata | interrotta | interrotta |
  | 2 | 0 | completata | interrotta | — |
  | 2 | 1 | completata | completata | completata |
  | 3 | 0 | completata | interrotta | — |
  | 3 | 1 | completata | completata | completata |

  Con `MAX_PASSAGGI=1` nessuna correzione rientra nel limite. Il rifiuto del Router usa 2 passaggi e si completa con qualunque valore.

Quando il limite è raggiunto il turno viene scartato: la cronologia torna a com'era prima della domanda, compare un messaggio («La richiesta non è stata completata: raggiunto il limite di N passaggi…», dove N è `MAX_PASSAGGI`) e la chat continua. È un caso diverso dal limite di revisioni, che invece restituisce l'ultima risposta.

## Struttura

```
src/assistente/   config, modello (LM Studio), grafo (LangGraph), terminale
                  router (Router di ambito: contesto, prompt, rifiuto)
                  revisore (Revisore della risposta: giudizio, osservazione, contesto dell'agente)
                  strumenti (orologio e composizione), unita, calcolatrice
                  mcp_client, verifica_mcp (client MCP e controllo di salute)
                  server_mcp, note, meteo (server MCP)
                  strumenti_http, servizi_http/ (wrapper e servizio FastAPI)
tests/            test automatici, senza rete né modello
prove_reali/      prove con LM Studio e Docker, da eseguire a mano
docs/superpowers/ specifica e piano
```

## Limitazioni note

- **Latenza del Router:** ogni domanda richiede una classificazione in più prima dell'agente. Nelle prove reali del 2026-11-15 (`google/gemma-4-e2b`, 19 classificazioni, in locale e in Docker) ogni classificazione ha richiesto da 6,9 a 61,3 s, **mediana 40,5 s**: quasi sempre fra 33 e 61 s, una sola volta 6,9 s, per una causa non verificata. È accettata provvisoriamente come limite dell'ambiente locale, non come prestazione adeguata. Dettagli in `prove_reali/PROVE.md`.
- **Latenza del Revisore:** ogni domanda in ambito richiede un giudizio in più dopo la risposta (anche con `MAX_REVISIONI=0`), e ogni correzione aggiunge una risposta dell'agente e un altro giudizio. Nelle prove reali del 2026-11-15 (27 giudizi) il Revisore ha richiesto da 5,6 a 57,8 s, mediana 9,7 s; un turno completo da 32 a 204 s, mediana 99 s. Dettagli in `prove_reali/PROVE.md`.
- **Falsi rifiuti del Revisore:** nelle prove reali la risposta completa a «Che ore sono a Tokyo e che tempo fa a Roma?» è stata respinta 3 volte su 3 in locale («informazioni datate», orario «attuale o futuro»): nelle due sessioni con `MAX_REVISIONI=1` è stata approvata dopo la correzione, in quella con `MAX_REVISIONI=0` è stata restituita con il `WARNING` di limite. In Docker la stessa domanda è stata approvata al primo giudizio. Limitazione accettata per lo Step 2: un eventuale miglioramento delle istruzioni andrà valutato separatamente, con nuovi esperimenti e test.
- **Correzione vuota:** se il Revisore respinge una risposta e la correzione dell'agente è vuota, il turno termina con l'avviso di risposta vuota e la prima risposta (la bozza respinta) non viene mostrata. Resta nella cronologia della sessione, ma nelle domande successive non viene passata né all'agente né al Router e al Revisore. È il comportamento previsto dalla specifica (le risposte vuote non passano dal Revisore), accettato come limitazione. Con il limite predefinito la risposta arriva comunque, ma il turno si allunga e gli strumenti vengono rieseguiti. Le istruzioni del Revisore non sono state modificate: farlo richiede di ripetere lo spike.
- **Revisore e dati:** il Revisore controlla coerenza e completezza, non l'esattezza: una risposta completa ma sbagliata (nelle prove, 15 per 7 calcolato come 15/7) viene approvata. Il motivo che l'agente riceve può essere impreciso, e a volte il Revisore esce dal suo criterio (ha respinto un calcolo sbagliato).
- **Azioni ripetute durante una correzione:** l'agente può richiamare uno strumento già eseguito nel turno. Per gli strumenti che leggono costa solo tempo; con `aggiungi_nota` può creare una nota duplicata, perché il modello può ignorare l'avvertenza dell'osservazione. Non esiste un blocco automatico; `elimina_nota` resta protetto dalla conferma nel terminale.
- **Errori del Revisore:** se il giudizio non è valido o il server non risponde, la risposta arriva senza revisione e può essere incompleta (`WARNING` nei log).
- **Cronologia:** con le correzioni la cronologia della sessione cresce (al massimo una risposta scartata e un'osservazione per domanda con il predefinito).
- **Motivo nei log:** è testo generato dal modello. Troncamento e istruzioni dello schema riducono il rischio che riporti parti della richiesta, ma non lo azzerano.
- **Modello piccolo e sessioni lunghe:** con tutti gli 11 strumenti registrati, `google/gemma-4-e2b` a volte **non chiama lo strumento** e risponde a parole o dalla cronologia. In due sessioni di 22 domande è successo ogni volta sulle stesse 4 domande (catalogo, note, meteo), quindi in modo riproducibile; le stesse domande, in sessioni nuove, hanno scelto lo strumento giusto 12 volte su 12. Non è stato mai chiamato uno strumento sbagliato. Se la risposta sembra inventata o obsoleta (per esempio un elenco di note), riformula la domanda o riavvia l'agente. L'elenco delle note mostrato dal modello senza chiamata può non essere aggiornato. Vedi `prove_reali/PROVE.md`.
- **Conferma di cancellazione:** una cancellazione non parte mai senza il tuo `s` nel terminale; se il modello non chiama `elimina_nota` non compare la domanda `[s/N]` e non viene cancellato nulla. Con input da pipe una domanda saltata disallinea le righe successive.
- **Servizi e porte occupate:** se una porta pubblicata (8001 per `server-mcp`, 8000 per `servizi-http`) è già in uso dall'host, `docker compose run --rm assistente` fallisce perché Compose non avvia la dipendenza; usa `docker compose run --rm --no-deps assistente`. Provato per la porta 8001 e per la 8000.
- **Catalogo e date:** i corsi sono fittizi e le date sono limitate al 2026-2027.
- **Immagine Docker:** il codice è copiato nell'immagine al momento della build. Dopo ogni modifica a `src/` esegui `docker compose build`, altrimenti `docker compose run` usa l'immagine vecchia.
- **`MAX_PASSAGGI` piccolo:** con `MAX_REVISIONI=1` (predefinito) e `MAX_PASSAGGI=1` nessuna correzione e nessun giro di strumento rientrano nel limite; con 2 o più sì. Con `MAX_REVISIONI=0` un giro di strumento richiede almeno `MAX_PASSAGGI=4`. Tabella completa in «Limite di passaggi».
- **Fuso orario:** un valore con spazi ai lati (`" Asia/Tokyo"`) viene rifiutato con un errore, e per argomenti del tipo sbagliato il messaggio restituito al modello è lungo.
- **Errori imprevisti:** un'eccezione non legata al server del modello (per esempio una richiesta di strumento senza identificativo) interrompe la sessione.
- **Input non valido:** i byte non validi in UTF-8 che il terminale può inviare (per esempio con certi caratteri incollati come `«»`, `°` o uno spazio non separabile in una sessione interattiva di Docker) vengono sostituiti con «�» prima di essere inviati al modello: la sessione non si interrompe, ma il modello vede quel carattere sostitutivo. Conviene riscrivere la riga.
- **Prompt:** dopo Ctrl+C o Ctrl+D il cursore può restare sulla riga di «Tu: ».

## Diagnosi

- **Variabile mancante:** il programma lo dice e termina con codice 1.
- **«Non riesco a ottenere una risposta dal server»:** LM Studio è spento o `LM_STUDIO_BASE_URL` è sbagliato. La chat resta aperta: riavviato il server, si può riprovare.
- **Identificativo del modello:** LM Studio con un solo modello caricato ha risposto anche a un identificativo inesistente, quindi un errore di battitura può non dare errori. Verifica sempre con `prove_reali\verifica_modelli.py`.
