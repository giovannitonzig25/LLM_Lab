"""Prova reale (non è un test automatico): elenca i modelli di LM Studio e controlla quello configurato.

Richiede LM Studio attivo e le variabili LM_STUDIO_BASE_URL e LM_STUDIO_MODEL.
"""
import json
import os
import sys
import urllib.request


def main() -> int:
    base_url = os.environ.get("LM_STUDIO_BASE_URL", "").strip().rstrip("/")
    modello = os.environ.get("LM_STUDIO_MODEL", "").strip()
    if not base_url or not modello:
        print("Servono LM_STUDIO_BASE_URL e LM_STUDIO_MODEL.", file=sys.stderr)
        return 1
    try:
        with urllib.request.urlopen(f"{base_url}/models", timeout=10) as risposta:
            identificativi = [m["id"] for m in json.load(risposta)["data"]]
    except OSError as errore:
        print(f"Server non raggiungibile su {base_url}: {errore}", file=sys.stderr)
        return 1
    print("Modelli disponibili:", *identificativi, sep="\n  ")
    if modello not in identificativi:
        print(f"Il modello configurato non è presente: {modello}", file=sys.stderr)
        return 1
    print(f"OK: {modello}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
