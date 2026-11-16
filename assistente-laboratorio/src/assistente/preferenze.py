"""Preferenze dell'utente lette dalla resource MCP `utente://preferenze` (Step 4).

L'host legge la resource una volta all'avvio; il modello non la vede mai come strumento.
I valori predefiniti esistono solo qui: il server MCP non li conosce (spec §7.1).
"""
import json
import logging
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from assistente.config import Config
from assistente.mcp_client import ErroreMcp

LOG = logging.getLogger("assistente.preferenze")

URI_PREFERENZE = "utente://preferenze"
MAX_LINGUA = 40
STILI = ("sintetico", "dettagliato")


@dataclass(frozen=True)
class Preferenze:
    lingua: str
    fuso_orario: str
    stile: str


PREFERENZE_PREDEFINITE = Preferenze(lingua="italiano", fuso_orario="Europe/Rome", stile="sintetico")

# Appendice A della specifica, testo esatto.
BLOCCO_PROMPT = """Preferenze dell'utente (valide per tutta la sessione):
- Rispondi sempre in {lingua}.
- Fuso orario predefinito: {fuso_orario}. Usalo per data e ora quando l'utente non indica un altro fuso.
- Stile: {testo_stile}"""

TESTI_STILE = {
    "sintetico": "risposte brevi ed essenziali, senza dettagli non richiesti.",
    "dettagliato": "risposte complete, con spiegazioni ed esempi quando sono utili.",
}


def testo_prompt(preferenze: Preferenze) -> str:
    return BLOCCO_PROMPT.format(
        lingua=preferenze.lingua, fuso_orario=preferenze.fuso_orario, testo_stile=TESTI_STILE[preferenze.stile]
    )


def _per_log(valore: Any) -> str:
    """Valore non valido da mostrare nei log, troncato a MAX_LINGUA caratteri."""
    testo = repr(valore)
    return testo if len(testo) <= MAX_LINGUA else testo[:MAX_LINGUA] + "…"


def _lingua(valore: Any) -> tuple[str | None, str]:
    if not isinstance(valore, str):
        return None, "non è un testo"
    pulito = valore.strip()
    if not pulito:
        return None, "vuota"
    if len(pulito) > MAX_LINGUA:
        return None, f"più di {MAX_LINGUA} caratteri"
    # Categoria C (controllo, compreso l'a capo) più Zl/Zp: U+2028 e U+2029 sono a capo per `splitlines`.
    if any(unicodedata.category(c).startswith("C") or unicodedata.category(c) in ("Zl", "Zp") for c in pulito):
        return None, "contiene a capo o caratteri di controllo"
    return pulito, ""


def _fuso_orario(valore: Any) -> tuple[str | None, str]:
    if not isinstance(valore, str) or not valore.strip():
        return None, "non è un nome di fuso orario"
    pulito = valore.strip()
    try:
        ZoneInfo(pulito)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return None, "fuso orario IANA sconosciuto"
    return pulito, ""


def _stile(valore: Any) -> tuple[str | None, str]:
    if isinstance(valore, str) and valore.strip().lower() in STILI:
        return valore.strip().lower(), ""
    return None, "ammessi solo " + " o ".join(STILI)


VALIDATORI: dict[str, Callable[[Any], tuple[str | None, str]]] = {
    "lingua": _lingua, "fuso_orario": _fuso_orario, "stile": _stile,
}


def _riepilogo(preferenze: Preferenze, origini: dict[str, str]) -> None:
    parti = [f"{campo}={getattr(preferenze, campo)} ({origini[campo]})" for campo in VALIDATORI]
    LOG.info("preferenze della sessione: %s", ", ".join(parti))


def _tutte_predefinite(causa: str) -> Preferenze:
    LOG.warning("preferenze non disponibili (%s): uso i valori predefiniti", causa)
    _riepilogo(PREFERENZE_PREDEFINITE, dict.fromkeys(VALIDATORI, "predefinito"))
    return PREFERENZE_PREDEFINITE


def interpreta_preferenze(testo: str) -> Preferenze:
    """Testo della resource → preferenze, campo per campo (spec §7.2-7.3). Non solleva eccezioni."""
    try:
        dati = json.loads(testo)
    except (ValueError, TypeError, RecursionError) as errore:  # RecursionError: JSON annidato troppo in profondità
        return _tutte_predefinite(f"testo non JSON: {type(errore).__name__}: {str(errore)[:80]}")
    if not isinstance(dati, dict):
        return _tutte_predefinite(f"il JSON non è un oggetto ma {type(dati).__name__}")
    sconosciute = sorted(str(chiave) for chiave in dati if chiave not in VALIDATORI)
    if sconosciute:
        LOG.warning("chiavi sconosciute ignorate: %s", ", ".join(sconosciute))
    valori, origini = {}, {}
    for campo, valida in VALIDATORI.items():
        predefinito = getattr(PREFERENZE_PREDEFINITE, campo)
        if campo not in dati:
            valore, motivo = None, "mancante"
        else:
            valore, motivo = valida(dati[campo])
            if valore is None:
                motivo = f"{motivo}: {_per_log(dati[campo])}"
        if valore is None:
            LOG.warning("preferenza %s non valida (%s): uso %s", campo, motivo, predefinito)
            valori[campo], origini[campo] = predefinito, "predefinito"
        else:
            valori[campo], origini[campo] = valore, "resource"
    preferenze = Preferenze(**valori)
    _riepilogo(preferenze, origini)
    return preferenze


def carica_preferenze(config: Config, leggi: Callable[[str, str, float], str]) -> Preferenze:
    """Legge la resource una volta (un solo tentativo) e la interpreta; con qualunque errore usa i predefiniti."""
    try:
        testo = leggi(config.mcp_url, URI_PREFERENZE, config.mcp_timeout)
    except ErroreMcp as errore:
        return _tutte_predefinite(str(errore))
    LOG.info("resource %s letta da %s", URI_PREFERENZE, config.mcp_url)
    return interpreta_preferenze(testo)
