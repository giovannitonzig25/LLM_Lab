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
Get-Content .env | Where-Object { $_ -match '^\s*[^#\s]' } | ForEach-Object { $n, $v = $_ -split '=', 2; Set-Item -Path "env:$n" -Value $v }
.\.venv\Scripts\python.exe prove_reali\verifica_modelli.py
```

Lo script elenca gli identificativi restituiti da `GET /v1/models` ed esce con errore se `LM_STUDIO_MODEL` non è tra questi. Variabili:

| Variabile | Significato |
|---|---|
| `LM_STUDIO_BASE_URL` | indirizzo del server, per esempio `http://localhost:1234/v1` (obbligatoria) |
| `LM_STUDIO_MODEL` | identificativo del modello (obbligatoria) |
| `MAX_PASSAGGI` | limite di passaggi del grafo, predefinito 6 |
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

LM Studio resta sull'host; nel container l'indirizzo è `http://host.docker.internal:1234/v1` (Compose lo imposta al posto di quello di `.env`; per un'altra porta o indirizzo definisci `LM_STUDIO_DOCKER_URL` in `.env`). `LM_STUDIO_MODEL` e `MAX_PASSAGGI` vengono da `.env`.

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

## Strumento orologio e log

Il modello può chiedere lo strumento `orologio`, con un fuso orario IANA (`timezone`, predefinito `Europe/Rome`). Il grafo lo esegue davvero e restituisce il risultato al modello. Ogni richiesta e ogni esito compaiono nei log su stderr:

```
INFO assistente.strumenti: strumento richiesto: nome=orologio argomenti={'timezone': 'Asia/Tokyo'}
INFO assistente.strumenti: strumento eseguito: nome=orologio risultato=2026-11-02 01:48:55 (Asia/Tokyo, UTC+09:00)
```

Un fuso non valido o uno strumento inesistente non fanno cadere il programma: il modello riceve un risultato che inizia con `Errore:`.

## Limite di passaggi

`MAX_PASSAGGI` è il limite di passaggi del grafo (`recursion_limit` di LangGraph), non di richieste di strumento. Misurato con un modello simulato che chiede sempre lo strumento (LangGraph 1.2.19): con 6 il modello è chiamato 3 volte e lo strumento eseguito 3 volte prima dell'interruzione; con 2, una volta ciascuno. Il test `test_caratterizza_il_limite_di_passaggi` fissa questi valori e segnala se cambiano.

Quando il limite è raggiunto il turno viene scartato: la cronologia torna a com'era prima della domanda, compare un messaggio («La richiesta non è stata completata…») e la chat continua.

## Struttura

```
src/assistente/   config, modello (LM Studio), strumenti (orologio), grafo (LangGraph), terminale
tests/            test automatici, senza rete né modello
prove_reali/      prove con LM Studio e Docker, da eseguire a mano
docs/superpowers/ specifica e piano
```

## Limitazioni note

- **Immagine Docker:** il codice è copiato nell'immagine al momento della build. Dopo ogni modifica a `src/` esegui `docker compose build`, altrimenti `docker compose run` usa l'immagine vecchia.
- **`MAX_PASSAGGI`:** con 1 falliscono anche le risposte senza strumento; con 2 o 3 non basta un giro completo dello strumento; ne servono almeno 4.
- **Fuso orario:** un valore con spazi ai lati (`" Asia/Tokyo"`) viene rifiutato con un errore, e per argomenti del tipo sbagliato il messaggio restituito al modello è lungo.
- **Errori imprevisti:** un'eccezione non legata al server del modello (per esempio una richiesta di strumento senza identificativo) interrompe la sessione.
- **Prompt:** dopo Ctrl+C o Ctrl+D il cursore può restare sulla riga di «Tu: ».

## Diagnosi

- **Variabile mancante:** il programma lo dice e termina con codice 1.
- **«Non riesco a ottenere una risposta dal server»:** LM Studio è spento o `LM_STUDIO_BASE_URL` è sbagliato. La chat resta aperta: riavviato il server, si può riprovare.
- **Identificativo del modello:** LM Studio con un solo modello caricato ha risposto anche a un identificativo inesistente, quindi un errore di battitura può non dare errori. Verifica sempre con `prove_reali\verifica_modelli.py`.
