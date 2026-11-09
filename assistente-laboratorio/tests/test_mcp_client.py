import asyncio
import logging
import socket
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from fastmcp import Client
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool

from assistente.grafo import costruisci_grafo
from assistente.mcp_client import ErroreMcp, StrumentoMcp, scopri_strumenti
from assistente.note import ArchivioNote
from assistente.server_mcp import crea_server
from finti import ModelloSimulato
from server_reale import avvia_server_mcp

ISTANTE = datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def server(tmp_path):
    percorso = str(tmp_path / "note.db")
    with avvia_server_mcp(crea_server(ArchivioNote(percorso, adesso=lambda: ISTANTE))) as url:
        yield url, percorso


def porta_chiusa() -> str:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    return f"http://127.0.0.1:{porta}/mcp"


@contextmanager
def porta_muta():
    """Socket in ascolto che accetta connessioni ma non risponde mai."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(5)
    try:
        yield f"http://127.0.0.1:{s.getsockname()[1]}/mcp"
    finally:
        s.close()


def richiesta(nome, args, id_):
    return {"name": nome, "args": args, "id": id_, "type": "tool_call"}


def test_discovery_riporta_nome_descrizione_e_schema_del_server(server):
    url, _ = server

    async def diretto():
        async with Client(url) as client:
            return await client.list_tools()

    attesi = {t.name: t for t in asyncio.run(diretto())}
    strumenti = scopri_strumenti(url)

    assert {s.name for s in strumenti} == set(attesi)
    for s in strumenti:
        assert isinstance(s, BaseTool)
        assert s.description == attesi[s.name].description
    aggiungi = next(s for s in strumenti if s.name == "aggiungi_nota")
    assert "testo" in aggiungi.args_schema["properties"]


def test_chiamate_ripetute_stesso_processo(server):
    url, _ = server
    aggiungi = next(s for s in scopri_strumenti(url) if s.name == "aggiungi_nota")

    risultati = [aggiungi.invoke({"testo": f"nota {i}"}) for i in range(3)]

    for atteso, risultato in zip((1, 2, 3), risultati):
        assert f"id {atteso}" in risultato
        assert not risultato.startswith("Errore:")


def test_due_turni_del_grafo_con_finto_modello(server):
    url, _ = server
    modello = ModelloSimulato([
        AIMessage("", tool_calls=[richiesta("aggiungi_nota", {"testo": "uno"}, "call_1")]),
        AIMessage("Fatto uno"),
        AIMessage("", tool_calls=[richiesta("aggiungi_nota", {"testo": "due"}, "call_2")]),
        AIMessage("Fatto due"),
    ])
    grafo = costruisci_grafo(modello, scopri_strumenti(url))

    primo = grafo.invoke({"messages": [HumanMessage("annota uno")]})
    secondo = grafo.invoke({"messages": primo["messages"] + [HumanMessage("annota due")]})

    risposte1 = [m for m in primo["messages"] if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in risposte1] == ["call_1"]
    assert "id 1" in risposte1[0].content
    assert primo["messages"][-1].content == "Fatto uno"
    risposte2 = [m for m in secondo["messages"] if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in risposte2] == ["call_1", "call_2"]
    assert "id 2" in risposte2[1].content
    assert secondo["messages"][-1].content == "Fatto due"
    assert len(modello.chiamate[2]) > len(modello.chiamate[0])  # cronologia del primo turno


def test_due_richieste_nello_stesso_messaggio(server):
    url, _ = server
    modello = ModelloSimulato([
        AIMessage("", tool_calls=[
            richiesta("aggiungi_nota", {"testo": "a"}, "a"),
            richiesta("aggiungi_nota", {"testo": "b"}, "b"),
        ]),
        AIMessage("Fatto"),
    ])
    grafo = costruisci_grafo(modello, scopri_strumenti(url))

    esito = grafo.invoke({"messages": [HumanMessage("due note")]})

    risposte = [m for m in esito["messages"] if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in risposte] == ["a", "b"]
    assert "id 1" in risposte[0].content and "id 2" in risposte[1].content


def test_server_non_raggiungibile_alla_discovery():
    with pytest.raises(ErroreMcp):
        scopri_strumenti(porta_chiusa(), timeout=2)


def test_server_caduto_a_meta_sessione(tmp_path):
    percorso = str(tmp_path / "note.db")
    with avvia_server_mcp(crea_server(ArchivioNote(percorso))) as url:
        aggiungi = next(s for s in scopri_strumenti(url) if s.name == "aggiungi_nota")

    risultato = aggiungi.invoke({"testo": "ciao"})

    assert risultato.startswith("Errore:")
    assert "non raggiungibile" in risultato


def test_timeout():
    with porta_muta() as url:
        strumento = StrumentoMcp(
            name="x", description="d", args_schema={"type": "object", "properties": {}},
            url=url, timeout=0.5,
        )
        inizio = time.monotonic()
        risultato = strumento.invoke({})
        durata = time.monotonic() - inizio

    assert risultato.startswith("Errore: timeout")
    assert durata < 3


@pytest.mark.parametrize("argomenti", [{"testo": 5}, {}])
def test_errore_dello_strumento_non_e_un_successo(server, argomenti):
    url, percorso = server
    aggiungi = next(s for s in scopri_strumenti(url) if s.name == "aggiungi_nota")

    risultato = aggiungi.invoke(argomenti)

    assert risultato.startswith("Errore:")
    assert "Traceback" not in risultato
    try:
        righe = sqlite3.connect(percorso).execute("SELECT * FROM note").fetchall()
    except sqlite3.OperationalError:
        righe = []
    assert righe == []


def test_log_discovery_e_invocazione(server, caplog):
    url, _ = server
    with caplog.at_level(logging.INFO, logger="assistente.mcp"):
        aggiungi = next(s for s in scopri_strumenti(url) if s.name == "aggiungi_nota")
        aggiungi.invoke({"testo": "ciao"})

    messaggi = [r.getMessage() for r in caplog.records if r.name == "assistente.mcp"]
    assert any("scoperti" in m and "aggiungi_nota" in m for m in messaggi)
    assert any("invocazione" in m and "aggiungi_nota" in m for m in messaggi)


def test_invocazione_con_ciclo_asyncio_gia_attivo(server):
    url, _ = server
    aggiungi = next(s for s in scopri_strumenti(url) if s.name == "aggiungi_nota")

    async def dentro_un_ciclo():
        return aggiungi.invoke({"testo": "da un ciclo attivo"})

    assert "id 1" in asyncio.run(dentro_un_ciclo())
