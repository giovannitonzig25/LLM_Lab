"""Calcolatrice sicura: valuta espressioni aritmetiche con `ast`, mai con `eval`/`exec`."""

import ast
import math
import operator
from typing import Any

from langchain_core.tools import tool

MAX_CARATTERI = 200
MAX_ESPONENTE = 100
MAX_VALORE = 1e15

_BINARI = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARI = {ast.UAdd: operator.pos, ast.USub: operator.neg}

_AIUTO = "Usa solo numeri (punto come separatore decimale), + - * / ** (potenza) e parentesi."


class _Rifiutata(Exception):
    """Espressione non valutabile; il messaggio è già leggibile."""


def _controlla(valore: Any) -> Any:
    """Ogni numero, letterale o intermedio, deve essere reale, finito e entro il limite."""
    if isinstance(valore, bool) or not isinstance(valore, (int, float)):
        raise _Rifiutata("il risultato non è un numero reale")
    if isinstance(valore, float) and not math.isfinite(valore):
        raise _Rifiutata("il risultato non è finito")
    if abs(valore) > MAX_VALORE:
        raise _Rifiutata(f"numero troppo grande (il limite è {MAX_VALORE:.0e})")
    return valore


def _valuta_nodo(nodo: ast.AST) -> Any:
    if isinstance(nodo, ast.Expression):
        return _valuta_nodo(nodo.body)
    if isinstance(nodo, ast.Constant):
        if isinstance(nodo.value, bool) or not isinstance(nodo.value, (int, float)):
            raise _Rifiutata(f"valore non ammesso: {nodo.value!r}. {_AIUTO}")
        return _controlla(nodo.value)
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in _UNARI:
        return _controlla(_UNARI[type(nodo.op)](_valuta_nodo(nodo.operand)))
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in _BINARI:
        sinistra, destra = _valuta_nodo(nodo.left), _valuta_nodo(nodo.right)
        if isinstance(nodo.op, ast.Pow) and abs(destra) > MAX_ESPONENTE:
            raise _Rifiutata(f"esponente troppo grande (al massimo {MAX_ESPONENTE})")
        try:
            return _controlla(_BINARI[type(nodo.op)](sinistra, destra))
        except ZeroDivisionError:
            raise _Rifiutata("divisione per zero") from None
        except OverflowError:
            raise _Rifiutata("il risultato è troppo grande") from None
    if isinstance(nodo, ast.Name):
        raise _Rifiutata(f"nome non ammesso: {nodo.id!r}. {_AIUTO}")
    if isinstance(nodo, ast.Call):
        raise _Rifiutata(f"le funzioni non sono ammesse. {_AIUTO}")
    raise _Rifiutata(f"elemento non ammesso nell'espressione. {_AIUTO}")


def _formatta(numero: Any) -> str:
    if isinstance(numero, int):
        return str(numero)
    if numero == 0:
        return "0"
    if numero.is_integer():
        return str(int(numero))
    return f"{numero:.10g}"


def valuta(espressione: Any) -> str:
    """Valuta un'espressione aritmetica. Non solleva eccezioni: un problema dà un testo `Errore: ...`."""
    if not isinstance(espressione, str):
        return f"Errore: l'espressione deve essere un testo. {_AIUTO}"
    testo = espressione.strip()
    if not testo:
        return f"Errore: espressione vuota. {_AIUTO}"
    if len(espressione) > MAX_CARATTERI:
        return f"Errore: espressione troppo lunga ({len(espressione)} caratteri, al massimo {MAX_CARATTERI})"
    try:
        albero = ast.parse(testo, mode="eval")
        return _formatta(_valuta_nodo(albero))
    except _Rifiutata as errore:
        return f"Errore: {errore}"
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return f"Errore: espressione non valida. {_AIUTO}"


@tool
def calcola(espressione: str) -> str:
    """Calcola il risultato di un'espressione aritmetica. Usalo per ogni calcolo, senza farlo a mente. Ammessi numeri (punto decimale), + - * / ** (potenza) e parentesi, al massimo 200 caratteri; non serve per convertire unità di misura. Esempio: "quanto fa 17 per 23 più 5?" → espressione="17*23+5"."""
    return valuta(espressione)


def _errore_argomenti(errore: Exception) -> str:
    return "Errore: argomenti non validi per calcola: serve espressione (un testo, per esempio '17*23+5')."


calcola.handle_validation_error = _errore_argomenti
