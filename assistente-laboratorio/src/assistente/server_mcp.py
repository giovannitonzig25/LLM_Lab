"""Server MCP (FastMCP, Streamable HTTP) con gli strumenti per le note.

Avvio: `python -m assistente.server_mcp` (variabili `NOTE_DB_PATH`, `MCP_HOST`, `MCP_PORT`).
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from assistente.note import ArchivioNote, ErroreNote

logger = logging.getLogger("assistente.server_mcp")


def crea_server(archivio: ArchivioNote) -> FastMCP:
    server = FastMCP("note")

    @server.tool(
        description=(
            "Salva una nota. "
            'Esempio: "ricordami di consegnare il report venerdì"'
        )
    )
    def aggiungi_nota(testo: str) -> str:
        try:
            nota = archivio.aggiungi(testo)
        except ErroreNote as errore:
            raise ToolError(str(errore)) from errore
        logger.info("nota aggiunta: id %s", nota.id)
        return f"Nota creata: id {nota.id}, data {nota.creata}"

    @server.tool(
        description=(
            "Elenca le note salvate, dalla più recente. `filtro` cerca una parola nel "
            "testo (facoltativo); `limite` è il numero massimo di note (1-100, predefinito 20). "
            'Esempio: "elenca le mie note" oppure "cerca le note sul report"'
        )
    )
    def elenca_note(filtro: str | None = None, limite: int = 20) -> str:
        try:
            note = archivio.elenca(filtro, limite)
        except ErroreNote as errore:
            raise ToolError(str(errore)) from errore
        if not note:
            return "Nessuna nota trovata."
        return "\n".join(f"id {n.id} | {n.creata} | {n.testo}" for n in note)

    return server


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    percorso = os.environ.get("NOTE_DB_PATH", "data/note.db")
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    try:
        porta = int(os.environ.get("MCP_PORT", "8001"))
    except ValueError:
        print("MCP_PORT deve essere un numero intero", file=sys.stderr)
        return 1
    Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    logger.info("server MCP delle note su http://%s:%s/mcp (archivio %s)", host, porta, percorso)
    server = crea_server(ArchivioNote(percorso))
    asyncio.run(server.run_http_async(host=host, port=porta, path="/mcp", show_banner=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
