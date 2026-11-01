import logging

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END

from assistente.grafo import costruisci_grafo, instrada
from assistente.strumenti import STRUMENTI
from finti import ModelloSimulato


def richiesta(*chiamate):
    """AIMessage che chiede strumenti: ogni chiamata è (identificativo, nome, argomenti)."""
    return AIMessage(
        content="",
        tool_calls=[{"id": i, "name": n, "args": a} for i, n, a in chiamate],
    )


def esegui(modello, domanda="Che ora è?"):
    grafo = costruisci_grafo(modello, STRUMENTI)
    return grafo.invoke({"messages": [HumanMessage(domanda)]})["messages"]


def test_instrada_senza_tool_calls_termina():
    assert instrada({"messages": [AIMessage("Ciao")]}) == END


def test_instrada_con_tool_calls_va_a_strumenti():
    stato = {"messages": [richiesta(("c1", "orologio", {}))]}

    assert instrada(stato) == "strumenti"


def test_percorso_con_strumento():
    modello = ModelloSimulato(
        [richiesta(("c1", "orologio", {"timezone": "Asia/Tokyo"})), AIMessage("Sono le ore tali")]
    )

    messaggi = esegui(modello)

    secondo_invio = modello.chiamate[1]
    risultato = secondo_invio[-1]
    assert isinstance(risultato, ToolMessage)
    assert risultato.tool_call_id == "c1"
    assert "Asia/Tokyo" in risultato.content
    assert messaggi[-1].content == "Sono le ore tali"


def test_due_richieste_nello_stesso_messaggio():
    modello = ModelloSimulato(
        [
            richiesta(("a", "orologio", {"timezone": "Asia/Tokyo"}), ("b", "orologio", {})),
            AIMessage("Fatto"),
        ]
    )

    esegui(modello)

    risultati = [m for m in modello.chiamate[1] if isinstance(m, ToolMessage)]
    assert [(m.tool_call_id, "Asia/Tokyo" in m.content) for m in risultati] == [("a", True), ("b", False)]
    assert "Europe/Rome" in risultati[1].content


def test_strumento_inesistente_da_errore_come_risultato():
    modello = ModelloSimulato([richiesta(("c1", "meteo", {})), AIMessage("Non posso")])

    messaggi = esegui(modello)

    risultato = modello.chiamate[1][-1]
    assert isinstance(risultato, ToolMessage)
    assert risultato.content.startswith("Errore:") and "meteo" in risultato.content
    assert messaggi[-1].content == "Non posso"


def test_argomenti_non_validi_danno_errore_come_risultato():
    modello = ModelloSimulato([richiesta(("c1", "orologio", {"timezone": 42})), AIMessage("Ok")])

    esegui(modello)

    assert modello.chiamate[1][-1].content.startswith("Errore:")


def test_log_richiesta_ed_esito(caplog):
    modello = ModelloSimulato(
        [richiesta(("c1", "orologio", {"timezone": "Asia/Tokyo"})), AIMessage("Ok")]
    )

    with caplog.at_level(logging.INFO, logger="assistente.strumenti"):
        esegui(modello)

    testi = [r.getMessage() for r in caplog.records]
    assert any("orologio" in t and "Asia/Tokyo" in t and "richiesto" in t for t in testi)
    assert any("eseguito" in t and "UTC+09:00" in t for t in testi)
