"""Avvio: python -m assistente.servizi_http (SERVIZI_HOST, SERVIZI_PORT)."""
import os

import uvicorn

from .app import crea_app


def main() -> None:
    host = os.environ.get("SERVIZI_HOST", "").strip() or "127.0.0.1"
    porta = int(os.environ.get("SERVIZI_PORT", "").strip() or "8000")
    uvicorn.run(crea_app(), host=host, port=porta)


if __name__ == "__main__":
    main()
