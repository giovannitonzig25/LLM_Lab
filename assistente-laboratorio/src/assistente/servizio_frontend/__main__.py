"""Avvio: python -m assistente.servizio_frontend (BACKEND_URL, FRONTEND_HOST, FRONTEND_PORT)."""
import logging
import os
import sys

import httpx
import uvicorn

from .app import crea_app

# Come il back-end verso l'agente: connessione entro 10 s, nessun limite sulla risposta (un turno può durare minuti).
TIMEOUT_BACKEND = httpx.Timeout(10.0, read=None)


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    backend_url = os.environ.get("BACKEND_URL", "").strip() or "http://127.0.0.1:8003"
    host = os.environ.get("FRONTEND_HOST", "").strip() or "127.0.0.1"
    porta = int(os.environ.get("FRONTEND_PORT", "").strip() or "8004")
    with httpx.Client(base_url=backend_url, timeout=TIMEOUT_BACKEND) as backend:
        uvicorn.run(crea_app(backend), host=host, port=porta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
