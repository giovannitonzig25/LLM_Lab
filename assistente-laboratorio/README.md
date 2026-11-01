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

## Avvio

```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.terminale
```

Uscita: `esci`, Ctrl+C o Ctrl+D. In questo stato il grafo risponde sempre con una frase fissa.
