"""Preferenze dell'utente (Step 4): validazione campo per campo, caricamento con fallback, testo del prompt."""
import json
import logging
from pathlib import Path

import pytest

import assistente.preferenze as modulo_preferenze
from assistente import strumenti
from assistente.config import carica_config
from assistente.mcp_client import ErroreMcp
from assistente.preferenze import (
    PREFERENZE_PREDEFINITE, URI_PREFERENZE, Preferenze, carica_preferenze, interpreta_preferenze,
)

SPECIFICA = Path(__file__).resolve().parents[1] / "docs" / "superpowers" / "specs" / "2026-11-16-preferenze-design.md"
LOGGER = "assistente.preferenze"
VALIDE = {"lingua": "inglese", "fuso_orario": "America/New_York", "stile": "dettagliato"}
CONFIG = carica_config({"LM_STUDIO_BASE_URL": "http://localhost:1234/v1", "LM_STUDIO_MODEL": "m", "AMBITO_AGENTE": "a"})


def appendice_a() -> tuple[str, dict[str, str]]:
    """Blocco del prompt e testi dello stile, letti dall'Appendice A della specifica."""
    testo = SPECIFICA.read_text(encoding="utf-8")
    dopo = testo[testo.index("## Appendice A"):]
    inizio = dopo.index("```\n") + len("```\n")
    blocco = dopo[inizio: dopo.index("\n```", inizio)]
    stili = {}
    for stile in ("sintetico", "dettagliato"):
        riga = dopo[dopo.index(f"- `{stile}` → `") + len(f"- `{stile}` → `"):]
        stili[stile] = riga[: riga.index("`")]
    return blocco, stili


def avvisi(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == LOGGER and r.levelno == logging.WARNING]


def riga_finale(caplog) -> str:
    righe = [r.getMessage() for r in caplog.records if r.name == LOGGER and r.levelno == logging.INFO]
    return [r for r in righe if r.startswith("preferenze della sessione")][-1]


def interpreta(dati, caplog) -> Preferenze:
    with caplog.at_level(logging.INFO, logger=LOGGER):
        return interpreta_preferenze(json.dumps(dati))


def test_file_valido_usa_i_tre_valori(caplog):
    assert interpreta(VALIDE, caplog) == Preferenze("inglese", "America/New_York", "dettagliato")
    assert riga_finale(caplog) == (
        "preferenze della sessione: lingua=inglese (resource), fuso_orario=America/New_York (resource), "
        "stile=dettagliato (resource)"
    )
    assert avvisi(caplog) == []


ASSENTE = object()


@pytest.mark.parametrize(
    "campo, valore",
    [
        *[("lingua", v) for v in ("", "   ", "x" * 41, "ita\nliano", 5, None, ASSENTE)],
        *[("fuso_orario", v) for v in ("Marte/Olympus", "", "../x", 3, ASSENTE)],
        *[("stile", v) for v in ("dettagliatissimo", None, ["sintetico"], ASSENTE)],
    ],
)
def test_campo_non_valido_usa_il_predefinito_solo_per_quel_campo(campo, valore, caplog):
    dati = dict(VALIDE)
    if valore is ASSENTE:
        del dati[campo]
    else:
        dati[campo] = valore

    risultato = interpreta(dati, caplog)

    for nome in VALIDE:
        atteso = getattr(PREFERENZE_PREDEFINITE, nome) if nome == campo else VALIDE[nome]
        assert getattr(risultato, nome) == atteso
    assert any(campo in a for a in avvisi(caplog))
    assert f"{campo}={getattr(PREFERENZE_PREDEFINITE, campo)} (predefinito)" in riga_finale(caplog)


def test_lingua_non_ascii_accettata(caplog):
    assert interpreta({**VALIDE, "lingua": "français"}, caplog).lingua == "français"
    assert avvisi(caplog) == []


def test_lingua_lunga_troncata_nel_log(caplog):
    interpreta({**VALIDE, "lingua": "x" * 200}, caplog)

    assert avvisi(caplog)
    assert not any("x" * 41 in r.getMessage() for r in caplog.records)


def test_stile_normalizzato(caplog):
    assert interpreta({**VALIDE, "stile": "Dettagliato"}, caplog).stile == "dettagliato"
    assert interpreta({**VALIDE, "stile": " SINTETICO "}, caplog).stile == "sintetico"


def test_valori_con_spazi_ripuliti(caplog):
    risultato = interpreta({**VALIDE, "lingua": " inglese ", "fuso_orario": " Asia/Tokyo "}, caplog)

    assert (risultato.lingua, risultato.fuso_orario) == ("inglese", "Asia/Tokyo")


def test_chiavi_sconosciute_ignorate_con_warning(caplog):
    risultato = interpreta({"lingua": "inglese", "fuso": "Asia/Tokyo", "stile": "sintetico"}, caplog)

    assert risultato.fuso_orario == PREFERENZE_PREDEFINITE.fuso_orario
    assert any("fuso" in a and "fuso_orario" not in a for a in avvisi(caplog))


@pytest.mark.parametrize("testo", ["non è json {", "[1, 2]", '"testo"', "null"])
def test_testo_non_oggetto_usa_tutti_i_predefiniti(testo, caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        risultato = interpreta_preferenze(testo)

    assert risultato == PREFERENZE_PREDEFINITE
    assert avvisi(caplog)
    assert riga_finale(caplog).count("(predefinito)") == 3


def test_carica_con_errore_mcp_usa_i_predefiniti(caplog):
    def leggi(url, uri, timeout):
        raise ErroreMcp("discovery impossibile su http://x/mcp: connessione rifiutata")

    with caplog.at_level(logging.INFO, logger=LOGGER):
        risultato = carica_preferenze(CONFIG, leggi)

    assert risultato == PREFERENZE_PREDEFINITE
    assert any("connessione rifiutata" in a for a in avvisi(caplog))
    assert riga_finale(caplog).count("(predefinito)") == 3


def test_carica_passa_url_uri_e_timeout():
    chiamate = []

    def leggi(url, uri, timeout):
        chiamate.append((url, uri, timeout))
        return json.dumps(VALIDE)

    assert carica_preferenze(CONFIG, leggi) == Preferenze("inglese", "America/New_York", "dettagliato")
    assert chiamate == [(CONFIG.mcp_url, "utente://preferenze", CONFIG.mcp_timeout)]
    assert URI_PREFERENZE == "utente://preferenze"


def test_carica_riuscita_scrive_info_di_lettura(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        carica_preferenze(CONFIG, lambda url, uri, timeout: json.dumps(VALIDE))

    info = [r.getMessage() for r in caplog.records if r.name == LOGGER and r.levelno == logging.INFO]
    assert any("utente://preferenze" in r and CONFIG.mcp_url in r for r in info)


@pytest.mark.parametrize("stile", ["sintetico", "dettagliato"])
def test_testo_prompt(stile):
    blocco, stili = appendice_a()
    preferenze = Preferenze("inglese", "America/New_York", stile)

    atteso = blocco.format(lingua="inglese", fuso_orario="America/New_York", testo_stile=stili[stile])
    assert modulo_preferenze.testo_prompt(preferenze) == atteso


def test_valori_predefiniti_e_limite():
    assert PREFERENZE_PREDEFINITE == Preferenze("italiano", "Europe/Rome", "sintetico")
    assert modulo_preferenze.MAX_LINGUA == 40


def test_fuso_predefinito_dell_orologio_viene_dalle_preferenze():
    assert strumenti.FUSO_PREDEFINITO == PREFERENZE_PREDEFINITE.fuso_orario == "Europe/Rome"
