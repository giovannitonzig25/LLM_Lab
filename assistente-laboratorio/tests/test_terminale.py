from langchain_core.messages import AIMessage

from assistente.grafo import RISPOSTA_FISSA, costruisci_grafo
from assistente.terminale import esegui_chat


def esegui(grafo, righe):
    """Fa girare la chat leggendo da `righe`; ritorna ciò che è stato stampato."""
    coda = list(righe)
    stampato = []

    def leggi():
        voce = coda.pop(0)
        if isinstance(voce, BaseException):
            raise voce
        return voce

    esegui_chat(grafo, leggi, stampato.append)
    return stampato


class GrafoSpia:
    def __init__(self):
        self.chiamate = 0

    def invoke(self, stato):
        self.chiamate += 1
        return {"messages": [*stato["messages"], AIMessage("x")]}


def test_esci_termina_la_chat():
    assert esegui(costruisci_grafo(), ["esci"]) == []


def test_domanda_stampa_la_risposta():
    stampato = esegui(costruisci_grafo(), ["Ciao", "esci"])

    assert any(RISPOSTA_FISSA in riga for riga in stampato)


def test_riga_vuota_ignorata():
    spia = GrafoSpia()

    esegui(spia, ["", "   ", "esci"])

    assert spia.chiamate == 0


def test_eof_termina_senza_eccezioni():
    esegui(costruisci_grafo(), [EOFError()])


def test_ctrl_c_termina_senza_eccezioni():
    esegui(costruisci_grafo(), [KeyboardInterrupt()])
