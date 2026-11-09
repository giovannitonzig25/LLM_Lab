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


def test_variabili_mcp_assenti_usano_i_predefiniti():
    config = carica_config(BASE)

    assert config.mcp_url == "http://localhost:8001/mcp"
    assert config.mcp_timeout == 10.0
    assert config.mcp_attesa_avvio == 0.0


def test_variabili_mcp_valide():
    config = carica_config(
        {**BASE, "MCP_URL": "http://server-mcp:8001/mcp", "MCP_TIMEOUT": "2.5", "MCP_ATTESA_AVVIO": "20"}
    )

    assert (config.mcp_url, config.mcp_timeout, config.mcp_attesa_avvio) == (
        "http://server-mcp:8001/mcp", 2.5, 20.0,
    )


@pytest.mark.parametrize("valore", ["abc", "0", "-1", "nan", "inf"])
def test_mcp_timeout_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="MCP_TIMEOUT"):
        carica_config({**BASE, "MCP_TIMEOUT": valore})


@pytest.mark.parametrize("valore", ["abc", "-1", "nan", "inf"])
def test_mcp_attesa_avvio_non_valida(valore):
    with pytest.raises(ErroreConfigurazione, match="MCP_ATTESA_AVVIO"):
        carica_config({**BASE, "MCP_ATTESA_AVVIO": valore})


def test_mcp_attesa_avvio_zero_e_valida():
    assert carica_config({**BASE, "MCP_ATTESA_AVVIO": "0"}).mcp_attesa_avvio == 0.0


def test_variabili_servizi_predefiniti_e_valide():
    config = carica_config(BASE)
    assert (config.servizi_base_url, config.servizi_timeout) == ("http://localhost:8000", 10.0)
    config = carica_config({**BASE, "SERVIZI_BASE_URL": "http://servizi-http:8000", "SERVIZI_TIMEOUT": "2.5"})
    assert (config.servizi_base_url, config.servizi_timeout) == ("http://servizi-http:8000", 2.5)


@pytest.mark.parametrize("valore", ["abc", "0", "-1", "nan", "inf"])
def test_servizi_timeout_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="SERVIZI_TIMEOUT"):
        carica_config({**BASE, "SERVIZI_TIMEOUT": valore})
