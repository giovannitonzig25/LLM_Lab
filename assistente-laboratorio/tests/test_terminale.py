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


def test_ctrl_c_durante_la_risposta_termina_senza_eccezioni():
    grafo, _ = grafo_con(KeyboardInterrupt())

    stampato = esegui(grafo, ["Ciao"])

    assert stampato == []


def test_contenuto_a_blocchi_viene_stampato_come_testo():
    grafo, _ = grafo_con(AIMessage(content=[{"type": "text", "text": "ciao dai blocchi"}]))

    stampato = esegui(grafo, ["Ciao", "esci"])

    assert any("ciao dai blocchi" in riga for riga in stampato)


def test_contenuto_a_blocchi_vuoto_stampa_un_avviso():
    grafo, _ = grafo_con(AIMessage(content=[]))

    stampato = esegui(grafo, ["Ciao", "esci"])

    assert any("vuota" in riga for riga in stampato)



def test_main_scrive_gli_avvisi_su_stderr_e_continua(monkeypatch, capsys):
    from assistente import terminale

    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("LM_STUDIO_MODEL", "m")
    monkeypatch.setattr(
        terminale, "componi_strumenti", lambda config, chiedi_conferma=None: ([], ["AVVISO: server MCP assente"])
    )
    monkeypatch.setattr(
        terminale, "crea_modello", lambda config, strumenti: ModelloSimulato([AIMessage("Ciao!")])
    )
    righe = iter(["salve", "esci"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(righe))

    assert terminale.main() == 0

    letto = capsys.readouterr()
    assert "AVVISO: server MCP assente" in letto.err
    assert "AVVISO: server MCP assente" not in letto.out
    assert "Ciao!" in letto.out


# --- T5: conferma di cancellazione chiesta dal terminale, con server MCP reale ---
import sqlite3

import pytest

from assistente import terminale
from assistente.note import ArchivioNote
from assistente.server_mcp import crea_server
from server_reale import avvia_server_mcp


def esegui_main_con_cancellazione(monkeypatch, tmp_path, risposta_conferma, argomenti=None):
    """Fa girare main() con un server reale; il modello chiede subito `elimina_nota` (id 1).

    Restituisce (prompt mostrati, esiste ancora la nota 1, testo della chat).
    """
    percorso = str(tmp_path / "note.db")
    ArchivioNote(percorso).aggiungi("da cancellare")
    prompt = []
    voci = iter(["cancella la nota 1", risposta_conferma, "esci"])

    def finto_input(testo=""):
        prompt.append(testo)
        voce = next(voci)
        if isinstance(voce, BaseException):
            raise voce
        return voce

    richiesta = {"name": "elimina_nota", "args": argomenti or {"id": 1, "conferma": True}, "id": "c1", "type": "tool_call"}
    with avvia_server_mcp(crea_server(ArchivioNote(percorso))) as url:
        monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
        monkeypatch.setenv("LM_STUDIO_MODEL", "m")
        monkeypatch.setenv("MCP_URL", url)
        monkeypatch.setattr(
            terminale, "crea_modello",
            lambda config, strumenti: ModelloSimulato([AIMessage("", tool_calls=[richiesta]), AIMessage("Fine")]),
        )
        monkeypatch.setattr("builtins.input", finto_input)
        assert terminale.main() == 0
    esiste = sqlite3.connect(percorso).execute("SELECT 1 FROM note WHERE id = 1").fetchone() is not None
    return prompt, esiste


@pytest.mark.parametrize("risposta", ["n", "", "no", "boh", EOFError()])
def test_main_conferma_negata_non_cancella(monkeypatch, tmp_path, capsys, risposta):
    prompt, esiste = esegui_main_con_cancellazione(monkeypatch, tmp_path, risposta)

    assert esiste
    assert any("[s/N]" in p and "elimina_nota" in p for p in prompt)
    assert "Fine" in capsys.readouterr().out  # nessun crash: il turno si conclude


@pytest.mark.parametrize("risposta", ["s", "sì", "SI"])
def test_main_conferma_positiva_cancella(monkeypatch, tmp_path, risposta):
    prompt, esiste = esegui_main_con_cancellazione(monkeypatch, tmp_path, risposta, {"id": 1})

    assert any("[s/N]" in p for p in prompt)
    assert not esiste


def test_chiedi_conferma_del_terminale(monkeypatch):
    messaggi = []
    monkeypatch.setattr("builtins.input", lambda p="": messaggi.append(p) or "s")

    assert terminale.chiedi_conferma("Confermi: elimina_nota {'id': 3}?") is True
    assert messaggi == ["Confermi: elimina_nota {'id': 3}? [s/N]: "]


# --- input con byte non validi (surrogati da stdin con surrogateescape) ---
def test_input_con_byte_non_valido_non_interrompe_la_sessione():
    grafo, modello = grafo_con("Fatto.")

    stampato = esegui(grafo, ["elimina la nota \udcc2", "esci"])

    assert any("Fatto." in riga for riga in stampato)
    ricevuto = modello.chiamate[0][-1].content
    ricevuto.encode("utf-8")  # il testo inviato al modello deve essere codificabile
    assert ricevuto.startswith("elimina la nota ") and "�" in ricevuto


def test_input_con_sequenza_utf8_troncata_viene_sostituito():
    grafo, modello = grafo_con("ok")

    esegui(grafo, ["caff\udcc3 e latte", "esci"])

    ricevuto = modello.chiamate[0][-1].content
    ricevuto.encode("utf-8")
    assert "�" in ricevuto and "latte" in ricevuto


def test_input_valido_con_accenti_e_virgolette_resta_invariato():
    grafo, modello = grafo_con("ok")

    esegui(grafo, ["Perché «città» costa 5 €?", "esci"])

    assert modello.chiamate[0][-1].content == "Perché «città» costa 5 €?"


def test_input_con_surrogato_isolato_qualsiasi_non_interrompe_la_sessione():
    grafo, modello = grafo_con("ok")

    stampato = esegui(grafo, ["prova \ud800 fine", "esci"])

    assert any("ok" in riga for riga in stampato)
    modello.chiamate[0][-1].content.encode("utf-8")
