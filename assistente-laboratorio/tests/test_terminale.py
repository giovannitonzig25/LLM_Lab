import httpx
import openai
from langchain_core.messages import AIMessage, HumanMessage

from assistente.grafo import costruisci_grafo
from assistente.terminale import esegui_chat, esegui_turno
from finti import ModelloSimulato


def esegui(grafo, righe):
    """Fa girare la chat leggendo da `righe`; ritorna ciò che è stato stampato."""
    coda = list(righe)
    stampato = []

    def leggi():
        voce = coda.pop(0)
        if isinstance(voce, BaseException):
            raise voce
        return voce

    esegui_chat(grafo, 6, leggi, stampato.append)
    return stampato


class GrafoSpia:
    def __init__(self):
        self.chiamate = 0

    def invoke(self, stato):
        self.chiamate += 1
        return {"messages": [*stato["messages"], AIMessage("x")]}


def grafo_con(*risposte):
    modello = ModelloSimulato([AIMessage(r) if isinstance(r, str) else r for r in risposte])
    return costruisci_grafo(modello), modello


def test_esci_termina_la_chat():
    grafo, _ = grafo_con()

    assert esegui(grafo, ["esci"]) == []


def test_domanda_stampa_la_risposta():
    grafo, _ = grafo_con("Salve!")

    stampato = esegui(grafo, ["Ciao", "esci"])

    assert any("Salve!" in riga for riga in stampato)


def test_riga_vuota_ignorata():
    spia = GrafoSpia()

    esegui(spia, ["", "   ", "esci"])

    assert spia.chiamate == 0


def test_eof_termina_senza_eccezioni():
    esegui(grafo_con()[0], [EOFError()])


def test_ctrl_c_termina_senza_eccezioni():
    esegui(grafo_con()[0], [KeyboardInterrupt()])


def test_errore_del_server_non_interrompe_la_chat():
    errore = openai.APIConnectionError(request=httpx.Request("POST", "http://localhost:1234/v1"))
    grafo, _ = grafo_con(errore, "Eccomi")

    stampato = esegui(grafo, ["Prima", "Seconda", "esci"])

    assert any("/v1/models" in riga for riga in stampato)
    assert any("Eccomi" in riga for riga in stampato)


def test_la_seconda_domanda_vede_la_prima():
    grafo, modello = grafo_con("Piacere, Marco", "Ti chiami Marco")

    esegui(grafo, ["Mi chiamo Marco", "Come mi chiamo?", "esci"])

    seconda = modello.chiamate[1]
    assert [type(m) for m in seconda] == [HumanMessage, AIMessage, HumanMessage]
    assert [m.content for m in seconda] == ["Mi chiamo Marco", "Piacere, Marco", "Come mi chiamo?"]


def test_cronologia_non_persiste_tra_sessioni():
    grafo, modello = grafo_con("Uno", "Due")

    esegui(grafo, ["Prima sessione", "esci"])
    esegui(grafo, ["Seconda sessione", "esci"])

    assert [m.content for m in modello.chiamate[1]] == ["Seconda sessione"]


def test_errore_del_server_ripristina_la_cronologia():
    errore = openai.APIConnectionError(request=httpx.Request("POST", "http://localhost:1234/v1"))
    grafo, _ = grafo_con(errore)
    precedente = [HumanMessage("Ciao"), AIMessage("Salve")]

    cronologia, testo = esegui_turno(grafo, precedente, "Nuova domanda", 6)

    assert cronologia == precedente
    assert "/v1/models" in testo


def test_risposta_vuota_stampa_un_avviso():
    grafo, _ = grafo_con("")

    stampato = esegui(grafo, ["Ciao", "esci"])

    assert any(riga.strip() and "vuota" in riga for riga in stampato)
