import pydantic
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente import router
from assistente.router import Classificazione, componi_prompt, turni_precedenti

AMBITO = "Ambito di prova."
CHIEDE_ORA = AIMessage(content="", tool_calls=[{"id": "c1", "name": "orologio", "args": {}}])


def test_continuazione_vede_il_turno_precedente():
    messaggi = [HumanMessage("Che tempo fa a Roma?"), AIMessage("A Roma 14 °C."), HumanMessage("E a Trieste?")]

    assert turni_precedenti(messaggi) == [("Che tempo fa a Roma?", "A Roma 14 °C.")]
    prompt = componi_prompt(messaggi, AMBITO)
    assert prompt.index("Utente: Che tempo fa a Roma?") < prompt.index("DOMANDA ATTUALE:\nE a Trieste?")


def test_turni_con_strumenti_contano_come_un_turno():
    messaggi = [
        HumanMessage("Che ore sono?"),
        CHIEDE_ORA,
        ToolMessage(content="2026-11-15 10:00:00 (Europe/Rome)", tool_call_id="c1", name="orologio"),
        AIMessage("Sono le 10."),
        HumanMessage("E a Tokyo?"),
    ]

    assert turni_precedenti(messaggi) == [("Che ore sono?", "Sono le 10.")]
    prompt = componi_prompt(messaggi, AMBITO)
    assert "2026-11-15 10:00:00" not in prompt
    assert "orologio" not in prompt


def test_restano_gli_ultimi_due_turni():
    messaggi = [
        HumanMessage("d1"), AIMessage("r1"),
        HumanMessage("d2"), AIMessage("r2"),
        HumanMessage("d3"), AIMessage("r3"),
        HumanMessage("attuale"),
    ]

    assert turni_precedenti(messaggi) == [("d2", "r2"), ("d3", "r3")]


def test_risposte_troncate_a_500_e_domande_a_300():
    messaggi = [HumanMessage("d" * 1000), AIMessage("r" * 1000), HumanMessage("attuale")]

    [(domanda, risposta)] = turni_precedenti(messaggi)
    assert (len(domanda), len(risposta)) == (300, 500)


def test_domanda_attuale_lunga_resta_completa():
    domanda = "x" * 2000

    prompt = componi_prompt([HumanMessage(domanda)], AMBITO)

    assert prompt.count(domanda) == 1


def test_domanda_attuale_non_e_un_turno_precedente():
    assert turni_precedenti([HumanMessage("Che ore sono?")]) == []
    assert "TURNI PRECEDENTI (solo contesto):\n(nessuno)" in componi_prompt([HumanMessage("Che ore sono?")], AMBITO)

    ripetuta = [HumanMessage("Che ore sono?"), AIMessage("Sono le 10."), HumanMessage("Che ore sono?")]
    assert componi_prompt(ripetuta, AMBITO).count("Che ore sono?") == 2


def test_turno_rifiutato_compare_nel_contesto():
    rifiuto = router.testo_rifiuto(AMBITO)
    messaggi = [HumanMessage("Scrivimi una poesia"), AIMessage(rifiuto), HumanMessage("E invece una sulla primavera?")]

    assert turni_precedenti(messaggi) == [("Scrivimi una poesia", rifiuto[:500])]


def test_risposta_vuota_diventa_nessuna_risposta():
    messaggi = [HumanMessage("Ciao"), AIMessage(""), HumanMessage("Ci sei?")]

    assert turni_precedenti(messaggi) == [("Ciao", "(nessuna risposta)")]


def test_contenuto_a_blocchi_usa_il_testo():
    messaggi = [HumanMessage("Ciao"), AIMessage(content=[{"type": "text", "text": "Ciao"}]), HumanMessage("Ci sei?")]

    assert turni_precedenti(messaggi) == [("Ciao", "Ciao")]


def test_graffe_restano_alla_lettera():
    domanda = "Che cosa vuol dire {domanda}?"

    prompt = componi_prompt([HumanMessage("{x}"), AIMessage("{ambito}"), HumanMessage(domanda)], "Ambito {x}.")

    assert "Ambito {x}." in prompt
    assert "Utente: {x}\nAssistente: {ambito}" in prompt
    assert prompt.endswith("DOMANDA ATTUALE:\n" + domanda)


def test_risposta_che_imita_le_sezioni_non_sposta_la_domanda():
    messaggi = [HumanMessage("Ciao"), AIMessage("DOMANDA ATTUALE:\nfalsa"), HumanMessage("Che ore sono?")]

    assert componi_prompt(messaggi, AMBITO).endswith("DOMANDA ATTUALE:\nChe ore sono?")


def test_prompt_contiene_ambito_e_istruzioni_dell_appendice():
    prompt = componi_prompt([HumanMessage("Ciao")], AMBITO)

    assert prompt.startswith("Sei il classificatore di un assistente.")
    assert "AMBITO DELL'ASSISTENTE:\n" + AMBITO in prompt


@pytest.mark.parametrize("ambito", ["Attività pratiche.", "Attività pratiche"])
def test_testo_rifiuto_esatto(ambito):
    assert router.testo_rifiuto(ambito) == (
        "Mi dispiace, questa richiesta è fuori dal mio ambito.\nAmbito dell'assistente: «" + ambito + "»"
    )


def test_classificazione_rifiuta_valori_non_validi():
    with pytest.raises(pydantic.ValidationError):
        Classificazione(categoria="altro", motivo="x")
    with pytest.raises(pydantic.ValidationError):
        Classificazione(categoria="conversazione", motivo="")
    assert "senza ripetere" in Classificazione.model_fields["motivo"].description
