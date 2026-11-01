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

## Avvio

Dopo aver caricato le variabili nella stessa finestra di PowerShell:

```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.terminale
```

Uscita: `esci`, Ctrl+C o Ctrl+D.

La cronologia vale per la sessione: dentro la stessa esecuzione il modello ricorda i turni precedenti, al riavvio riparte da zero. Se un turno fallisce (per esempio server spento) la cronologia resta com'era prima della domanda.

## Avvio con Docker Compose

LM Studio resta sull'host; nel container l'indirizzo è `http://host.docker.internal:1234/v1` (Compose lo imposta al posto di quello di `.env`; per un'altra porta o indirizzo definisci `LM_STUDIO_DOCKER_URL` in `.env`). `LM_STUDIO_MODEL` e `MAX_PASSAGGI` vengono da `.env`.

```powershell
docker compose build
docker compose run --rm assistente
```

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
