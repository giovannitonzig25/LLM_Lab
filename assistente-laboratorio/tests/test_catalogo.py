import json
import re
from importlib import resources

from assistente.servizi_http.catalogo import carica_catalogo, cerca, trova

CAMPI = {"codice", "titolo", "settore", "sede", "durata_ore", "descrizione"}

CORSI = [
    {"codice": "X-1", "titolo": "Sviluppo Software", "settore": "Informatica", "sede": "Forlì",
     "durata_ore": 10, "descrizione": "d1"},
    {"codice": "X-2", "titolo": "Reti e sicurezza", "settore": "Informatica", "sede": "Udine",
     "durata_ore": 20, "descrizione": "d2"},
    {"codice": "X-3", "titolo": "Logistica", "settore": "Trasporti", "sede": "Udine",
     "durata_ore": 30, "descrizione": "d3"},
]


def codici(corsi):
    return [c["codice"] for c in corsi]


def test_cerca_per_titolo_settore_e_sede_senza_maiuscole():
    assert codici(cerca(CORSI, "SVILUPPO", 5)[1]) == ["X-1"]
    assert codici(cerca(CORSI, "informatica", 5)[1]) == ["X-1", "X-2"]
    assert codici(cerca(CORSI, "uDiNe", 5)[1]) == ["X-2", "X-3"]


def test_cerca_ignora_gli_accenti():
    assert codici(cerca(CORSI, "forli", 5)[1]) == ["X-1"]
    assert codici(cerca(CORSI, "Forlì", 5)[1]) == ["X-1"]


def test_cerca_piu_parole_devono_comparire_tutte():
    assert codici(cerca(CORSI, "informatica udine", 5)[1]) == ["X-2"]


def test_cerca_totale_e_limite():
    totale, risultati = cerca(CORSI, "udine", 1)
    assert totale == 2 and len(risultati) == 1


def test_cerca_senza_risultati():
    assert cerca(CORSI, "astrofisica", 5) == (0, [])


def test_risultati_senza_durata_e_descrizione():
    _, risultati = cerca(CORSI, "udine", 5)
    assert all(set(r) == {"codice", "titolo", "settore", "sede"} for r in risultati)


def test_cerca_non_cerca_nella_descrizione():
    assert cerca(CORSI, "d1", 5) == (0, [])


def test_trova_ignora_maiuscole_e_spazi():
    assert trova(CORSI, " x-2 ")["titolo"] == "Reti e sicurezza"
    assert trova(CORSI, "X-9") is None


def test_catalogo_fittizio_ben_formato():
    testo = resources.files("assistente.servizi_http").joinpath("dati/catalogo.json").read_text(encoding="utf-8")
    corsi = json.loads(testo)
    assert 8 <= len(corsi) <= 12
    assert len({c["codice"] for c in corsi}) == len(corsi)
    for c in corsi:
        assert set(c) == CAMPI
        assert re.fullmatch(r"ITS-\d{3}", c["codice"])
        assert isinstance(c["durata_ore"], int) and c["durata_ore"] > 0
        assert all(isinstance(c[k], str) and c[k].strip() for k in CAMPI - {"durata_ore"})
    assert carica_catalogo() == corsi
    # gli esempi delle prove reali devono esistere
    assert trova(corsi, "ITS-003") is not None
    assert cerca(corsi, "Udine", 10)[0] >= 3
