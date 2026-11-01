"""Configurazione letta dalle variabili d'ambiente."""
import os
from collections.abc import Mapping
from dataclasses import dataclass

MAX_PASSAGGI_PREDEFINITO = 6


class ErroreConfigurazione(Exception):
    pass


@dataclass(frozen=True)
class Config:
    base_url: str
    modello: str
    max_passaggi: int


def _obbligatoria(env: Mapping[str, str], nome: str) -> str:
    valore = env.get(nome, "").strip()
    if not valore:
        raise ErroreConfigurazione(f"Variabile d'ambiente mancante o vuota: {nome}")
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
    return Config(base_url=base_url, modello=modello, max_passaggi=max_passaggi)
