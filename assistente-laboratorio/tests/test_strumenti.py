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
    assert orologio in STRUMENTI
    assert [s.name for s in STRUMENTI] == ["orologio", "converti_unita", "calcola"]


def test_orologio_accetta_timezone_nullo():
    assert "Europe/Rome" in orologio.invoke({"timezone": None})


# --- composizione all'avvio (locali + MCP) ---
from langchain_core.tools import tool

from assistente.config import carica_config
from assistente.mcp_client import ErroreMcp
from assistente.strumenti import componi_strumenti

_ENV = {"LM_STUDIO_BASE_URL": "http://localhost:1234/v1", "LM_STUDIO_MODEL": "m"}


@tool
def strumento_mcp_finto(x: str) -> str:
    """Strumento MCP finto."""
    return x


NOMI_LOCALI = ["orologio", "converti_unita", "calcola"]
NOMI_HTTP = ["giorni_lavorativi", "calcola_scadenza"]


def nomi(strumenti):
    return [s.name for s in strumenti]


class Orologio:
    """Tempo simulato: `dormi` avanza `adesso`, nessuna attesa reale."""

    def __init__(self):
        self.t = 0.0

    def adesso(self):
        return self.t

    def dormi(self, secondi):
        self.t += secondi


def config_con(**extra):
    return carica_config({**_ENV, **extra})


def test_compone_locali_piu_mcp():
    strumenti, avvisi = componi_strumenti(
        config_con(), scopri=lambda url, timeout, chiedi_conferma=None: [strumento_mcp_finto]
    )

    assert nomi(strumenti) == [*NOMI_LOCALI, *NOMI_HTTP, "strumento_mcp_finto"]
    assert avvisi == []


def test_avvio_ridotto_con_avviso():
    def scopri(url, timeout, chiedi_conferma=None):
        raise ErroreMcp("giù")

    strumenti, avvisi = componi_strumenti(config_con(MCP_URL="http://x:1/mcp"), scopri=scopri)

    assert nomi(strumenti) == [*NOMI_LOCALI, *NOMI_HTTP]
    assert len(avvisi) == 1
    assert "http://x:1/mcp" in avvisi[0]
    assert "Riavvia l'agente quando il server è attivo" in avvisi[0]
    assert "aggiungi_nota" not in avvisi[0]


def test_attesa_all_avvio_server_in_ritardo():
    orologio_finto = Orologio()
    tentativi = []

    def scopri(url, timeout, chiedi_conferma=None):
        tentativi.append(orologio_finto.t)
        if len(tentativi) < 3:
            raise ErroreMcp("non ancora")
        return [strumento_mcp_finto]

    strumenti, avvisi = componi_strumenti(
        config_con(MCP_ATTESA_AVVIO="20"), scopri=scopri,
        dormi=orologio_finto.dormi, adesso=orologio_finto.adesso,
    )

    assert nomi(strumenti) == [*NOMI_LOCALI, *NOMI_HTTP, "strumento_mcp_finto"]
    assert avvisi == []
    assert tentativi == [0.0, 1.0, 2.0]


def test_attesa_scaduta():
    orologio_finto = Orologio()
    tentativi = []

    def scopri(url, timeout, chiedi_conferma=None):
        tentativi.append(1)
        raise ErroreMcp("giù")

    strumenti, avvisi = componi_strumenti(
        config_con(MCP_ATTESA_AVVIO="3"), scopri=scopri,
        dormi=orologio_finto.dormi, adesso=orologio_finto.adesso,
    )

    assert nomi(strumenti) == [*NOMI_LOCALI, *NOMI_HTTP]
    assert len(avvisi) == 1
    assert orologio_finto.t == 3.0
    assert len(tentativi) == 4


def test_con_attesa_zero_un_solo_tentativo():
    tentativi = []

    def scopri(url, timeout, chiedi_conferma=None):
        tentativi.append(1)
        raise ErroreMcp("giù")

    def dormi(secondi):
        raise AssertionError("con attesa 0 non si deve attendere")

    componi_strumenti(config_con(MCP_ATTESA_AVVIO="0"), scopri=scopri, dormi=dormi)

    assert len(tentativi) == 1


def test_scopri_riceve_url_e_timeout_della_config():
    visti = []

    def scopri(url, timeout, chiedi_conferma=None):
        visti.append((url, timeout))
        return []

    componi_strumenti(config_con(MCP_URL="http://h:9/mcp", MCP_TIMEOUT="3"), scopri=scopri)

    assert visti == [("http://h:9/mcp", 3.0)]


def test_chiedi_conferma_viene_inoltrata_alla_discovery():
    viste = []

    def scopri(url, timeout, chiedi_conferma=None):
        viste.append(chiedi_conferma)
        return []

    def conferma(messaggio):
        return True

    componi_strumenti(config_con(), scopri=scopri, chiedi_conferma=conferma)
    componi_strumenti(config_con(), scopri=scopri)

    assert viste == [conferma, None]
