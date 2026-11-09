"""Catalogo di corsi FITTIZI: ricerca e dettaglio, funzioni pure sopra una lista di dizionari."""
import json
import unicodedata
from importlib import resources

CAMPI_RISULTATO = ("codice", "titolo", "settore", "sede")


def carica_catalogo() -> list[dict]:
    testo = resources.files(__package__).joinpath("dati/catalogo.json").read_text(encoding="utf-8")
    return json.loads(testo)


def _normalizza(testo: str) -> str:
    """Minuscolo e senza accenti: «Forlì» e «forli» coincidono."""
    scomposto = unicodedata.normalize("NFKD", testo.casefold())
    return "".join(c for c in scomposto if not unicodedata.combining(c))


def cerca(corsi: list[dict], testo: str, massimo: int) -> tuple[int, list[dict]]:
    """Corsi i cui titolo, settore e sede contengono tutte le parole di `testo`.
    Restituisce (totale dei corrispondenti, primi `massimo` con i soli campi di sintesi)."""
    parole = _normalizza(testo).split()
    trovati = [
        c for c in corsi
        if parole and all(p in _normalizza(f"{c['titolo']} {c['settore']} {c['sede']}") for p in parole)
    ]
    return len(trovati), [{k: c[k] for k in CAMPI_RISULTATO} for c in trovati[:massimo]]


def trova(corsi: list[dict], codice: str) -> dict | None:
    cercato = codice.strip().upper()
    return next((c for c in corsi if c["codice"].upper() == cercato), None)
