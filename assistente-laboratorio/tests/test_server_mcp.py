import asyncio
import logging
import sqlite3
from datetime import datetime, timezone

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

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


def chiama(server, nome, argomenti):
    async def vai(url):
        async with Client(url) as client:
            return await client.call_tool(nome, argomenti)

    with avvia_server_mcp(server) as url:
        return asyncio.run(vai(url))


def test_elenca_note_via_mcp(tmp_path):
    percorso, server = crea(tmp_path)
    archivio = ArchivioNote(percorso, adesso=lambda: ISTANTE)
    archivio.aggiungi("consegnare il report venerdì")
    archivio.aggiungi("comprare il caffè")

    tutte = chiama(server, "elenca_note", {}).content[0].text
    filtrate = chiama(server, "elenca_note", {"filtro": "report", "limite": 5}).content[0].text
    nessuna = chiama(server, "elenca_note", {"filtro": "inesistente"}).content[0].text

    assert tutte.index("caffè") < tutte.index("report")  # dalla più recente
    assert "id 2" in tutte and "id 1" in tutte and "2026-11-09 10:00:00" in tutte
    assert "report" in filtrate and "caffè" not in filtrate
    assert "Nessuna nota" in nessuna


@pytest.mark.parametrize(
    "nome, argomenti",
    [
        ("aggiungi_nota", {"testo": "   "}),
        ("aggiungi_nota", {"testo": "x" * 501}),
        ("elenca_note", {"limite": 0}),
        ("elenca_note", {"limite": "abc"}),
    ],
)
def test_errori_via_mcp(tmp_path, nome, argomenti):
    _, server = crea(tmp_path)

    with pytest.raises(ToolError) as errore:
        chiama(server, nome, argomenti)

    assert "Traceback" not in str(errore.value)
    assert str(errore.value).strip()


def test_errore_dell_archivio_via_mcp(tmp_path):
    server = crea_server(ArchivioNote(str(tmp_path)))  # percorso inutilizzabile

    with pytest.raises(ToolError, match="archivio non accessibile"):
        chiama(server, "aggiungi_nota", {"testo": "ciao"})


def test_log_di_ogni_modifica(tmp_path, caplog):
    _, server = crea(tmp_path)

    with caplog.at_level(logging.INFO, logger="assistente.server_mcp"):
        chiama(server, "aggiungi_nota", {"testo": "ciao"})

    assert any("nota aggiunta" in r.getMessage() and "1" in r.getMessage() for r in caplog.records)
