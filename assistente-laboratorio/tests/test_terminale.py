import httpx
import openai
from langchain_core.messages import AIMessage, HumanMessage

from assistente.grafo import costruisci_grafo
from assistente.config import SOGLIA_RIASSUNTO_PREDEFINITA
from finti import riassuntore_inerte
from assistente.agente import Sessione, esegui_turno
from cli_su_api import chat_su_grafo
from fastapi.testclient import TestClient

from assistente import agente
from assistente.agente import costruisci_agente
from assistente.config import carica_config
from assistente.mcp_client import elenca_prompt, ottieni_prompt
from assistente.servizio_agente.app import crea_app
from assistente.terminale import esegui_chat
from assistente.preferenze import PREFERENZE_PREDEFINITE
from finti import AMBITO_TEST, ModelloSimulato, approva_sempre, in_ambito


def esegui(grafo, righe):
    """Fa girare la chat leggendo da `righe`; ritorna ciò che è stato stampato."""
    coda = list(righe)
    stampato = []

    def leggi():
        voce = coda.pop(0)
        if isinstance(voce, BaseException):
            raise voce
        return voce

    chat_su_grafo(grafo, leggi, stampato.append)
    return stampato


class GrafoSpia:
    def __init__(self):
        self.chiamate = 0

    def invoke(self, stato):
        self.chiamate += 1
        return {"messages": [*stato["messages"], AIMessage("x")]}


def grafo_con(*risposte):
    modello = ModelloSimulato([AIMessage(r) if isinstance(r, str) else r for r in risposte])
    return costruisci_grafo(modello, classificatore=in_ambito(), ambito=AMBITO_TEST, revisore=approva_sempre(), max_revisioni=1, riassuntore=riassuntore_inerte(), soglia_riassunto=SOGLIA_RIASSUNTO_PREDEFINITA), modello


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

    # Step 4 (spec §10.1): in testa c'è sempre il SystemMessage delle preferenze; la cronologia segue.
    sistema, *seconda = modello.chiamate[1]
    assert type(sistema).__name__ == "SystemMessage"
    assert [type(m) for m in seconda] == [HumanMessage, AIMessage, HumanMessage]
    assert [m.content for m in seconda] == ["Mi chiamo Marco", "Piacere, Marco", "Come mi chiamo?"]


def test_cronologia_non_persiste_tra_sessioni():
    grafo, modello = grafo_con("Uno", "Due")

    esegui(grafo, ["Prima sessione", "esci"])
    esegui(grafo, ["Seconda sessione", "esci"])

    # Step 4 (spec §10.1): in testa c'è sempre il SystemMessage delle preferenze; la cronologia segue.
    assert type(modello.chiamate[1][0]).__name__ == "SystemMessage"
    assert [m.content for m in modello.chiamate[1][1:]] == ["Seconda sessione"]


def test_errore_del_server_ripristina_la_cronologia():
    errore = openai.APIConnectionError(request=httpx.Request("POST", "http://localhost:1234/v1"))
    grafo, _ = grafo_con(errore)
    precedente = [HumanMessage("Ciao"), AIMessage("Salve")]

    sessione, testo = esegui_turno(grafo, Sessione(tuple(precedente)), "Nuova domanda", 6, max_revisioni=1)

    assert sessione.messaggi == tuple(precedente)
    assert "/v1/models" in testo


def test_risposta_vuota_stampa_un_avviso():
    grafo, _ = grafo_con("")

    stampato = esegui(grafo, ["Ciao", "esci"])

    assert any(riga.strip() and "vuota" in riga for riga in stampato)


def test_ctrl_c_durante_la_risposta_termina_senza_eccezioni():
    class ClientInterrotto:
        def chat(self, *a, **k):
            raise KeyboardInterrupt

    stampato = []
    righe = iter(["Ciao"])
    esegui_chat(ClientInterrotto(), lambda: next(righe), stampato.append)

    assert stampato == []


def test_contenuto_a_blocchi_viene_stampato_come_testo():
    grafo, _ = grafo_con(AIMessage(content=[{"type": "text", "text": "ciao dai blocchi"}]))

    stampato = esegui(grafo, ["Ciao", "esci"])

    assert any("ciao dai blocchi" in riga for riga in stampato)


def test_contenuto_a_blocchi_vuoto_stampa_un_avviso():
    grafo, _ = grafo_con(AIMessage(content=[]))

    stampato = esegui(grafo, ["Ciao", "esci"])

    assert any("vuota" in riga for riga in stampato)



def ambiente_agente(monkeypatch, crea_modello, url_mcp=None):
    """Costruisce l'agente come il servizio (`costruisci_agente`), con modelli simulati."""
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("LM_STUDIO_MODEL", "m")
    monkeypatch.setenv("AMBITO_AGENTE", "a")
    if url_mcp:
        monkeypatch.setenv("MCP_URL", url_mcp)
    monkeypatch.setattr(agente, "crea_classificatore", lambda config: in_ambito())
    monkeypatch.setattr(agente, "crea_revisore", lambda config: approva_sempre())
    monkeypatch.setattr(agente, "crea_modello", crea_modello)
    return costruisci_agente(carica_config())


def main_su_app(monkeypatch, app, leggi):
    """Esegue `terminale.main` con l'API servita in memoria e `input` sostituito da `leggi`."""
    monkeypatch.setattr("builtins.input", leggi)
    return terminale.main(crea_http=lambda **opzioni: TestClient(app))


def test_costruisci_agente_restituisce_gli_avvisi(monkeypatch):
    monkeypatch.setattr(
        agente, "componi_strumenti",
        lambda config, chiedi_conferma=None, carica_preferenze=None: ([], PREFERENZE_PREDEFINITE, ["AVVISO: server MCP assente"]),
    )
    _, avvisi = ambiente_agente(monkeypatch, lambda config, strumenti: ModelloSimulato([AIMessage("Ciao!")]))

    assert avvisi == ["AVVISO: server MCP assente"]


def test_main_con_agente_parzialmente_raggiungibile_avvisa_e_continua(monkeypatch, capsys):
    grafo, _ = grafo_con("Ciao!")
    app = crea_app(grafo, max_passaggi=6, max_revisioni=1, stato_mcp=lambda: "non raggiungibile: spento", stato_modello=lambda: "ok")
    righe = iter(["salve", "esci"])

    assert main_su_app(monkeypatch, app, lambda prompt="": next(righe)) == 0

    letto = capsys.readouterr()
    assert "non raggiungibile: spento" in letto.err
    assert "Ciao!" in letto.out


def test_main_senza_agente_esce_con_1(monkeypatch, capsys):
    monkeypatch.setenv("AGENTE_URL", "http://127.0.0.1:9")  # porta chiusa

    assert terminale.main() == 1

    assert "Agente non raggiungibile su http://127.0.0.1:9" in capsys.readouterr().err


# --- T5: conferma di cancellazione chiesta dal terminale, con server MCP reale ---
import sqlite3

import pytest

from assistente import terminale
from assistente.note import ArchivioNote
from assistente.server_mcp import crea_server
from server_reale import avvia_server_mcp


def esegui_main_con_cancellazione(monkeypatch, tmp_path, risposta_conferma, argomenti=None):
    """Fa girare CLI e API con un server MCP reale; il modello chiede subito `elimina_nota` (id 1).

    Con la conferma il turno si ripete (spec Step 6 §4.2): il modello simulato ha le risposte per due giri.
    Restituisce (prompt mostrati, esiste ancora la nota 1).
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
    risposte = [AIMessage("", tool_calls=[richiesta]), AIMessage("Fine")] * 2
    with avvia_server_mcp(crea_server(ArchivioNote(percorso))) as url:
        grafo, _ = ambiente_agente(monkeypatch, lambda config, strumenti: ModelloSimulato(risposte), url)
        app = crea_app(grafo, max_passaggi=6, max_revisioni=1)
        assert main_su_app(monkeypatch, app, finto_input) == 0
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


# --- Step 4: le preferenze arrivano all'orologio; la resource non passa a bind_tools ---
def test_main_bind_tools_senza_resource(monkeypatch, tmp_path):
    file_preferenze = tmp_path / "preferenze.json"
    file_preferenze.write_text('{"lingua": "inglese", "fuso_orario": "America/New_York", "stile": "dettagliato"}', encoding="utf-8")
    registrati = []
    modello = ModelloSimulato([AIMessage("Ciao!")])

    def crea_modello_finto(config, strumenti):
        registrati.extend(strumenti)
        return modello

    with avvia_server_mcp(crea_server(ArchivioNote(str(tmp_path / "note.db")), percorso_preferenze=file_preferenze)) as url:
        grafo, _ = ambiente_agente(monkeypatch, crea_modello_finto, url)
        righe = iter(["salve", "esci"])
        assert main_su_app(monkeypatch, crea_app(grafo, max_passaggi=6, max_revisioni=1), lambda prompt="": next(righe)) == 0

    nomi = [s.name for s in registrati]
    assert nomi == [
        "orologio", "converti_unita", "calcola",
        "giorni_lavorativi", "calcola_scadenza", "cerca_catalogo", "dettaglio_catalogo",
        "aggiungi_nota", "elenca_note", "elimina_nota", "meteo",
    ]
    assert not any("utente://" in s.description or "preferenze" in s.name for s in registrati)
    assert "America/New_York" in registrati[0].invoke({})
    # Le stesse preferenze arrivano in cima al prompt di sistema dell'agente (T5).
    assert "Rispondi sempre in inglese." in modello.chiamate[0][0].content


# --- Step 5: prompt MCP richiamati dalla CLI (spec 2026-11-16-prompt-mcp-design.md §10–§12) ---

from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.errors import GraphRecursionError

from assistente.comandi import CLIENT_NON_CONFIGURATO, COMANDO_SCONOSCIUTO
from assistente.mcp_client import ArgomentoPrompt, ErroreMcp, PromptMcp
from assistente.agente import esegui_turno_messaggi
from finti import ClassificatoreSimulato, valutazione

SPIEGA = PromptMcp(
    "spiega", "Spiega.", (ArgomentoPrompt("argomento", "", True), ArgomentoPrompt("livello", "", False))
)


def elenca_finto():
    return (SPIEGA,)


def ottieni_che_fallisce(nome, argomenti):
    raise ErroreMcp("server spento")


def ottieni_finto(nome, argomenti):
    return [("user", f"Spiega {argomenti['argomento']}")]


def chat(grafo, righe, elenca=elenca_finto, ottieni=ottieni_finto):
    coda = list(righe)
    stampato = []
    chat_su_grafo(grafo, lambda: coda.pop(0), stampato.append, elenca=elenca, ottieni=ottieni)
    return stampato


class GrafoRegistra:
    """Grafo spia che accetta `config` come quello vero e registra lo stato ricevuto."""

    def __init__(self):
        self.stati = []

    def invoke(self, stato, config=None):
        self.stati.append(stato)
        return {"messages": [*stato["messages"], AIMessage("x")], "riassunto": stato["riassunto"]}


@pytest.mark.parametrize(
    "riga, ottieni, elenca, attesa",
    [
        ("/prompts", ottieni_finto, elenca_finto, "Prompt disponibili:"),
        ("/aiuto", ottieni_finto, elenca_finto, COMANDO_SCONOSCIUTO),
        ("/prompt spiega", ottieni_finto, elenca_finto, "Argomenti obbligatori mancanti: argomento."),
        ("/prompt spiega argomento=x", ottieni_che_fallisce, elenca_finto, "Prompt non eseguito: server spento"),
        ("/prompts", ottieni_finto, None, CLIENT_NON_CONFIGURATO),
    ],
)
def test_comandi_non_invocano_il_grafo(riga, ottieni, elenca, attesa):
    spia = GrafoRegistra()

    stampato = chat(spia, [riga, "esci"], elenca=elenca, ottieni=ottieni)

    assert spia.stati == []
    assert any(attesa in r for r in stampato)


def test_comandi_senza_client_nella_chat_di_sempre():
    spia = GrafoRegistra()

    assert esegui(spia, ["/prompts", "esci"]) == [CLIENT_NON_CONFIGURATO]
    assert spia.stati == []


def test_prompt_valido_passa_al_grafo():
    spia = GrafoRegistra()

    stampato = chat(spia, ["/prompt spiega argomento=MCP", "esci"])

    ultimo = spia.stati[0]["messages"][-1]
    assert isinstance(ultimo, HumanMessage) and ultimo.content == "Spiega MCP"
    assert stampato == ["[prompt spiega] Spiega MCP", "x"]


def test_domanda_dopo_un_prompt_vede_il_prompt():
    grafo, modello = grafo_con("risposta al prompt", "risposta 2")

    chat(grafo, ["/prompt spiega argomento=MCP", "e poi?", "esci"])

    contenuti = [m.content for m in modello.chiamate[1][1:]]
    assert contenuti == ["Spiega MCP", "risposta al prompt", "e poi?"]


class GrafoCheFallisce:
    def invoke(self, stato, config=None):
        raise GraphRecursionError("limite")


def test_turno_di_prompt_fallito_lascia_la_sessione():
    sessione = Sessione((HumanMessage("Ciao"), AIMessage("Salve")))

    nuova, testo = esegui_turno_messaggi(GrafoCheFallisce(), sessione, [HumanMessage("Spiega MCP")], 6, max_revisioni=1)

    assert nuova is sessione
    assert "limite" in testo


def test_prompt_attraversa_tutto_il_grafo():
    chiamate_strumento = []

    def strumento_finto() -> str:
        """Strumento di prova."""
        chiamate_strumento.append(True)
        return "ok"

    strumento = StructuredTool.from_function(strumento_finto, name="strumento_finto")
    modello = ModelloSimulato([
        AIMessage("", tool_calls=[{"name": "strumento_finto", "args": {}, "id": "c1", "type": "tool_call"}]),
        AIMessage("risposta finale"),
    ])
    classificatore, revisore = in_ambito(), ClassificatoreSimulato([valutazione(True, "ok")], True)
    grafo = costruisci_grafo(
        modello, [strumento], classificatore=classificatore, ambito=AMBITO_TEST, revisore=revisore, max_revisioni=1,
        riassuntore=riassuntore_inerte(), soglia_riassunto=SOGLIA_RIASSUNTO_PREDEFINITA,
    )
    prompt = HumanMessage("Spiega l'argomento «MCP» a livello base.")

    sessione, testo = esegui_turno_messaggi(grafo, Sessione(), [prompt], 6, max_revisioni=1)

    assert testo == "risposta finale"
    assert len(classificatore.chiamate) == 1 and len(revisore.chiamate) == 1
    assert chiamate_strumento == [True]
    assert sessione.messaggi[0].content == prompt.content
    assert any(isinstance(m, ToolMessage) for m in sessione.messaggi)


def test_main_prompt_spiega_dal_server_reale(monkeypatch, tmp_path, capsys):
    modello = ModelloSimulato([AIMessage("MCP è un protocollo.")])
    with avvia_server_mcp(crea_server(ArchivioNote(str(tmp_path / "note.db")))) as url:
        grafo, _ = ambiente_agente(monkeypatch, lambda config, strumenti: modello, url)
        app = crea_app(
            grafo, max_passaggi=6, max_revisioni=1,
            elenca=lambda: elenca_prompt(url), ottieni=lambda nome, argomenti: ottieni_prompt(url, nome, argomenti),
        )
        righe = iter(["/prompts", '/prompt spiega argomento="Model Context Protocol"', "esci"])
        assert main_su_app(monkeypatch, app, lambda prompt="": next(righe)) == 0

    uscita = capsys.readouterr().out
    assert "Prompt disponibili:" in uscita
    assert "[prompt spiega] Spiega l'argomento «Model Context Protocol» a livello base." in uscita
    assert "MCP è un protocollo." in uscita
    ultimo = modello.chiamate[0][-1]
    assert isinstance(ultimo, HumanMessage)
    assert ultimo.content.startswith("Spiega l'argomento «Model Context Protocol» a livello base.")
