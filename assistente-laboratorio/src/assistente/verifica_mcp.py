"""Controllo di salute del server MCP: una vera discovery, non una semplice connessione TCP.

Uso: `python -m assistente.verifica_mcp` (variabili `MCP_URL` e `MCP_TIMEOUT`).
Esce con 0 se la discovery trova almeno uno strumento, altrimenti con 1.
"""

import os
import sys

from assistente.config import MCP_TIMEOUT_PREDEFINITO, MCP_URL_PREDEFINITO
from assistente.mcp_client import ErroreMcp, scopri_strumenti


def verifica(url: str, timeout: float = 5.0) -> int:
    try:
        strumenti = scopri_strumenti(url, timeout)
    except ErroreMcp as errore:
        print(f"Server MCP non sano: {errore}", file=sys.stderr)
        return 1
    if not strumenti:
        print(f"Server MCP su {url}: nessuno strumento scoperto", file=sys.stderr)
        return 1
    nomi = ", ".join(s.name for s in strumenti)
    print(f"Discovery MCP riuscita su {url}: {nomi}")
    return 0


def main() -> int:
    url = os.environ.get("MCP_URL", "").strip() or MCP_URL_PREDEFINITO
    grezzo = os.environ.get("MCP_TIMEOUT", "").strip()
    try:
        timeout = float(grezzo) if grezzo else MCP_TIMEOUT_PREDEFINITO
        if not timeout > 0:
            raise ValueError
    except ValueError:
        print(f"MCP_TIMEOUT deve essere un numero di secondi positivo, ricevuto: {grezzo!r}", file=sys.stderr)
        return 1
    return verifica(url, timeout)


if __name__ == "__main__":
    raise SystemExit(main())
