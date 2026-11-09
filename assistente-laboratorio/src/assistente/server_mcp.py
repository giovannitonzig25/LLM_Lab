"""Server MCP (FastMCP, Streamable HTTP) con gli strumenti per le note."""

import logging

from fastmcp import FastMCP

from assistente.note import ArchivioNote

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
        nota = archivio.aggiungi(testo)
        logger.info("nota aggiunta: id %s", nota.id)
        return f"Nota creata: id {nota.id}, data {nota.creata}"

    return server
