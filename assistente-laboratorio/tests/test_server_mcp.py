import asyncio
import sqlite3
from datetime import datetime, timezone

from fastmcp import Client

from assistente.note import ArchivioNote
from assistente.server_mcp import crea_server
from server_reale import avvia_server_mcp

ISTANTE = datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)


def crea(tmp_path):
    percorso = str(tmp_path / "note.db")
    return percorso, crea_server(ArchivioNote(percorso, adesso=lambda: ISTANTE))


def test_discovery_elenca_aggiungi_nota(tmp_path):
    _, server = crea(tmp_path)

    async def scopri(url):
        async with Client(url) as client:
            return await client.list_tools()

    with avvia_server_mcp(server) as url:
        strumenti = {t.name: t for t in asyncio.run(scopri(url))}

    assert "aggiungi_nota" in strumenti
    strumento = strumenti["aggiungi_nota"]
    assert strumento.description
    assert strumento.input_schema["properties"]["testo"]["type"] == "string"


def test_invocazione_diretta_aggiungi_nota(tmp_path):
    percorso, server = crea(tmp_path)

    async def chiama(url):
        async with Client(url) as client:
            return await client.call_tool("aggiungi_nota", {"testo": "ciao"})

    with avvia_server_mcp(server) as url:
        risultato = asyncio.run(chiama(url))

    testo = risultato.content[0].text
    assert "id 1" in testo and "2026-11-09 10:00:00" in testo
    righe = sqlite3.connect(percorso).execute("SELECT id, testo FROM note").fetchall()
    assert righe == [(1, "ciao")]
