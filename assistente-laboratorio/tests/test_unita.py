import pytest

from assistente.unita import UNITA_AMMESSE, converti, converti_unita


@pytest.mark.parametrize("valore, da, a, atteso", [
    (10, "km", "mi", "10 km = 6.2137 mi"),
    (1, "mi", "km", "1 mi = 1.6093 km"),
    (100, "C", "F", "100 C = 212 F"),
    (212, "F", "C", "212 F = 100 C"),
    (0, "K", "C", "0 K = -273.15 C"),
    (0, "C", "K", "0 C = 273.15 K"),
    (1, "gal", "l", "1 gal = 3.7854 l"),
    (500, "ml", "l", "500 ml = 0.5 l"),
    (1, "kg", "lb", "1 kg = 2.2046 lb"),
    (16, "oz", "g", "16 oz = 453.5924 g"),
    (6, "ft", "in", "6 ft = 72 in"),
    (2.5, "m", "cm", "2.5 m = 250 cm"),
])
def test_conversioni(valore, da, a, atteso):
    assert converti(valore, da, a) == atteso


@pytest.mark.parametrize("da, a", [("KM", "MI"), (" Km ", "mI"), ("km", "Mi")])
def test_maiuscole_e_spazi_non_contano(da, a):
    assert converti(10, da, a) == "10 km = 6.2137 mi"


@pytest.mark.parametrize("da, a", [("c", "f"), ("°C", "°F"), ("C", "F")])
def test_temperature_con_minuscole_e_gradi(da, a):
    assert converti(100, da, a) == "100 C = 212 F"


def test_stessa_unita():
    assert converti(5, "km", "KM") == "5 km = 5 km"


def test_valore_numerico_come_testo():
    assert converti("10", "km", "mi") == "10 km = 6.2137 mi"
    assert converti(" 2.5 ", "m", "cm") == "2.5 m = 250 cm"


def test_zero_negativo_non_compare():
    assert converti(0, "m", "cm") == "0 m = 0 cm"
    assert converti(-0.00001, "m", "cm") == "-1e-05 m = -0.001 cm"


def assert_errore_con_unita(risultato):
    assert risultato.startswith("Errore:")
    for unita in ("mm", "km", "kg", "lb", "ml", "gal", "C", "F", "K"):
        assert unita in risultato  # l'errore elenca le unità ammesse


def test_unita_incompatibili():
    risultato = converti(10, "km", "kg")

    assert_errore_con_unita(risultato)
    assert "lunghezza" in risultato and "massa" in risultato


def test_unita_sconosciuta():
    risultato = converti(10, "parsec", "km")

    assert_errore_con_unita(risultato)
    assert "parsec" in risultato
    assert_errore_con_unita(converti(10, "km", "furlong"))


@pytest.mark.parametrize("valore", ["abc", "", "   ", "1,5", None, True, [1], float("nan"), float("inf"), "nan", "inf"])
def test_valore_non_valido(valore):
    risultato = converti(valore, "km", "mi")

    assert risultato.startswith("Errore:")
    assert "Traceback" not in risultato


@pytest.mark.parametrize("valore, da", [(-300, "C"), (-500, "F"), (-1, "K")])
def test_sotto_lo_zero_assoluto(valore, da):
    assert "zero assoluto" in converti(valore, da, "K" if da != "K" else "C")


def test_risultato_enorme():
    assert converti(1e308, "mi", "mm").startswith("Errore:")


def test_unita_ammesse_sono_le_attese():
    assert UNITA_AMMESSE == {
        "lunghezza": ["mm", "cm", "m", "km", "in", "ft", "mi"],
        "massa": ["g", "kg", "lb", "oz"],
        "volume": ["ml", "l", "gal"],
        "temperatura": ["C", "F", "K"],
    }


def test_strumento_ha_nome_schema_e_descrizione_in_italiano():
    assert converti_unita.name == "converti_unita"
    assert set(converti_unita.args) == {"valore", "da", "a"}
    descrizione = converti_unita.description
    assert "miglia" in descrizione and "Esempio" in descrizione


def test_strumento_restituisce_testo():
    assert converti_unita.invoke({"valore": 10, "da": "km", "a": "mi"}) == "10 km = 6.2137 mi"


def test_strumento_con_valore_testuale_non_solleva():
    risultato = converti_unita.invoke({"valore": "abc", "da": "km", "a": "mi"})

    assert risultato.startswith("Errore:")  # nessuna eccezione sollevata da invoke


# --- review del ramo: precisione dei valori piccoli e argomenti mancanti o di tipo sbagliato ---
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.grafo import costruisci_grafo
from finti import ModelloSimulato


@pytest.mark.parametrize("valore, da, a, atteso", [
    (2, "m", "mi", "2 m = 0.001243 mi"),
    (1, "g", "oz", "1 g = 0.03527 oz"),
    (5, "cm", "km", "5 cm = 5e-05 km"),
    (0.5, "kg", "g", "0.5 kg = 500 g"),
    (0.12345678, "m", "m", "0.1235 m = 0.1235 m"),
])
def test_i_risultati_piccoli_conservano_le_cifre_significative(valore, da, a, atteso):
    assert converti(valore, da, a) == atteso


@pytest.mark.parametrize("argomenti", [
    {"valore": 10, "da": "km"},            # manca `a`
    {"valore": 10, "da": 5, "a": "m"},     # `da` non è testo
    {"valore": None, "da": "km", "a": "mi"},
    {"valore": [1], "da": "km", "a": "mi"},
    {},
])
def test_argomenti_mancanti_o_di_tipo_sbagliato_danno_un_errore_chiaro(argomenti):
    risultato = converti_unita.invoke(argomenti)

    assert risultato.startswith("Errore:")
    assert "converti_unita" in risultato
    assert "validation error" not in risultato and "pydantic" not in risultato
    assert "\n" not in risultato  # una riga sola, leggibile da un modello piccolo


def test_il_grafo_riceve_l_errore_chiaro_e_prosegue():
    richiesta = {"name": "converti_unita", "args": {"valore": 10, "da": "km"}, "id": "x1", "type": "tool_call"}
    modello = ModelloSimulato([AIMessage("", tool_calls=[richiesta]), AIMessage("Riprovo")])

    esito = costruisci_grafo(modello, [converti_unita]).invoke({"messages": [HumanMessage("converti")]})

    risposta = next(m for m in esito["messages"] if isinstance(m, ToolMessage))
    assert risposta.tool_call_id == "x1"
    assert risposta.content.startswith("Errore: argomenti non validi per converti_unita")
    assert esito["messages"][-1].content == "Riprovo"
