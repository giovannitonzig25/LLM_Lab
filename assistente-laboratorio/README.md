# Assistente del laboratorio

Agente in Python con un grafo LangGraph esplicito, esposto come servizio HTTP (FastAPI) e usato da una CLI da terminale che ne è client. Specifica e piano: `docs/superpowers/`.

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
| `SOGLIA_RIASSUNTO` | numero di messaggi oltre il quale i turni più vecchi vengono riassunti (vedi «Riassunto della cronologia»), intero ≥ 1, predefinito 20; vuota vale 20, altri valori fermano l'avvio con un errore che nomina la variabile |
| `MCP_URL` | indirizzo del server MCP delle note, predefinito `http://localhost:8001/mcp` |
| `MCP_TIMEOUT` | secondi massimi per discovery e invocazione MCP (> 0), predefinito 10 |
| `MCP_ATTESA_AVVIO` | secondi di attesa all'avvio perché il server MCP risponda (≥ 0), predefinito 0 in locale e 20 in Compose |
| `MCP_DOCKER_URL` | solo Compose: indirizzo del server MCP visto dal container, predefinito `http://server-mcp:8001/mcp` |
| `SERVIZI_BASE_URL` | indirizzo del servizio HTTP di date e scadenze, predefinito `http://localhost:8000` |
| `SERVIZI_TIMEOUT` | secondi massimi per ogni richiesta al servizio (> 0), predefinito 10 |
| `SERVIZI_DOCKER_URL` | solo Compose: indirizzo del servizio visto dal container, predefinito `http://servizi-http:8000` |

Lato servizio dell'agente (`python -m assistente.servizio_agente`): `AGENTE_HOST` (predefinito `127.0.0.1`), `AGENTE_PORT` (predefinito `8002`); tutte le variabili della tabella sopra si leggono qui. Lato CLI (`python -m assistente.terminale`): solo `AGENTE_URL` (predefinito `http://localhost:8002`).

Lato servizio HTTP (`python -m assistente.servizi_http`): `SERVIZI_HOST` (predefinito `127.0.0.1`), `SERVIZI_PORT` (predefinito `8000`).

Lato server MCP (`python -m assistente.server_mcp`): `NOTE_DB_PATH` (file SQLite, predefinito `data/note.db`), `PREFERENZE_PATH` (file delle preferenze, predefinito `data/preferenze.json` nella cartella del progetto, vedi «Preferenze dell'utente»), `MCP_HOST` (predefinito `127.0.0.1`), `MCP_PORT` (predefinito `8001`).

## Avvio

Servono quattro finestre di PowerShell, tutte da `assistente-laboratorio/` con `$env:PYTHONPATH = "src"`: server MCP (porta 8001) e servizio HTTP (porta 8000), descritti sotto, poi l'agente e la CLI. Nella finestra dell'agente carica prima le variabili di `.env`:

```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.servizio_agente   # agente, porta 8002
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.terminale         # CLI, in un'altra finestra
```

Uscita dalla CLI: `esci`, Ctrl+C o Ctrl+D. Se l'agente non è attivo la CLI stampa `Agente non raggiungibile su http://localhost:8002…` ed esce con codice 1; se l'agente è attivo ma MCP o il modello non sono raggiungibili, stampa un avviso e prosegue.

### API dell'agente

L'agente è senza stato: a ogni chiamata riceve la cronologia (messaggi LangChain serializzati con `messages_to_dict`) e il riassunto, e li restituisce aggiornati. La documentazione OpenAPI è su `http://localhost:8002/docs`.

| Endpoint | Uso |
|---|---|
| `POST /chat` | `{messaggio \| messaggi, cronologia, riassunto, conferme}` → `{risposta, cronologia, riassunto, strumenti_usati, conferme_richieste}` |
| `GET /stato` | `{agente, mcp, modello}`: 200 se tutto è raggiungibile, altrimenti 503 col motivo |
| `GET /prompts`, `POST /prompts/{nome}` | prompt MCP (usati dai comandi `/prompts` e `/prompt`); 503 se MCP è spento |

```powershell
$r = Invoke-RestMethod -Method Post -Uri http://localhost:8002/chat -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes('{"messaggio": "Che ore sono a Tokyo?"}'))
$r.risposta; $r.strumenti_usati
Invoke-RestMethod http://localhost:8002/stato
```

Errori: 503 se LM Studio non è raggiungibile (`{"errore": "Non riesco a ottenere una risposta dal server del modello…"}`), 502 per altri errori del modello, 422 per una richiesta malformata (anche `messaggio` e `messaggi` insieme). Il limite di passaggi e gli strumenti in errore rispondono 200, come nella CLI. Nel log dell'agente ogni turno chiude con `turno: esito=… strumenti=[…] durata=…`, preceduto dalle righe `strumento richiesto` / `strumento eseguito`.

### Server MCP delle note (uso locale)

Gli strumenti `aggiungi_nota`, `elenca_note` ed `elimina_nota` sono esposti da un server MCP (Streamable HTTP) che gira come processo separato. Avvialo in **un'altra finestra di PowerShell**, sempre da `assistente-laboratorio/`, e poi avvia l'agente come sopra:

```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.server_mcp
```

Le note stanno in `data/note.db` (cartella ignorata da Git). All'avvio l'agente fa la discovery degli strumenti: nei log compare `strumenti scoperti su http://localhost:8001/mcp: [...]`.

**Avvio ridotto.** Se il server MCP non risponde, l'agente parte lo stesso con i soli strumenti locali (`orologio`) e scrive su stderr «Server MCP non raggiungibile su …». La discovery non viene ripetuta nei turni successivi: riavvia l'agente quando il server è attivo. Con `MCP_ATTESA_AVVIO` maggiore di 0 l'agente riprova ogni secondo, ma solo all'avvio.

**Eliminazione delle note.** `elimina_nota` è dichiarato dal server con l'annotazione MCP `destructiveHint`. L'agente lo esegue solo se la richiesta HTTP contiene in `conferme` lo stesso strumento con gli stessi argomenti; altrimenti non lo esegue e lo restituisce in `conferme_richieste`. La CLI chiede allora `Confermi: elimina_nota {'id': 3}? [s/N]` e, se confermi, ripete lo stesso turno con la conferma: solo `s`, `si` o `sì` fanno partire la cancellazione; qualsiasi altra risposta, Ctrl+D o l'assenza della domanda la impediscono, qualunque cosa il modello scriva negli argomenti. **Limite:** la protezione riguarda l'uso tramite questo agente. Il server da solo non verifica nulla, quindi un altro client MCP collegato alla porta 8001 può cancellare le note senza conferma.

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

## Preferenze dell'utente

Il server MCP espone la **resource** `utente://preferenze` con tre preferenze: lingua delle risposte, fuso orario predefinito e stile. A differenza degli strumenti, una resource non la sceglie il modello: la legge **l'applicazione** una volta all'avvio di ogni sessione, e le preferenze finiscono in cima al prompt di sistema dell'agente. Cambiando il file cambia il comportamento della sessione successiva, senza toccare il codice.

**Creare il file** (una volta, da `assistente-laboratorio/`; `data/` è ignorata da Git e su un clone nuovo non esiste ancora):

```powershell
New-Item -ItemType Directory -Force data | Out-Null
Copy-Item preferenze.example.json data\preferenze.json
```

Formato (`preferenze.example.json`):

```json
{
  "lingua": "italiano",
  "fuso_orario": "Europe/Rome",
  "stile": "sintetico"
}
```

| Chiave | Valori ammessi |
|---|---|
| `lingua` | testo libero (per esempio `inglese`), al massimo 40 caratteri, su una riga |
| `fuso_orario` | nome IANA, per esempio `Europe/Rome`, `America/New_York`, `Asia/Tokyo` |
| `stile` | `sintetico` oppure `dettagliato` |

Il file può essere salvato anche con BOM (Blocco note, PowerShell 5.1). Il server lo rilegge a ogni richiesta: dopo una modifica basta **riavviare l'agente**, non il server. In locale il percorso viene da `PREFERENZE_PATH`; se manca è `data/preferenze.json` nella cartella del progetto, da qualunque cartella si avvii il server.

**Che cosa cambia:**
- l'orologio usa il fuso preferito quando non ne viene indicato un altro: «Che ore sono?» dà l'ora di quel fuso; «Che ore sono a Tokyo?» resta Tokyo;
- l'agente riceve in cima al prompt di sistema: rispondi in quella lingua, fuso predefinito, stile delle risposte. Router, Revisore e Riassunto non cambiano.

**Valori predefiniti:** `italiano`, `Europe/Rome`, `sintetico`, cioè il comportamento di prima. Si usano per tutti e tre i campi se il server MCP non risponde, se il file manca o non si legge, se il testo non è JSON o non è un oggetto; si usano **solo per un campo** se quel campo manca o non è valido (le chiavi sconosciute vengono ignorate). In ogni caso l'agente parte.

**Log** (logger `assistente.preferenze` nell'agente, `assistente.server_mcp` nel server), separati da quelli degli strumenti (`assistente.mcp`, `assistente.strumenti`):

```
INFO assistente.preferenze: resource utente://preferenze letta da http://localhost:8001/mcp
INFO assistente.preferenze: preferenze della sessione: lingua=inglese (resource), fuso_orario=America/New_York (resource), stile=sintetico (predefinito)
WARNING assistente.preferenze: preferenza stile non valida (ammessi solo sintetico o dettagliato: 'dettagliatissimo'): uso sintetico
WARNING assistente.preferenze: preferenze non disponibili (...): uso i valori predefiniti
```

La riga `preferenze della sessione` c'è sempre e dice per ogni valore se viene dal file (`resource`) o dai valori predefiniti (`predefinito`). Con il server spento compaiono due avvisi distinti: quello degli strumenti MCP (invariato) e quello delle preferenze.

**Docker:** `server-mcp` monta la cartella `./data` dell'host in sola lettura su `/preferenze` (`PREFERENZE_PATH=/preferenze/preferenze.json`). Crea il file prima dell'avvio; dopo una modifica basta un nuovo `docker compose run --rm assistente`, senza `docker compose build`.

## Comandi della CLI: prompt MCP

Il server MCP espone due **prompt**: modelli di istruzioni con argomenti, salvati sul server. Non li sceglie il modello e non sono strumenti: li richiami **tu** con un comando che comincia con `/`. L'agente compila il prompt tramite il server e manda il testo ottenuto al grafo come una domanda qualsiasi, quindi passa anche da Router, strumenti e Revisore.

| Comando | Effetto |
|---|---|
| `/prompts` | elenca i prompt del server con descrizione e argomenti (obbligatori o facoltativi) |
| `/prompt nome argomento=valore …` | richiama un prompt; i valori con spazi vanno tra **virgolette doppie** |

Esempi:

```
/prompt spiega argomento="Model Context Protocol" livello=base
/prompt riassumi_conversazione
/prompt riassumi_conversazione stile="elenco puntato"
```

- `spiega(argomento, livello)`: `livello` vale `base` (predefinito), `intermedio` o `avanzato`. Il livello richiesto prevale sullo stile delle preferenze.
- `riassumi_conversazione(stile)`: `stile` è testo libero (predefinito `breve`) e riassume la sessione in corso.

Prima di chiamare il server l'agente **controlla la richiesta** rispetto all'elenco dei prompt: un prompt sconosciuto, un argomento obbligatorio mancante, un argomento sconosciuto o un valore vuoto bloccano la richiesta con un messaggio e la riga d'uso, senza chiamare il modello e senza toccare la cronologia. Un valore non ammesso dal server (per esempio `livello=esperto`) dà «Prompt non eseguito: …». Prima della risposta il terminale mostra il testo compilato, preceduto da `[prompt nome]`.

Ogni comando interroga il server al momento: se il server MCP è spento i comandi rispondono «Prompt MCP non disponibili: …» e la chat continua; quando il server riparte i prompt tornano disponibili senza riavviare l'agente. Ogni riga che comincia con `/` è un comando: un comando sconosciuto non arriva al modello.

**Log:** `assistente.mcp` registra i prompt scoperti, il prompt richiamato con gli argomenti e i messaggi ottenuti dal server; `assistente.comandi` registra le richieste respinte dal controllo.

```
INFO assistente.mcp: prompt richiamato: nome=spiega argomenti={'argomento': 'Model Context Protocol', 'livello': 'base'}
INFO assistente.mcp: prompt ottenuto: nome=spiega messaggi=[('user', "Spiega l'argomento «Model Context Protocol» a livello base. …")]
WARNING assistente.comandi: richiesta respinta: prompt=spiega argomenti={} problemi=['Argomenti obbligatori mancanti: argomento.', …]
```

## Avvio con Docker Compose

LM Studio resta sull'host; nel container l'indirizzo è `http://host.docker.internal:1234/v1` (Compose lo imposta al posto di quello di `.env`; per un'altra porta o indirizzo definisci `LM_STUDIO_DOCKER_URL` in `.env`). `LM_STUDIO_MODEL`, `MAX_PASSAGGI`, `MAX_REVISIONI` e `SOGLIA_RIASSUNTO` vengono da `.env`.

```powershell
docker compose build
docker compose run --rm assistente
```

Compose avvia quattro servizi con la stessa immagine: `agente` (servizio HTTP dell'agente, solo su `127.0.0.1:8002`, con le variabili di `.env`), `server-mcp` (porta pubblicata solo su `127.0.0.1:8001`, note nel volume `dati-note`), `servizi-http` (solo su `127.0.0.1:8000`; il controllo di salute fa una richiesta HTTP reale a `/salute`) e `assistente` (la CLI, con `AGENTE_URL=http://agente:8002`). `docker compose run --rm assistente` avvia anche agente e server, se non sono già attivi. Lo stato del server si vede con `docker compose ps`: il controllo di salute fa una vera discovery MCP (`python -m assistente.verifica_mcp`), non solo una connessione alla porta.

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
docker compose up -d --no-deps agente
docker compose run --rm --no-deps assistente
```

che avviano l'agente senza il server (avvio ridotto) e poi la CLI. La CLI dipende da `agente` con `condition: service_healthy`: parte quando l'agente risponde, dopo l'eventuale attesa di `MCP_ATTESA_AVVIO`. I log dell'agente (con la traccia degli strumenti) si leggono con `docker compose logs agente`.

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

Il modello può chiedere lo strumento `orologio`, con un fuso orario IANA (`timezone`; se omesso si usa il fuso delle preferenze, `Europe/Rome` senza preferenze). Il grafo lo esegue davvero e restituisce il risultato al modello. Ogni richiesta e ogni esito compaiono nei log su stderr:

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

## Riassunto della cronologia

All'inizio di ogni domanda un nodo **Riassunto** controlla la lunghezza della cronologia, prima del Router:

```
START → riassunto → router ─┬─ conversazione → modello ⇄ strumenti … → revisore → …   (come sopra)
                            └─ fuori_ambito → rifiuto → END
```

- **Quando comprime:** solo se i messaggi della sessione, contata anche la domanda appena scritta, sono **più** di `SOGLIA_RIASSUNTO` (si contano tutti: richieste e risultati degli strumenti, bozze e osservazioni del Revisore) **e** oltre gli ultimi 2 turni completi c'è almeno un turno da togliere. Altrimenti il modello riassuntore non viene chiamato.
- **Che cosa conserva:** gli ultimi **2 turni completi** e la domanda attuale restano intatti; i turni precedenti escono dalla cronologia e vengono sostituiti da un **riassunto aggiornato**, non accumulato: ogni compressione unisce il riassunto precedente e i turni che escono. Il taglio cade sempre all'inizio di una domanda dell'utente, quindi una richiesta di strumento non viene mai separata dal suo risultato.
- **Il riassuntore:** stesso server e modello, client separato senza strumenti, `temperature=0`, `reasoning_effort="none"`, al massimo 768 token. Riceve la trascrizione dei soli turni che escono (risultati degli strumenti troncati a 1000 caratteri, bozze e osservazioni omesse) e scrive sei sezioni: Obiettivo, Informazioni e vincoli, Preferenze, Decisioni aggiornate, Risultati utili, Questioni aperte.
- **Chi lo usa:** l'agente lo riceve come messaggio di sistema temporaneo (mai salvato nella cronologia, mai contato per la soglia); Router e Revisore lo vedono in una sezione del prompt prima dei turni precedenti. Tutti e tre sono avvisati che è contesto e non una richiesta, e che le informazioni più recenti prevalgono. Senza riassunto i prompt sono identici a quelli precedenti.
- **Errori del riassuntore** (server non raggiungibile, risposta vuota o troncata): nessuna compressione, il riassunto precedente resta, la domanda prosegue normalmente (*fail-open*) e nei log compare un `WARNING`. Alla domanda successiva si riprova.
- **Turno atomico:** se la domanda fallisce (limite di passaggi, server non raggiungibile durante il Router o l'agente) la sessione torna esattamente com'era, riassunto compreso; una compressione fatta in quel turno si ripete alla domanda successiva.
- La memoria vale solo per la sessione: all'uscita cronologia e riassunto si perdono.

Nei log su stderr (logger `assistente.riassunto`; esempi del formato, non esiti misurati):

```
INFO assistente.riassunto: riassunto: soglia non superata (messaggi=5, soglia=20), nessuna chiamata
INFO assistente.riassunto: riassunto: nessun turno eliminabile (messaggi=9, soglia=6, turni completi=2), nessuna chiamata
INFO assistente.riassunto: riassunto: compressi 1 turni, messaggi 7 → 5, durata=12.3s
WARNING assistente.riassunto: riassunto: errore APIConnectionError, nessuna compressione durata=2.1s
WARNING assistente.riassunto: riassunto: output non valido (troncato (finish_reason=length)), nessuna compressione durata=30.4s
```

Nei log non compaiono mai testi dell'utente, degli strumenti, del riassunto o del modello, né il testo delle eccezioni.

## Limite di passaggi

Il limite di LangGraph (`recursion_limit`) per ogni domanda è:

```
1 (Riassunto) + 1 (Router) + (MAX_REVISIONI + 1) × (MAX_PASSAGGI + 1 (Revisore))
```

Il Riassunto usa un passaggio a ogni domanda, anche quando non comprime. Con i valori predefiniti (6 e 1) il limite è 16; con `MAX_REVISIONI=0` è 9. `MAX_PASSAGGI` è quindi il **budget nominale di ogni tentativo** dell'agente, non un limite rigido per tentativo: il limite è unico per tutta la domanda, e un tentativo può usare anche il margine non speso dagli altri.

Valori misurati con modelli simulati (LangGraph 1.2.19), fissati da `test_caratterizza_il_limite_di_passaggi` e dai test del limite in `tests/test_revisore.py`:

- **Ciclo infinito di strumenti** (il modello chiede sempre lo strumento): con i predefiniti il modello è chiamato 7 volte e lo strumento eseguito 7 volte prima dell'interruzione (nello Step 1 erano 3 e 3; invariati con il Riassunto, perché il suo passaggio è compensato dalla formula); con `MAX_PASSAGGI=2` 3 e 3; con `MAX_REVISIONI=0` 4 e 3 (`MAX_PASSAGGI=6`) oppure 2 e 1 (`MAX_PASSAGGI=2`).
- **Turni riusciti:** con il limite 16 un turno può usare al massimo 15 passaggi; un turno con giudizio finale ne usa sempre un numero pari, quindi al massimo 14. Per esempio 3 giri di strumenti, una correzione con 1 giro e i due giudizi (14) si completano; con 2 giri nella correzione (16) il turno si interrompe, anche se il Revisore era già stato chiamato due volte.
- **Valori piccoli:**

  | `MAX_PASSAGGI` | `MAX_REVISIONI` | risposta senza strumenti | un giro di strumento | una correzione senza strumenti |
  |---|---|---|---|---|
  | 1 | 0 | interrotta | interrotta | — |
  | 1 | 1 | completata | interrotta | interrotta |
  | 2 | 0 | completata | interrotta | — |
  | 2 | 1 | completata | completata | completata |
  | 3 | 0 | completata | interrotta | — |
  | 3 | 1 | completata | completata | completata |

  La tabella è invariata con il Riassunto. Con `MAX_PASSAGGI=1` nessuna correzione rientra nel limite. Il rifiuto del Router usa 3 passaggi (Riassunto, Router, rifiuto) e si completa con qualunque valore.

Quando il limite è raggiunto il turno viene scartato: la cronologia torna a com'era prima della domanda, compare un messaggio («La richiesta non è stata completata: raggiunto il limite di N passaggi…», dove N è `MAX_PASSAGGI`) e la chat continua. È un caso diverso dal limite di revisioni, che invece restituisce l'ultima risposta.

## Struttura

```
src/assistente/   config, modello (LM Studio), grafo (LangGraph)
                  agente (turno e costruzione del grafo), servizio_agente/ (API FastAPI dell'agente)
                  terminale (CLI client dell'API)
                  comandi (comandi /prompts e /prompt: scomposizione, controllo, conversione)
                  riassunto (Riassunto della cronologia: turni, trascrizione, prompt, nodo)
                  router (Router di ambito: contesto, prompt, rifiuto)
                  preferenze (preferenze dell'utente dalla resource MCP: validazione, prompt)
                  revisore (Revisore della risposta: giudizio, osservazione, contesto dell'agente)
                  strumenti (orologio e composizione), unita, calcolatrice
                  mcp_client, verifica_mcp (client MCP e controllo di salute)
                  server_mcp, note, meteo (server MCP: strumenti, resource e prompt)
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
- **Cronologia:** con le correzioni la cronologia della sessione cresce (al massimo una risposta scartata e un'osservazione per domanda con il predefinito), finché il Riassunto non toglie i turni vecchi.
- **Riassunto: soglia in messaggi.** La soglia conta messaggi, non token, e non garantisce di restare nella finestra di contesto del modello (8192 token per `google/gemma-4-e2b`).
- **Riassunto a ogni turno (caso A1):** se gli ultimi 2 turni da soli superano la soglia (turni lunghi con molti strumenti, o soglia molto bassa), il riassunto può essere aggiornato a ogni domanda, con la latenza relativa.
- **Messaggi eliminati non recuperabili:** dei turni tolti resta solo ciò che il riassunto ha catturato.
- **Fail-open ripetuto:** se il riassuntore fallisce più volte di seguito la cronologia continua a crescere e può superare la finestra di contesto; non c'è altro meccanismo di riserva.
- **Elenchi lunghi:** i risultati degli strumenti oltre 1000 caratteri arrivano al riassuntore troncati; anche un risultato intero può perdere singoli elementi (negli esperimenti una nota in fondo a un elenco di 25 non è stata conservata nemmeno senza troncamento). La fonte autorevole resta lo strumento, che si può interrogare di nuovo.
- **Risultati storici superati:** il riassunto può conservare risultati legati a decisioni poi cambiate (per esempio un conteggio di giorni fino a una scadenza spostata) senza segnarli come superati.
- **Qualità del riassunto:** con un modello da 2B lo stile non è sempre pulito (sintassi della trascrizione ricopiata, «Nessuno»/«nessuna» alternati); non c'è verifica dei fatti, e un errore entrato nel riassunto si propaga alle compressioni successive. Il prompt è stato validato su 5 scenari, e a `temperature=0` l'output non è sempre deterministico.
- **Latenza del Riassunto:** nelle domande in cui scatta la compressione il riassuntore aggiunge una chiamata (6–30 s negli spike, con picchi fino a 68 s; nelle prove reali da 6,8 a 33,2 s), oltre a Router e Revisore. Se quella domanda fallisce, la chiamata si ripete alla domanda successiva.
- **Prompt più lunghi:** con un riassunto presente i prompt di Router, agente e Revisore crescono.
- **«Come mi chiamo?» dopo la compressione:** se il nome è rimasto solo nel riassunto, il Router classifica la domanda fuori ambito («richiesta informazione personale») e risponde con il rifiuto. Domande più ricche come «Ricordami come mi chiamo e qual è il mio obiettivo» passano e l'agente risponde dal riassunto. Tre formulazioni della sezione del riassunto non hanno cambiato il comportamento (vedi `prove_reali/PROVE.md`).
- **«Ho salvato»:** richiamando informazioni dal riassunto l'agente può scrivere «Ho salvato le seguenti informazioni»: è impreciso, nulla viene salvato oltre la sessione.
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
- **Preferenze e testi fissi:** il rifiuto del Router, gli avvisi e le conferme restano in italiano qualunque sia la `lingua` preferita.
- **Preferenze e modello:** il programma garantisce solo il fuso dell'orologio senza argomenti; rispettare lingua e stile dipende dal modello locale. `lingua` è testo libero e non viene verificata.
- **Preferenze per sessione:** vengono lette solo all'avvio; una modifica del file vale dalla sessione successiva. Con il server spento la lettura fa un tentativo in più (al massimo `MCP_TIMEOUT` secondi).
- **Prompt e ambito:** il prompt passa dal Router come ogni domanda. `spiega` su un argomento fuori da `AMBITO_AGENTE` riceve il rifiuto: per questo l'ambito di `.env.example` comprende le «spiegazioni introduttive di concetti informatici». Chi ha un `.env` precedente deve aggiungere la stessa frase.
- **Prompt e modello:** il livello di `spiega` (linguaggio, esempio) viene rispettato, ma il contenuto dipende da ciò che sa il modello locale: nelle prove `google/gemma-4-e2b` ha descritto MCP in modo inesatto.
- **Riassunto della conversazione dopo la compressione:** `riassumi_conversazione` riporta bene i turni ancora nella cronologia, ma nelle prove ha omesso il turno già compresso dal Riassunto (presente solo nel riassunto delle istruzioni di sistema), anche con un testo che chiede esplicitamente di includerlo.
- **Comandi:** ogni riga che comincia con `/` è un comando, quindi una domanda che comincia con `/` non arriva al modello. Solo le virgolette doppie delimitano un valore, e un valore non può contenere virgolette doppie. I messaggi dei comandi sono in italiano qualunque sia la lingua preferita. Ogni `/prompt` fa due richieste al server.
- **Docker e cartella `data/`:** `server-mcp` vede tutta la cartella `data/` dell'host in sola lettura, compreso il `note.db` locale, che non usa (le note in Docker stanno nel volume `dati-note`).

## Diagnosi

- **Prompt rifiutato dal Router:** il testo compilato è fuori da `AMBITO_AGENTE`; controlla l'ambito nel tuo `.env`. Se un valore non ammesso dal server dà «Prompt non eseguito», nei log del server compare anche il traceback di FastMCP: è atteso.
- **Preferenze ignorate:** cerca nei log dell'agente la riga `preferenze della sessione`: `(predefinito)` indica il campo non letto, e il `WARNING` precedente dice perché. Se il file manca, nei log del server compare anche il traceback di FastMCP con `ResourceError`: è atteso.
- **Variabile mancante:** il programma lo dice e termina con codice 1.
- **«Non riesco a ottenere una risposta dal server»:** LM Studio è spento o `LM_STUDIO_BASE_URL` è sbagliato (l'API risponde 503). La chat resta aperta: riavviato il server, si può riprovare.
- **Agente:** `Invoke-RestMethod http://localhost:8002/stato` (in PowerShell 5.1 un 503 diventa un'eccezione: il corpo con il motivo è nel messaggio) dice quale componente non è raggiungibile.
- **Identificativo del modello:** LM Studio con un solo modello caricato ha risposto anche a un identificativo inesistente, quindi un errore di battitura può non dare errori. Verifica sempre con `prove_reali\verifica_modelli.py`.
