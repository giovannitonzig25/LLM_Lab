import logging

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.grafo import costruisci_grafo
from assistente.strumenti import STRUMENTI
from assistente.terminale import esegui_chat, esegui_turno
from finti import ModelloSimulato

CHIEDE_ORA = AIMessage(content="", tool_calls=[{"id": "c1", "name": "orologio", "args": {}}])


class ModelloCondizionale:
    """Chiede lo strumento all'infinito per la domanda «loop», risponde «Ok» a tutte le altre."""

    def invoke(self, messaggi):
        ultimo = messaggi[-1]
        if isinstance(ultimo, ToolMessage) or ultimo.content == "loop":
            return CHIEDE_ORA.model_copy(deep=True)
        return AIMessage("Ok")


def grafo_in_loop():
    return costruisci_grafo(ModelloCondizionale(), STRUMENTI)


def test_limite_ripristina_la_cronologia():
    precedente = [HumanMessage("Ciao"), AIMessage("Salve")]

    cronologia, _ = esegui_turno(grafo_in_loop(), precedente, "loop", 6)

    assert cronologia == precedente


def test_nessun_messaggio_parziale_resta():
    cronologia, _ = esegui_turno(grafo_in_loop(), [], "loop", 6)

    assert cronologia == []
    assert not any(isinstance(m, ToolMessage) or getattr(m, "tool_calls", None) for m in cronologia)


def test_messaggio_chiaro_all_utente():
    _, testo = esegui_turno(grafo_in_loop(), [], "loop", 6)

    assert "non è stata completata" in testo
    assert "riprovare" in testo and "riformulare" in testo


def test_la_chat_continua_dopo_il_limite():
    righe = iter(["loop", "Una domanda normale", "esci"])
    stampato = []

    esegui_chat(grafo_in_loop(), 6, lambda: next(righe), stampato.append)

    assert "non è stata completata" in stampato[0]
    assert stampato[1] == "Ok"


def test_log_del_limite(caplog):
    with caplog.at_level(logging.WARNING, logger="assistente.terminale"):
        esegui_turno(grafo_in_loop(), [], "loop", 6)

    assert any("limite" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(
    ("limite", "chiamate_al_modello", "strumenti_eseguiti"),
    [(2, 1, 1), (6, 3, 3)],  # valori osservati con LangGraph 1.2.19, non dedotti: vedi README
)
def test_caratterizza_il_limite_di_passaggi(caplog, limite, chiamate_al_modello, strumenti_eseguiti):
    modello = ModelloSimulato([CHIEDE_ORA], ripeti_ultima=True)

    with caplog.at_level(logging.INFO, logger="assistente.strumenti"):
        esegui_turno(costruisci_grafo(modello, STRUMENTI), [], "Che ora è?", limite)

    eseguiti = [r for r in caplog.records if "eseguito" in r.getMessage()]
    assert (len(modello.chiamate), len(eseguiti)) == (chiamate_al_modello, strumenti_eseguiti)
