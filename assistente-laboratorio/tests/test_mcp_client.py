import asyncio
import logging
import sqlite3
import time
from datetime import datetime, timezone

import pytest
from fastmcp import Client
from fastmcp.utilities.types import Image
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool

from assistente.grafo import costruisci_grafo
from assistente.mcp_client import ErroreMcp, StrumentoMcp, scopri_strumenti
from assistente.note import ArchivioNote
from assistente.server_mcp import crea_server
from finti import ModelloSimulato
from server_reale import avvia_server_mcp, porta_chiusa, porta_muta

ISTANTE = datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def server(tmp_path):
    percorso = str(tmp_path / "note.db")
    with avvia_server_mcp(crea_server(ArchivioNote(percorso, adesso=lambda: ISTANTE))) as url:
        yield url, percorso


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


# --- T5: conferma dell'utente per gli strumenti con destructiveHint ---
from fastmcp import FastMCP

MSG_NON_CONFERMATA = "Errore: cancellazione non confermata dall'utente"


def nota_esiste(percorso, id_=1):
    riga = sqlite3.connect(percorso).execute("SELECT 1 FROM note WHERE id = ?", (id_,)).fetchone()
    return riga is not None


def strumento(url, nome, chiedi_conferma):
    return next(s for s in scopri_strumenti(url, chiedi_conferma=chiedi_conferma) if s.name == nome)


class Conferma:
    """Funzione di conferma finta che registra i messaggi ricevuti."""

    def __init__(self, esito=True, solleva=None):
        self.esito, self.solleva, self.messaggi = esito, solleva, []

    def __call__(self, messaggio):
        self.messaggi.append(messaggio)
        if self.solleva:
            raise self.solleva
        return self.esito


@pytest.fixture
def server_con_nota(server):
    url, percorso = server
    ArchivioNote(percorso, adesso=lambda: ISTANTE).aggiungi("da cancellare")
    return url, percorso


def test_modello_chiede_subito_la_cancellazione_con_conferma_true(server_con_nota):
    url, percorso = server_con_nota
    conferma = Conferma(esito=False)
    modello = ModelloSimulato([
        AIMessage("", tool_calls=[richiesta("elimina_nota", {"id": 1, "conferma": True}, "call_x")]),
        AIMessage("Non cancellata"),
    ])
    grafo = costruisci_grafo(modello, scopri_strumenti(url, chiedi_conferma=conferma))

    esito = grafo.invoke({"messages": [HumanMessage("cancella la nota 1")]})

    assert nota_esiste(percorso)
    risposta = next(m for m in esito["messages"] if isinstance(m, ToolMessage))
    assert risposta.tool_call_id == "call_x"
    assert risposta.content == MSG_NON_CONFERMATA
    assert len(conferma.messaggi) == 1


def test_senza_funzione_di_conferma_non_si_cancella(server_con_nota):
    url, percorso = server_con_nota

    risultato = strumento(url, "elimina_nota", None).invoke({"id": 1})

    assert risultato == MSG_NON_CONFERMATA
    assert nota_esiste(percorso)


@pytest.mark.parametrize("errore", [EOFError(), RuntimeError("boom")])
def test_conferma_negata_o_che_solleva_non_cancella(server_con_nota, errore):
    url, percorso = server_con_nota

    risultato = strumento(url, "elimina_nota", Conferma(solleva=errore)).invoke({"id": 1})

    assert risultato == MSG_NON_CONFERMATA
    assert nota_esiste(percorso)


def test_conferma_diversa_da_true_non_cancella(server_con_nota):
    url, percorso = server_con_nota

    risultato = strumento(url, "elimina_nota", lambda m: "s").invoke({"id": 1})  # truthy ma non True

    assert risultato == MSG_NON_CONFERMATA
    assert nota_esiste(percorso)


def test_ctrl_c_durante_la_conferma_non_viene_inghiottito(server_con_nota):
    url, percorso = server_con_nota

    with pytest.raises(KeyboardInterrupt):
        strumento(url, "elimina_nota", Conferma(solleva=KeyboardInterrupt())).invoke({"id": 1})

    assert nota_esiste(percorso)


def test_cancellazione_dopo_conferma_dell_utente(server_con_nota):
    url, percorso = server_con_nota
    conferma = Conferma(esito=True)

    risultato = strumento(url, "elimina_nota", conferma).invoke({"id": 1})

    assert risultato == "Nota 1 eliminata"
    assert not nota_esiste(percorso)
    assert len(conferma.messaggi) == 1
    assert "elimina_nota" in conferma.messaggi[0] and "1" in conferma.messaggi[0]


def test_id_inesistente_dopo_conferma(server_con_nota):
    url, percorso = server_con_nota

    risultato = strumento(url, "elimina_nota", Conferma(esito=True)).invoke({"id": 99})

    assert risultato == "Errore: nota 99 non trovata"
    assert nota_esiste(percorso)


def test_destructive_hint_acquisito_dalla_discovery_e_conservato_nel_tool(server):
    url, _ = server

    strumenti = scopri_strumenti(url)

    assert all(isinstance(t, BaseTool) for t in strumenti)
    assert {t.name: t.richiede_conferma for t in strumenti} == {
        "aggiungi_nota": False, "elenca_note": False, "elimina_nota": True,
    }
    per_nome = {t.name: t for t in strumenti}
    assert per_nome["elimina_nota"].metadata["destructiveHint"] is True
    assert per_nome["aggiungi_nota"].metadata["destructiveHint"] is False


def test_il_hint_viene_dal_server_non_dal_nome():
    eseguite = []
    prova = FastMCP("prova")

    @prova.tool(annotations={"destructiveHint": True})
    def cancella_tutto() -> str:
        """Operazione distruttiva di prova."""
        eseguite.append("cancella_tutto")
        return "fatto"

    @prova.tool
    def elimina_altro() -> str:
        """Nome minaccioso ma senza annotazione."""
        eseguite.append("elimina_altro")
        return "fatto"

    conferma = Conferma(esito=False)
    with avvia_server_mcp(prova) as url:
        per_nome = {t.name: t for t in scopri_strumenti(url, chiedi_conferma=conferma)}
        assert per_nome["elimina_altro"].invoke({}) == "fatto"
        assert conferma.messaggi == []
        assert per_nome["cancella_tutto"].invoke({}) == MSG_NON_CONFERMATA

    assert eseguite == ["elimina_altro"]
    assert len(conferma.messaggi) == 1 and "cancella_tutto" in conferma.messaggi[0]


def test_strumenti_non_distruttivi_non_chiedono_conferma(server):
    url, _ = server
    conferma = Conferma(esito=False)
    argomenti = {"aggiungi_nota": {"testo": "ciao"}, "elenca_note": {}}  # T8 aggiunge `meteo`

    non_distruttivi = [t for t in scopri_strumenti(url, chiedi_conferma=conferma) if not t.richiede_conferma]

    assert non_distruttivi
    for t in non_distruttivi:
        assert t.name in argomenti, f"aggiungere gli argomenti di prova per {t.name}"
        assert not t.invoke(argomenti[t.name]).startswith("Errore:")
    assert conferma.messaggi == []


# --- review del ramo: validazione prima della conferma, risultati lunghi e vuoti ---
from assistente.mcp_client import MAX_CARATTERI_RISULTATO


@pytest.mark.parametrize(
    "argomenti",
    [{}, {"id": "abc"}, {"id": "2"}, {"id": True}, {"id": 2.5}, {"id": None}],
)
def test_argomenti_non_validi_non_chiedono_conferma_ne_cancellano(server_con_nota, argomenti):
    url, percorso = server_con_nota
    conferma = Conferma(esito=True)

    risultato = strumento(url, "elimina_nota", conferma).invoke(argomenti)

    assert risultato.startswith("Errore: argomenti non validi")
    assert conferma.messaggi == []  # nessuna domanda all'utente per un'azione impossibile
    assert nota_esiste(percorso)  # in particolare id=True non diventa id=1


def test_argomento_extra_fuori_schema_non_cambia_il_percorso(server_con_nota):
    url, percorso = server_con_nota
    conferma = Conferma(esito=False)

    risultato = strumento(url, "elimina_nota", conferma).invoke({"id": 1, "conferma": True})

    assert risultato == MSG_NON_CONFERMATA
    assert len(conferma.messaggi) == 1
    assert nota_esiste(percorso)


def server_di_prova_con_risultati():
    prova = FastMCP("prova")

    @prova.tool
    def lungo() -> str:
        """Restituisce un testo molto lungo."""
        return "x" * (MAX_CARATTERI_RISULTATO * 3)

    @prova.tool
    def vuoto() -> str:
        """Restituisce una stringa vuota."""
        return ""

    @prova.tool
    def immagine() -> Image:
        """Restituisce solo un'immagine, senza testo."""
        return Image(data=b"\x89PNG\r\n", format="png")

    return prova


def test_risultato_troppo_lungo_viene_troncato_con_avviso():
    with avvia_server_mcp(server_di_prova_con_risultati()) as url:
        per_nome = {t.name: t for t in scopri_strumenti(url)}
        risultato = per_nome["lungo"].invoke({})

    assert risultato.startswith("x" * MAX_CARATTERI_RISULTATO)
    assert "troncato" in risultato
    assert len(risultato) < MAX_CARATTERI_RISULTATO + 300
    assert not risultato.startswith("Errore:")


@pytest.mark.parametrize("nome", ["vuoto", "immagine"])
def test_risultato_vuoto_o_non_testuale_non_e_una_stringa_vuota(nome):
    with avvia_server_mcp(server_di_prova_con_risultati()) as url:
        per_nome = {t.name: t for t in scopri_strumenti(url)}
        risultato = per_nome[nome].invoke({})

    assert risultato.strip()
    assert "nessun contenuto testuale" in risultato
    assert not risultato.startswith("Errore:")
