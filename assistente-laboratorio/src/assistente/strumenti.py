"""Strumenti che il modello può chiedere al programma di eseguire."""
from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool

FUSO_PREDEFINITO = "Europe/Rome"


def adesso_utc() -> datetime:
    return datetime.now(UTC)


def _formatta_offset(istante: datetime) -> str:
    minuti = int(istante.utcoffset().total_seconds() // 60)
    segno = "+" if minuti >= 0 else "-"
    ore, resto = divmod(abs(minuti), 60)
    return f"UTC{segno}{ore:02d}:{resto:02d}"


def leggi_orologio(timezone: str | None = None, adesso: Callable[[], datetime] = adesso_utc) -> str:
    """Data e ora correnti nel fuso indicato. Non solleva eccezioni: un fuso non valido dà un testo `Errore: ...`."""
    if timezone is None or (isinstance(timezone, str) and not timezone.strip()):
        timezone = FUSO_PREDEFINITO
    try:
        fuso = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return f"Errore: fuso orario non valido: {timezone!r}. Usa un nome IANA, per esempio Europe/Rome o Asia/Tokyo."
    istante = adesso().astimezone(fuso)
    return f"{istante:%Y-%m-%d %H:%M:%S} ({timezone}, {_formatta_offset(istante)})"


@tool
def orologio(timezone: str | None = FUSO_PREDEFINITO) -> str:
    """Restituisce la data e l'ora correnti. `timezone` è un fuso orario IANA (per esempio Europe/Rome, Asia/Tokyo); se omesso si usa Europe/Rome."""
    return leggi_orologio(timezone)


STRUMENTI = [orologio]
