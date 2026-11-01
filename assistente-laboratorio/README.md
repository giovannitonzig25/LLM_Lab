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

## Diagnosi

- **Variabile mancante:** il programma lo dice e termina con codice 1.
- **«Non riesco a ottenere una risposta dal server»:** LM Studio è spento o `LM_STUDIO_BASE_URL` è sbagliato. La chat resta aperta: riavviato il server, si può riprovare.
- **Identificativo del modello:** LM Studio con un solo modello caricato ha risposto anche a un identificativo inesistente, quindi un errore di battitura può non dare errori. Verifica sempre con `prove_reali\verifica_modelli.py`.
