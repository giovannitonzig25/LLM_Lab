# repo-lab-llm

Client Python minimo da terminale per un modello eseguito in locale con LM Studio: legge le domande da tastiera, stampa la risposta in streaming e ricorda la conversazione finché resta aperto. Materiale della Lezione 3 del corso Deep Learning e LLM (ITS Alto Adriatico).

## Contenuto della repository

| File | Funzione |
|---|---|
| `client.py` | Client da terminale: domanda da `input()`, risposta in streaming, cronologia in memoria |
| `requirements.txt` | Dipendenze con versioni fissate |
| `.env.example` | Modello della configurazione locale, senza segreti |
| `CLAUDE.md` | Istruzioni di sviluppo lette da Claude Code |
| `.gitignore` | File esclusi da Git: configurazione locale, ambiente virtuale, pesi, log |

## Prerequisiti

- Windows con PowerShell, Git e VS Code (estensioni Python e Git Graph).
- Python con il launcher `py`.
- LM Studio con il modello `google/gemma-4-e2b`, quantizzazione a 4 bit (`Q4_K_M`).
- Claude Code CLI: guida ufficiale <https://code.claude.com/docs/en/setup>. In PowerShell: `irm https://claude.ai/install.ps1 | iex`, poi riaprire il terminale e verificare con `claude --version`.

## Preparazione

Dalla radice della repository:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r lezione-3\requirements.txt
```

In VS Code selezionare l'interprete `.venv` con **Python: Select Interpreter**.

## Configurazione

1. In LM Studio scaricare e caricare `google/gemma-4-e2b` (4 bit), poi avviare il server dalla sezione Developer.
2. Leggere l'identificativo del modello esposto dal server:

   ```powershell
   $base = "http://localhost:1234/v1"
   (Invoke-RestMethod "$base/models").data | Select-Object id
   ```

3. Creare la configurazione locale, solo se `.env` non esiste già. In `.env.example` i valori sono vuoti: in `.env` vanno compilati `LM_BASE_URL` (per esempio `http://127.0.0.1:1234/v1`) e `LM_MODEL` con l'identificativo letto al punto 2:

   ```powershell
   Copy-Item lezione-3\.env.example lezione-3\.env
   notepad lezione-3\.env
   ```

`.env` resta sul proprio computer ed è escluso da Git.

## Avvio

Dalla radice della repository:

```powershell
.\.venv\Scripts\python.exe lezione-3\client.py
```

Il client mostra il prompt `Tu>`: scrivere una domanda e premere Invio. Si esce con `esci` o con Ctrl+C; le righe vuote vengono ignorate.

- La risposta compare a frammenti mentre il modello la genera (streaming).
- Il client ricorda la conversazione finché resta aperto: la cronologia vive solo in memoria e si perde alla chiusura. Ogni turno allunga la richiesta (più token e più tempo, fino al limite di contesto del modello).
- Se una richiesta fallisce, la domanda non entra nella cronologia.

## Diagnosi rapida

| Messaggio | Primo controllo |
|---|---|
| `Connessione fallita` | LM Studio acceso, server avviato, URL e porta in `.env` |
| `Errore HTTP` seguito da codice e testo | Il server ha risposto con un errore: leggere il testo stampato; LM Studio acceso, modello caricato |
| `Errore dal server` con messaggio `Unexpected endpoint` | URL in `.env`: deve terminare con `/v1` |
| `Attesa scaduta` | Carico del computer, tempi del modello |
| Risposta vuota | `"reasoning_effort": "none"` nel payload: senza, il modello ragiona e consuma i token prima di rispondere |
| `KeyError: 'LM_BASE_URL'` o `'LM_MODEL'` | `.env` mancante o variabile non definita |
| `Configurazione incompleta` | `LM_BASE_URL` o `LM_MODEL` vuoti in `.env`: compilarli come al punto 3 della configurazione |

Un identificativo sbagliato in `LM_MODEL` non produce necessariamente un errore: nella prova con LM Studio il server ha risposto comunque con il modello caricato. Per questo l'identificativo va letto dal server (punto 2 della configurazione) e non dato per scontato.

Una risposta arrivata non è necessariamente corretta: va letta e valutata.
