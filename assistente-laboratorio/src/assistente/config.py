"""Configurazione letta dalle variabili d'ambiente."""
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass

MAX_PASSAGGI_PREDEFINITO = 6
MCP_URL_PREDEFINITO = "http://localhost:8001/mcp"
MCP_TIMEOUT_PREDEFINITO = 10.0
MCP_ATTESA_AVVIO_PREDEFINITA = 0.0
SERVIZI_BASE_URL_PREDEFINITO = "http://localhost:8000"
SERVIZI_TIMEOUT_PREDEFINITO = 10.0


class ErroreConfigurazione(Exception):
    pass


@dataclass(frozen=True)
class Config:
    base_url: str
    modello: str
    max_passaggi: int
    mcp_url: str = MCP_URL_PREDEFINITO
    mcp_timeout: float = MCP_TIMEOUT_PREDEFINITO
    mcp_attesa_avvio: float = MCP_ATTESA_AVVIO_PREDEFINITA
    servizi_base_url: str = SERVIZI_BASE_URL_PREDEFINITO
    servizi_timeout: float = SERVIZI_TIMEOUT_PREDEFINITO


def _obbligatoria(env: Mapping[str, str], nome: str) -> str:
    valore = env.get(nome, "").strip()
    if not valore:
        raise ErroreConfigurazione(f"Variabile d'ambiente mancante o vuota: {nome}")
    return valore


def _secondi(env: Mapping[str, str], nome: str, predefinito: float, minimo_incluso: bool) -> float:
    """Legge un numero finito di secondi; `minimo_incluso` ammette lo zero."""
    grezzo = env.get(nome, "").strip()
    if not grezzo:
        return predefinito
    try:
        valore = float(grezzo)
    except ValueError:
        valore = math.nan
    valido = math.isfinite(valore) and (valore >= 0 if minimo_incluso else valore > 0)
    if not valido:
        richiesta = "un numero di secondi finito e non negativo" if minimo_incluso else "un numero di secondi finito e positivo"
        raise ErroreConfigurazione(f"{nome} deve essere {richiesta}, ricevuto: {grezzo!r}")
    return valore


def carica_config(env: Mapping[str, str] = os.environ) -> Config:
    base_url = _obbligatoria(env, "LM_STUDIO_BASE_URL")
    modello = _obbligatoria(env, "LM_STUDIO_MODEL")
    grezzo = env.get("MAX_PASSAGGI", "").strip()
    try:
        max_passaggi = int(grezzo) if grezzo else MAX_PASSAGGI_PREDEFINITO
    except ValueError:
        max_passaggi = 0
    if max_passaggi < 1:
        raise ErroreConfigurazione(f"MAX_PASSAGGI deve essere un intero positivo, ricevuto: {grezzo!r}")
    return Config(
        base_url=base_url,
        modello=modello,
        max_passaggi=max_passaggi,
        mcp_url=env.get("MCP_URL", "").strip() or MCP_URL_PREDEFINITO,
        mcp_timeout=_secondi(env, "MCP_TIMEOUT", MCP_TIMEOUT_PREDEFINITO, minimo_incluso=False),
        mcp_attesa_avvio=_secondi(env, "MCP_ATTESA_AVVIO", MCP_ATTESA_AVVIO_PREDEFINITA, minimo_incluso=True),
        servizi_base_url=env.get("SERVIZI_BASE_URL", "").strip() or SERVIZI_BASE_URL_PREDEFINITO,
        servizi_timeout=_secondi(env, "SERVIZI_TIMEOUT", SERVIZI_TIMEOUT_PREDEFINITO, minimo_incluso=False),
    )
