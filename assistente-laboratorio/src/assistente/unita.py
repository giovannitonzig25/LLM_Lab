"""Conversione di unità di misura (elenco chiuso), come strumento locale per il modello."""

import math
from typing import Any

from langchain_core.tools import tool

# Fattore di ciascuna unità verso l'unità base della categoria (m, g, l).
_FATTORI = {
    "lunghezza": {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0, "in": 0.0254, "ft": 0.3048, "mi": 1609.344},
    "massa": {"g": 1.0, "kg": 1000.0, "lb": 453.59237, "oz": 28.349523125},
    "volume": {"ml": 0.001, "l": 1.0, "gal": 3.785411784},  # gal USA
}
_TEMPERATURE = ("C", "F", "K")

UNITA_AMMESSE = {categoria: list(unita) for categoria, unita in _FATTORI.items()}
UNITA_AMMESSE["temperatura"] = list(_TEMPERATURE)

# Nome scritto dall'utente (senza maiuscole né «°») → (categoria, simbolo canonico).
_RICONOSCIUTE = {
    simbolo.lower(): (categoria, simbolo)
    for categoria, simboli in UNITA_AMMESSE.items()
    for simbolo in simboli
}

_ELENCO = "; ".join(f"{categoria}: {', '.join(unita)}" for categoria, unita in UNITA_AMMESSE.items())


def _errore(messaggio: str) -> str:
    return f"Errore: {messaggio}. Unità ammesse - {_ELENCO}."


def _cerca(unita: Any) -> tuple[str, str] | None:
    if not isinstance(unita, str):
        return None
    return _RICONOSCIUTE.get(unita.strip().lstrip("°").strip().lower())


def _numero(valore: Any) -> float:
    """Converte il valore in un float finito, oppure solleva ValueError con un testo chiaro."""
    if isinstance(valore, bool) or valore is None:
        raise ValueError(f"valore non numerico: {valore!r}")
    if isinstance(valore, str):
        grezzo = valore.strip()
        try:
            numero = float(grezzo)
        except ValueError:
            raise ValueError(
                f"valore non numerico: {valore!r} (usa un numero, con il punto come separatore decimale)"
            ) from None
    elif isinstance(valore, (int, float)):
        numero = float(valore)
    else:
        raise ValueError(f"valore non numerico: {valore!r}")
    if not math.isfinite(numero):
        raise ValueError(f"valore non finito: {valore!r}")
    return numero


def _a_kelvin(valore: float, unita: str) -> float:
    return {"C": valore + 273.15, "F": (valore - 32) * 5 / 9 + 273.15, "K": valore}[unita]


def _da_kelvin(kelvin: float, unita: str) -> float:
    return {"C": kelvin - 273.15, "F": (kelvin - 273.15) * 9 / 5 + 32, "K": kelvin}[unita]


def _formatta(x: float) -> str:
    if x == 0:
        return "0"
    if 1e-3 <= abs(x) < 1e12:
        testo = f"{x:.4f}".rstrip("0").rstrip(".")
        return "0" if testo in ("", "-0") else testo
    return f"{x:.6g}"


def converti(valore: Any, da: Any, a: Any) -> str:
    """Converte `valore` da `da` ad `a`. Non solleva eccezioni: un problema dà un testo `Errore: ...`."""
    origine, destinazione = _cerca(da), _cerca(a)
    for scritta, trovata in ((da, origine), (a, destinazione)):
        if trovata is None:
            return _errore(f"unità non riconosciuta: {scritta!r}")
    (categoria_da, simbolo_da), (categoria_a, simbolo_a) = origine, destinazione
    if categoria_da != categoria_a:
        return _errore(
            f"unità incompatibili: {simbolo_da} è {categoria_da}, {simbolo_a} è {categoria_a}"
        )
    try:
        numero = _numero(valore)
    except ValueError as errore:
        return f"Errore: {errore}"

    if categoria_da == "temperatura":
        kelvin = _a_kelvin(numero, simbolo_da)
        if kelvin < -1e-9:
            return f"Errore: temperatura sotto lo zero assoluto: {_formatta(numero)} {simbolo_da}"
        risultato = _da_kelvin(max(kelvin, 0.0), simbolo_a)
    else:
        fattori = _FATTORI[categoria_da]
        risultato = numero * fattori[simbolo_da] / fattori[simbolo_a]
    if not math.isfinite(risultato):
        return "Errore: il risultato è troppo grande per essere rappresentato"
    return f"{_formatta(numero)} {simbolo_da} = {_formatta(risultato)} {simbolo_a}"


@tool
def converti_unita(valore: float | str, da: str, a: str) -> str:
    """Converte un valore da un'unità di misura a un'altra. Unità ammesse: lunghezza mm, cm, m, km, in (pollici), ft (piedi), mi (miglia); massa g, kg, lb (libbre), oz (once); volume ml, l, gal (galloni USA); temperatura C, F, K. Esempio: "quanti chilometri sono 10 miglia?" → valore=10, da="mi", a="km"."""
    return converti(valore, da, a)
