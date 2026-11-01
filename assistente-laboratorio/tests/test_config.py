import pytest

from assistente.config import Config, ErroreConfigurazione, carica_config

BASE = {"LM_STUDIO_BASE_URL": "http://localhost:1234/v1", "LM_STUDIO_MODEL": "google/gemma-4-e2b"}


def test_config_valida():
    assert carica_config({**BASE, "MAX_PASSAGGI": "4"}) == Config(
        base_url="http://localhost:1234/v1", modello="google/gemma-4-e2b", max_passaggi=4
    )


@pytest.mark.parametrize("variabile", ["LM_STUDIO_BASE_URL", "LM_STUDIO_MODEL"])
def test_variabile_mancante_viene_nominata(variabile):
    env = {k: v for k, v in BASE.items() if k != variabile}

    with pytest.raises(ErroreConfigurazione, match=variabile):
        carica_config(env)


@pytest.mark.parametrize("valore", ["", "   "])
def test_valori_vuoti_sono_mancanti(valore):
    with pytest.raises(ErroreConfigurazione, match="LM_STUDIO_MODEL"):
        carica_config({**BASE, "LM_STUDIO_MODEL": valore})


def test_max_passaggi_predefinito_6():
    assert carica_config(BASE).max_passaggi == 6


@pytest.mark.parametrize("valore", ["abc", "0", "-1"])
def test_max_passaggi_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="MAX_PASSAGGI"):
        carica_config({**BASE, "MAX_PASSAGGI": valore})
