"""Server MCP (FastMCP, Streamable HTTP) con gli strumenti per le note.

Avvio: `python -m assistente.server_mcp` (variabili `NOTE_DB_PATH`, `MCP_HOST`, `MCP_PORT`).
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from assistente.meteo import ErroreMeteo, leggi_meteo
from assistente.note import ArchivioNote, ErroreNote

logger = logging.getLogger("assistente.server_mcp")

METEO_TIMEOUT = 10.0  # secondi, per ciascuna delle due richieste a Open-Meteo


def crea_server(archivio: ArchivioNote, client_http: httpx.Client | None = None) -> FastMCP:
    """Server MCP con note e meteo. `client_http` serve ai test per simulare Open-Meteo."""
    server = FastMCP("note")
    client_meteo = client_http or httpx.Client(timeout=METEO_TIMEOUT)

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

    @server.tool(
        description=(
            "Elimina la nota con l'id indicato. L'applicazione chiede conferma all'utente "
            'prima di cancellare. Esempio: "elimina la nota 3"'
        ),
        annotations={"destructiveHint": True},
    )
    def elimina_nota(id: int) -> str:
        """Cancella la nota senza altre verifiche.

        La conferma dell'utente non è qui: la chiede il client (il nostro agente, in base a
        `destructiveHint`). Altri client MCP possono cancellare senza conferma.
        """
        try:
            archivio.elimina(id)
        except ErroreNote as errore:
            raise ToolError(str(errore)) from errore
        logger.info("nota eliminata: id %s", id)
        return f"Nota {id} eliminata"

    @server.tool(
        description=(
            "Restituisce il meteo attuale (temperatura in °C e condizioni) di una città, "
            "dato il suo nome. Non serve per sapere che ora è. "
            'Esempio: "che tempo fa a Bologna?" oppure "piove a Forlì?"'
        )
    )
    def meteo(citta: str) -> str:
        try:
            return leggi_meteo(citta, client_meteo)
        except ErroreMeteo as errore:
            logger.warning("meteo non disponibile per %r: %s", citta, errore)
            raise ToolError(str(errore)) from errore

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
