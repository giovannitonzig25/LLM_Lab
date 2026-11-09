import builtins

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.calcolatrice import calcola, valuta
from assistente.grafo import costruisci_grafo
from finti import ModelloSimulato


@pytest.mark.parametrize("espressione, atteso", [
    ("2+3*4", "14"),
    ("(2+3)*4", "20"),
    ("2**10", "1024"),
    ("-3**2", "-9"),
    ("(-3)**2", "9"),
    ("10/4", "2.5"),
    ("10/5", "2"),
    ("17*23+5", "396"),
    ("1/3", "0.3333333333"),
    ("0.1+0.2", "0.3"),
    ("2**-2", "0.25"),
    ("2**0.5", "1.414213562"),
    ("+5", "5"),
    ("--5", "5"),
    ("  7 * 6  ", "42"),
    ("1e3+1", "1001"),
    (".5*4", "2"),
    ("100000*10000000", "1000000000000"),
    ("0*-1", "0"),
])
def test_espressioni_valide(espressione, atteso):
    assert valuta(espressione) == atteso


def assert_errore(risultato):
    assert risultato.startswith("Errore:")
    assert "Traceback" not in risultato


@pytest.mark.parametrize("espressione", [
    "1/0", "0**-1", "5/(3-3)",
    "2+", "*3", "(1+2", "1+2)", "", "   ", "1 2",
    "__import__('os')", "abs(1)", "a+1", "x", "pi",
    "9**9**9", "2**1000", "2**101", "2**-101", "10**100",
    "1; 2", "1\n+2", "1,5+1", "3^2", "7//2", "7%2", "1+'a'", "'a'*3", "[1]", "{1}", "(1,2)", "1 if 1 else 2",
    "lambda: 1", "().__class__", "1 < 2", "not 1", "True", "None", "1j", "(-8)**0.5",
    "1e308*10", "1e999", "9" * 20, "999999999999999*10",
    "x" * 201, "1+" * 100 + "1" + " " * 5,
])
def test_espressioni_rifiutate_con_errore(espressione):
    assert_errore(valuta(espressione))


@pytest.mark.parametrize("valore", [None, 5, 2.5, ["1+1"], True])
def test_valore_non_testuale(valore):
    assert_errore(valuta(valore))


def test_limite_di_lunghezza():
    sommatoria = "+".join(["1"] * 100)  # 199 caratteri
    assert len(sommatoria) == 199 and valuta(sommatoria) == "100"
    assert valuta("1+" * 99 + "1" + " ") == "100"  # 200 caratteri
    assert_errore(valuta("1+" * 100 + "1"))        # 201 caratteri


def test_limiti_di_esponente_e_risultato():
    assert valuta("10**15") == "1000000000000000"   # esattamente al limite
    assert valuta("2**100".replace("100", "49")) == "562949953421312"  # 2**49, sotto il limite
    assert_errore(valuta("2**100"))      # 1.27e30 supera 1e15
    assert_errore(valuta("10**16"))
    assert_errore(valuta("1.5**100"))    # 4e17: l'esponente è ammesso, il risultato no


def test_nidificazione_profonda_non_solleva():
    for espressione in ("(" * 150 + "1" + ")" * 150, "-" * 190 + "1", "(" * 100 + "1+" * 50):
        assert isinstance(valuta(espressione), str)


def test_non_usa_eval_ne_exec(monkeypatch):
    def vietato(*args, **kwargs):
        raise AssertionError("eval/exec non devono essere usati")

    monkeypatch.setattr(builtins, "eval", vietato)
    monkeypatch.setattr(builtins, "exec", vietato)

    assert valuta("2+3*4") == "14"
    assert_errore(valuta("__import__('os').system('echo no')"))


def test_nessun_effetto_collaterale(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    valuta("open('x.txt','w')")
    valuta("__import__('os').system('echo ciao > y.txt')")

    assert list(tmp_path.iterdir()) == []


def test_strumento_ha_nome_schema_e_descrizione_in_italiano():
    assert calcola.name == "calcola"
    assert set(calcola.args) == {"espressione"}
    assert "Esempio" in calcola.description and "**" in calcola.description


def test_strumento_restituisce_testo():
    assert calcola.invoke({"espressione": "17*23+5"}) == "396"
    assert_errore(calcola.invoke({"espressione": "1/0"}))


@pytest.mark.parametrize("argomenti", [{}, {"espressione": None}, {"espressione": ["1+1"]}])
def test_argomenti_mancanti_o_sbagliati_danno_un_errore_chiaro(argomenti):
    risultato = calcola.invoke(argomenti)

    assert risultato.startswith("Errore:") and "calcola" in risultato
    assert "validation error" not in risultato and "\n" not in risultato


def test_il_grafo_riceve_il_risultato():
    richiesta = {"name": "calcola", "args": {"espressione": "17*23+5"}, "id": "k1", "type": "tool_call"}
    modello = ModelloSimulato([AIMessage("", tool_calls=[richiesta]), AIMessage("Fa 396")])

    esito = costruisci_grafo(modello, [calcola]).invoke({"messages": [HumanMessage("quanto fa 17 per 23 più 5?")]})

    risposta = next(m for m in esito["messages"] if isinstance(m, ToolMessage))
    assert risposta.tool_call_id == "k1" and risposta.content == "396"
