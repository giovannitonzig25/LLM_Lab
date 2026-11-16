"""Step 6: API dell'agente con il grafo simulato (nessun modello, nessuna rete)."""
import httpx
import openai
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, messages_from_dict
from langchain_core.tools import StructuredTool

from assistente.agente import ErroreModello, Sessione, conferma_da_richiesta, esegui_turno_api
from assistente.config import SOGLIA_RIASSUNTO_PREDEFINITA
from assistente.grafo import costruisci_grafo
from assistente.mcp_client import ErroreMcp
from assistente.servizio_agente.app import crea_app
from finti import AMBITO_TEST, ModelloSimulato, approva_sempre, in_ambito, riassuntore_inerte


def chiamata(nome, argomenti, id_="c1"):
    return AIMessage("", tool_calls=[{"name": nome, "args": argomenti, "id": id_, "type": "tool_call"}])


def grafo_con(risposte, strumenti=()):
    modello = ModelloSimulato(risposte)
    grafo = costruisci_grafo(
        modello, list(strumenti), classificatore=in_ambito(), ambito=AMBITO_TEST, revisore=approva_sempre(),
        max_revisioni=1, riassuntore=riassuntore_inerte(), soglia_riassunto=SOGLIA_RIASSUNTO_PREDEFINITA,
    )
    return grafo, modello


def api(grafo, **dipendenze):
    return TestClient(crea_app(grafo, max_passaggi=6, max_revisioni=1, **dipendenze))


def orologio(timezone: str) -> str:
    """Ora nel fuso indicato."""
    return f"12:00 {timezone}"


cancellate = []


def cancella(id: int) -> str:
    """Strumento distruttivo di prova: chiede la conferma della richiesta come gli strumenti MCP."""
    if not conferma_da_richiesta("cancella", {"id": id}):
        return "Errore: cancellazione non confermata dall'utente"
    cancellate.append(id)
    return "cancellata"


STRUMENTI = [StructuredTool.from_function(orologio), StructuredTool.from_function(cancella)]


def test_chat_restituisce_risposta_cronologia_e_strumenti_usati(caplog):
    grafo, _ = grafo_con([chiamata("orologio", {"timezone": "Asia/Tokyo"}), AIMessage("A Tokyo sono le 12.")], STRUMENTI)

    with caplog.at_level("INFO"):
        risposta = api(grafo).post("/chat", json={"messaggio": "Che ore sono a Tokyo?"})

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["risposta"] == "A Tokyo sono le 12."
    assert corpo["strumenti_usati"] == [{"nome": "orologio", "argomenti": {"timezone": "Asia/Tokyo"}}]
    assert corpo["conferme_richieste"] == []
    tipi = [m.type for m in messages_from_dict(corpo["cronologia"])]
    assert tipi == ["human", "ai", "tool", "ai"]
    assert any("turno: esito=risposta strumenti=['orologio']" in r.message for r in caplog.records)


def test_la_cronologia_restituita_vale_per_il_turno_successivo():
    grafo, modello = grafo_con([AIMessage("Piacere, Marco"), AIMessage("Ti chiami Marco")])
    client = api(grafo)

    primo = client.post("/chat", json={"messaggio": "Mi chiamo Marco"}).json()
    client.post("/chat", json={"messaggio": "Come mi chiamo?", "cronologia": primo["cronologia"], "riassunto": "r"})

    contenuti = [m.content for m in modello.chiamate[1][1:]]
    assert contenuti == ["Mi chiamo Marco", "Piacere, Marco", "Come mi chiamo?"]
    assert "r" in modello.chiamate[1][0].content  # il riassunto ricevuto arriva al prompt di sistema


def test_strumento_distruttivo_solo_con_la_conferma_della_richiesta():
    cancellate.clear()
    risposte = [chiamata("cancella", {"id": 3}), AIMessage("Non confermata"), chiamata("cancella", {"id": 3}), AIMessage("Fatto")]
    grafo, _ = grafo_con(risposte, STRUMENTI)
    client = api(grafo)

    primo = client.post("/chat", json={"messaggio": "cancella la nota 3"}).json()
    assert cancellate == []
    assert primo["conferme_richieste"] == [{"strumento": "cancella", "argomenti": {"id": 3}}]

    secondo = client.post("/chat", json={"messaggio": "cancella la nota 3", "conferme": primo["conferme_richieste"]}).json()
    assert cancellate == [3]
    assert secondo["risposta"] == "Fatto" and secondo["conferme_richieste"] == []


def test_conferma_con_argomenti_diversi_non_vale():
    cancellate.clear()
    grafo, _ = grafo_con([chiamata("cancella", {"id": 4}), AIMessage("No")], STRUMENTI)

    corpo = api(grafo).post(
        "/chat", json={"messaggio": "cancella", "conferme": [{"strumento": "cancella", "argomenti": {"id": 3}}]}
    ).json()

    assert cancellate == []
    assert corpo["conferme_richieste"] == [{"strumento": "cancella", "argomenti": {"id": 4}}]


def test_messaggio_e_messaggi_insieme_o_nessuno_danno_422():
    grafo, _ = grafo_con([])
    client = api(grafo)

    assert client.post("/chat", json={"messaggio": "a", "messaggi": [{"ruolo": "user", "testo": "b"}]}).status_code == 422
    assert client.post("/chat", json={}).status_code == 422


def test_modello_irraggiungibile_da_503_con_messaggio():
    errore = openai.APIConnectionError(request=httpx.Request("POST", "http://localhost:1234/v1"))
    grafo, _ = grafo_con([errore])

    risposta = api(grafo).post("/chat", json={"messaggio": "Ciao"})

    assert risposta.status_code == 503
    assert "LM Studio" in risposta.json()["errore"]


def test_errore_modello_ha_il_codice():
    errore = openai.APIConnectionError(request=httpx.Request("POST", "http://localhost:1234/v1"))
    grafo, _ = grafo_con([errore])

    try:
        esegui_turno_api(grafo, Sessione(), [HumanMessage("Ciao")], 6, max_revisioni=1)
    except ErroreModello as e:
        assert e.codice == 503
    else:
        raise AssertionError("ErroreModello non sollevato")


def test_stato_503_se_mcp_non_raggiungibile():
    grafo, _ = grafo_con([])
    client = api(grafo, stato_mcp=lambda: "non raggiungibile: spento", stato_modello=lambda: "ok")

    risposta = client.get("/stato")

    assert risposta.status_code == 503
    assert risposta.json() == {"agente": "ok", "mcp": "non raggiungibile: spento", "modello": "ok"}


def test_stato_200_se_tutto_raggiungibile():
    grafo, _ = grafo_con([])

    assert api(grafo, stato_mcp=lambda: "ok", stato_modello=lambda: "ok").get("/stato").status_code == 200


def test_prompt_con_mcp_spento_danno_503():
    def elenca():
        raise ErroreMcp("discovery dei prompt impossibile")

    grafo, _ = grafo_con([])
    risposta = api(grafo, elenca=elenca, ottieni=lambda n, a: []).get("/prompts")

    assert risposta.status_code == 503
    assert risposta.json() == {"errore": "discovery dei prompt impossibile"}


def test_messaggi_di_un_prompt_aprono_il_turno():
    grafo, modello = grafo_con([AIMessage("Spiegazione")])

    corpo = api(grafo).post("/chat", json={"messaggi": [{"ruolo": "user", "testo": "Spiega MCP"}]}).json()

    assert corpo["risposta"] == "Spiegazione"
    assert modello.chiamate[0][-1].content == "Spiega MCP"


def test_documentazione_openapi_consultabile():
    grafo, _ = grafo_con([])
    client = api(grafo)

    schema = client.get("/openapi.json").json()

    assert {"/chat", "/stato", "/prompts", "/prompts/{nome}"} <= set(schema["paths"])
    assert client.get("/docs").status_code == 200
