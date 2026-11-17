"""Avvio: python -m assistente.servizio_backend (DATABASE_URL obbligatoria; AGENTE_URL, BACKEND_HOST, BACKEND_PORT)."""
import logging
import os
import sys

import httpx
import uvicorn

from assistente.archivio import ArchivioPostgres, ErroreDatabase

from .app import crea_app

# Come la CLI: connessione entro 10 s, nessun limite sulla risposta (un turno può durare minuti).
TIMEOUT_AGENTE = httpx.Timeout(10.0, read=None)


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL mancante: impostala in .env (vedi .env.example).", file=sys.stderr)
        return 1
    archivio = ArchivioPostgres(database_url)
    try:
        archivio.prepara()
    except ErroreDatabase as errore:
        print(f"Database non raggiungibile: {errore}", file=sys.stderr)
        return 1
    agente_url = os.environ.get("AGENTE_URL", "").strip() or "http://localhost:8002"
    host = os.environ.get("BACKEND_HOST", "").strip() or "127.0.0.1"
    porta = int(os.environ.get("BACKEND_PORT", "").strip() or "8003")
    with httpx.Client(base_url=agente_url, timeout=TIMEOUT_AGENTE) as agente:
        uvicorn.run(crea_app(archivio, agente), host=host, port=porta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
