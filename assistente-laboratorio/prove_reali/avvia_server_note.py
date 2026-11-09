"""Avvia il server MCP delle note su 127.0.0.1:8001 (provvisorio fino a T4).

Da assistente-laboratorio/, in una finestra PowerShell separata:
    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe prove_reali\avvia_server_note.py
"""

import asyncio
import logging
import os

from assistente.note import ArchivioNote
from assistente.server_mcp import crea_server

logging.basicConfig(level=logging.INFO)
percorso = os.environ.get("NOTE_DB_PATH", "note-prova.db")
server = crea_server(ArchivioNote(percorso))
asyncio.run(
    server.run_http_async(host="127.0.0.1", port=8001, path="/mcp", show_banner=False)
)
