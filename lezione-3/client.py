"""Client minimo per il server locale di LM Studio.

Scheletro da completare con Claude Code (slide 19-22):
configurazione, messaggi, payload e chiamata HTTP.
Import e gestione degli errori sono gia' presenti: conservarli.
"""

import json
import os

import requests
from dotenv import load_dotenv

# --- Configurazione -------------------------------------------------------
load_dotenv()
base_url = os.environ["LM_BASE_URL"]
model = os.environ["LM_MODEL"]
if not base_url.strip() or not model.strip():
    raise SystemExit("Configurazione incompleta: compilare LM_BASE_URL e LM_MODEL in .env.")

# --- Messaggi -------------------------------------------------------------
SYSTEM = "Sei un assistente per studenti. Rispondi in italiano, in modo chiaro e conciso."
messages = [{"role": "system", "content": SYSTEM}]

# --- Ciclo di domande -----------------------------------------------------
while True:
    try:
        domanda = input("Tu> ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        break
    if domanda.lower() == "esci":
        break
    if not domanda:
        continue
    messages.append({"role": "user", "content": domanda})

    # --- Payload ----------------------------------------------------------
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 300,
        "reasoning_effort": "none",
        "stream": True,
    }

    # --- Chiamata ---------------------------------------------------------
    testo = ""
    completata = False
    try:
        with requests.post(f"{base_url}/chat/completions", json=payload, stream=True, timeout=60) as response:
            response.raise_for_status()
            for riga in response.iter_lines():
                riga = riga.decode("utf-8")
                if not riga.startswith("data: "):
                    # Un errore del server puo' arrivare come JSON senza prefisso "data: ".
                    try:
                        errore = json.loads(riga).get("error")
                    except ValueError:
                        errore = None
                    if errore:
                        print("Errore dal server:", errore)
                    continue
                dati = riga[len("data: "):]
                if dati == "[DONE]":
                    completata = True
                    break
                delta = json.loads(dati)["choices"][0]["delta"]
                frammento = delta.get("content") or ""
                print(frammento, end="", flush=True)
                testo += frammento
        print()
    except requests.exceptions.Timeout:
        print("Attesa scaduta: controllare server, carico e tempi.")
    except requests.exceptions.ConnectionError:
        print("Connessione fallita: controllare server, URL e porta.")
    except requests.exceptions.HTTPError:
        print("Errore HTTP:", response.status_code, response.text)

    # --- Cronologia -------------------------------------------------------
    if completata and testo:
        messages.append({"role": "assistant", "content": testo})
    else:
        messages.pop()  # la domanda non ha avuto risposta
