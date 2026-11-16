"""Comandi della CLI per i prompt MCP (spec Step 5 §7–§10): funzioni pure, nessuna rete."""
import logging

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from assistente import comandi
from assistente.comandi import (
    CLIENT_NON_CONFIGURATO,
    COMANDO_SCONOSCIUTO,
    USO_PROMPT,
    USO_PROMPTS,
    ErroreComando,
    controlla_richiesta,
    converti_messaggi,
    esegui_comando,
    riga_uso,
    scomponi_richiesta,
)
from assistente.mcp_client import ArgomentoPrompt, ErroreMcp, PromptMcp

elenco = comandi.testo_elenco  # non importato col suo nome: pytest raccoglie le funzioni che iniziano con "test"

SPIEGA = PromptMcp(
    "spiega",
    "Spiega un argomento.",
    (ArgomentoPrompt("argomento", "", True), ArgomentoPrompt("livello", "", False)),
)
RIASSUMI = PromptMcp("riassumi_conversazione", "Riassume.", (ArgomentoPrompt("stile", "", False),))
SENZA_ARGOMENTI = PromptMcp("vuoto", "", ())
PROMPT = (SPIEGA, RIASSUMI)


class Client:
    """`elenca` e `ottieni` finti che registrano le chiamate."""

    def __init__(self, prompt=PROMPT, messaggi=(("user", "Spiega MCP"),), errore_elenca=None, errore_ottieni=None):
        self.prompt, self.messaggi = prompt, list(messaggi)
        self.errore_elenca, self.errore_ottieni = errore_elenca, errore_ottieni
        self.elencati = 0
        self.ottenuti = []

    def elenca(self):
        self.elencati += 1
        if self.errore_elenca:
            raise self.errore_elenca
        return self.prompt

    def ottieni(self, nome, argomenti):
        self.ottenuti.append((nome, argomenti))
        if self.errore_ottieni:
            raise self.errore_ottieni
        return self.messaggi


def comando(riga, client):
    return esegui_comando(riga, client.elenca, client.ottieni)


# --- scomposizione (§7.2) ---


@pytest.mark.parametrize(
    "riga, atteso",
    [
        (
            '/prompt spiega argomento="Model Context Protocol" livello=base',
            ("spiega", {"argomento": "Model Context Protocol", "livello": "base"}),
        ),
        ("/prompt spiega argomento=dell'MCP", ("spiega", {"argomento": "dell'MCP"})),
        ('/prompt spiega argomento="l\'intelligenza artificiale"', ("spiega", {"argomento": "l'intelligenza artificiale"})),
        (r"/prompt spiega argomento=C:\cartella\file", ("spiega", {"argomento": r"C:\cartella\file"})),
        ("/prompt spiega argomento=#uno", ("spiega", {"argomento": "#uno"})),
        ("/prompt spiega a=b=c", ("spiega", {"a": "b=c"})),
        ("/prompt spiega livello=", ("spiega", {"livello": ""})),
        ("/prompt spiega", ("spiega", {})),
    ],
)
def test_scomponi_richiesta(riga, atteso):
    assert scomponi_richiesta(riga) == atteso


def test_virgolette_non_chiuse():
    with pytest.raises(ErroreComando) as errore:
        scomponi_richiesta('/prompt spiega argomento="aperta')

    assert str(errore.value).startswith("Virgolette non chiuse.")
    assert USO_PROMPT in str(errore.value)


@pytest.mark.parametrize(
    "riga", ["/prompt", "/prompt spiega argomento", "/prompt spiega =x", "/prompt spiega a=1 a=2"]
)
def test_righe_non_valide(riga):
    with pytest.raises(ErroreComando) as errore:
        scomponi_richiesta(riga)

    assert USO_PROMPT in str(errore.value)


# --- controllo (§8) ---


def test_richiesta_valida():
    assert controlla_richiesta(PROMPT, "spiega", {"argomento": "x", "livello": "base"}) == []


@pytest.mark.parametrize("nome", ["xyz", "Spiega"])
def test_prompt_sconosciuto(nome):
    assert controlla_richiesta(PROMPT, nome, {"argomento": "x"}) == [
        f"Prompt sconosciuto: {nome}. Usa /prompts per l'elenco."
    ]


def test_argomento_obbligatorio_mancante():
    assert "Argomenti obbligatori mancanti: argomento." in controlla_richiesta(PROMPT, "spiega", {})


def test_argomento_sconosciuto():
    problemi = controlla_richiesta(PROMPT, "spiega", {"argomento": "x", "pippo": "1"})

    assert "Argomenti sconosciuti: pippo. Argomenti accettati: argomento, livello." in problemi


def test_valore_vuoto_anche_facoltativo():
    assert "Valore vuoto per: livello." in controlla_richiesta(PROMPT, "spiega", {"argomento": "x", "livello": "  "})


def test_piu_problemi_in_ordine_con_la_riga_d_uso():
    assert controlla_richiesta(PROMPT, "spiega", {"pippo": "1", "livello": ""}) == [
        "Argomenti obbligatori mancanti: argomento.",
        "Argomenti sconosciuti: pippo. Argomenti accettati: argomento, livello.",
        "Valore vuoto per: livello.",
        "Uso: /prompt spiega argomento=… [livello=…]",
    ]


def test_prompt_senza_argomenti():
    problemi = controlla_richiesta((SENZA_ARGOMENTI,), "vuoto", {"x": "1"})

    assert "Argomenti sconosciuti: x. Argomenti accettati: nessuno." in problemi


# --- uso ed elenco (§7.3) ---


def test_riga_uso():
    assert riga_uso(SPIEGA) == "Uso: /prompt spiega argomento=… [livello=…]"
    assert riga_uso(SENZA_ARGOMENTI) == "Uso: /prompt vuoto"


def test_testo_elenco():
    con_descrizione = PromptMcp("p", "Fa qualcosa.", (ArgomentoPrompt("a", "Che cosa.", True),))

    assert elenco((SPIEGA, con_descrizione, SENZA_ARGOMENTI)) == "\n".join(
        [
            "Prompt disponibili:",
            "/prompt spiega — Spiega un argomento.",
            "    argomento (obbligatorio)",
            "    livello (facoltativo)",
            "/prompt p — Fa qualcosa.",
            "    a (obbligatorio): Che cosa.",
            "/prompt vuoto",
        ]
    )


def test_testo_elenco_vuoto():
    assert elenco(()) == "Nessun prompt disponibile."


# --- conversione (§9) ---


def test_converti_messaggi():
    assert converti_messaggi([("user", "a")]) == [HumanMessage("a")]
    assert converti_messaggi([("assistant", "a"), ("user", "b")]) == [AIMessage("a"), HumanMessage("b")]


@pytest.mark.parametrize(
    "coppie, messaggio",
    [
        ([("user", "a"), ("assistant", "b")], "Prompt non utilizzabile: l'ultimo messaggio non è dell'utente."),
        ([], "Prompt non utilizzabile: nessun messaggio."),
        ([("system", "a")], "Prompt non utilizzabile: ruolo non riconosciuto: system."),
    ],
)
def test_converti_messaggi_non_utilizzabili(coppie, messaggio):
    with pytest.raises(ErroreComando) as errore:
        converti_messaggi(coppie)

    assert str(errore.value) == messaggio


# --- esegui_comando (§7, §10) ---


def test_prompts_elenca():
    client = Client()

    assert comando("/prompts", client) == ([elenco(PROMPT)], [])


def test_prompts_server_non_disponibile():
    client = Client(errore_elenca=ErroreMcp("x"))

    assert comando("/prompts", client) == (["Prompt MCP non disponibili: x"], [])


def test_prompts_con_altro_testo():
    client = Client()

    assert comando("/prompts x", client) == ([USO_PROMPTS], [])
    assert client.elencati == 0


@pytest.mark.parametrize("riga", ["/PROMPTS", "/aiuto", "/Prompt spiega argomento=x"])
def test_comando_sconosciuto(riga):
    client = Client()

    assert comando(riga, client) == ([COMANDO_SCONOSCIUTO], [])
    assert client.elencati == 0


@pytest.mark.parametrize("riga", ["/prompts", "/prompt spiega argomento=x", '/prompt spiega a="x'])
@pytest.mark.parametrize("manca", ["elenca", "ottieni"])
def test_client_non_configurato(riga, manca):
    client = Client()
    elenca = None if manca == "elenca" else client.elenca
    ottieni = None if manca == "ottieni" else client.ottieni

    assert esegui_comando(riga, elenca, ottieni) == ([CLIENT_NON_CONFIGURATO], [])


def test_prompt_con_elenca_in_errore():
    client = Client(errore_elenca=ErroreMcp("x"))

    assert comando("/prompt spiega argomento=x", client) == (["Prompt MCP non disponibili: x"], [])
    assert client.ottenuti == []


def test_prompt_scomposizione_fallita(caplog):
    client = Client()

    with caplog.at_level(logging.WARNING, logger="assistente.comandi"):
        righe, messaggi = comando('/prompt spiega argomento="aperta', client)

    assert righe[0].startswith("Virgolette non chiuse.") and messaggi == []
    assert client.elencati == 0 and client.ottenuti == []
    assert not caplog.records


def test_prompt_controllo_fallito(caplog):
    client = Client()

    with caplog.at_level(logging.WARNING, logger="assistente.comandi"):
        righe, messaggi = comando("/prompt spiega pippo=1", client)

    assert righe == controlla_richiesta(PROMPT, "spiega", {"pippo": "1"}) and messaggi == []
    assert client.ottenuti == []
    assert any("spiega" in r.getMessage() and "pippo" in r.getMessage() for r in caplog.records)


def test_prompt_rifiutato_dal_server():
    client = Client(errore_ottieni=ErroreMcp("y"))

    assert comando("/prompt spiega argomento=x", client) == (["Prompt non eseguito: y"], [])


def test_prompt_valido():
    client = Client()

    assert comando("/prompt spiega argomento=MCP", client) == (["[prompt spiega] Spiega MCP"], [HumanMessage("Spiega MCP")])
    assert client.ottenuti == [("spiega", {"argomento": "MCP"})]


def test_prompt_con_messaggio_dell_assistente():
    client = Client(messaggi=[("assistant", "a"), ("user", "b")])

    assert comando("/prompt spiega argomento=MCP", client) == (
        ["[prompt spiega, assistente] a", "[prompt spiega] b"],
        [AIMessage("a"), HumanMessage("b")],
    )


def test_prompt_conversione_fallita():
    client = Client(messaggi=[("user", "a"), ("assistant", "b")])

    assert comando("/prompt spiega argomento=MCP", client) == (
        ["Prompt non utilizzabile: l'ultimo messaggio non è dell'utente."],
        [],
    )
