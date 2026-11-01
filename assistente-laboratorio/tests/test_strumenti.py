from datetime import UTC, datetime

import pytest

from assistente.strumenti import STRUMENTI, leggi_orologio, orologio

ISTANTE = datetime(2026, 11, 1, 14, 4, 5, tzinfo=UTC)


def adesso():
    return ISTANTE


def test_roma():
    risultato = leggi_orologio("Europe/Rome", adesso)

    assert "2026-11-01 15:04:05" in risultato
    assert "Europe/Rome" in risultato
    assert "+01:00" in risultato


def test_tokyo():
    risultato = leggi_orologio("Asia/Tokyo", adesso)

    assert "2026-11-01 23:04:05" in risultato
    assert "Asia/Tokyo" in risultato
    assert "+09:00" in risultato


@pytest.mark.parametrize("valore", [None, "", "   "])
def test_predefinito_e_roma(valore):
    assert "Europe/Rome" in leggi_orologio(valore, adesso)


@pytest.mark.parametrize("valore", ["Mars/Base", "../etc", "Europe/../Rome", 42])
def test_fuso_non_valido_da_errore_chiaro(valore):
    risultato = leggi_orologio(valore, adesso)

    assert risultato.startswith("Errore:")
    assert str(valore) in risultato


def test_orologio_ha_schema_con_timezone():
    assert "timezone" in orologio.args
    assert orologio.name == "orologio"
    assert STRUMENTI == [orologio]


def test_orologio_accetta_timezone_nullo():
    assert "Europe/Rome" in orologio.invoke({"timezone": None})
