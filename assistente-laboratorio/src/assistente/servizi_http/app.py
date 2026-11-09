"""API FastAPI: giorni lavorativi e scadenze (festività nazionali italiane 2026-2027)."""
import json
from datetime import date
from importlib import resources

from fastapi import FastAPI, HTTPException

from .catalogo import carica_catalogo, cerca, trova
from .scadenze import calcola_scadenza, giorni_lavorativi

ANNO_MIN, ANNO_MAX = 2026, 2027
GIORNI_MIN, GIORNI_MAX = 1, 365
Q_MAX_CARATTERI = 100
RISULTATI_MIN, RISULTATI_MAX, RISULTATI_PREDEFINITI = 1, 10, 5
NOTA_CATALOGO = "Catalogo di esempio: i corsi sono fittizi."
NOTA = "Calcolo indicativo: le festività sono quelle nazionali italiane e il risultato non è normativo."


def carica_festivita() -> set[date]:
    testo = resources.files(__package__).joinpath("dati/festivita.json").read_text(encoding="utf-8")
    return {date.fromisoformat(d) for d in json.loads(testo)}


def _errore(messaggio: str) -> HTTPException:
    return HTTPException(status_code=422, detail=messaggio)


def _data(valore: str | None, nome: str) -> date:
    if valore is None or not valore.strip():
        raise _errore(f"Parametro '{nome}' mancante: serve una data nel formato AAAA-MM-GG.")
    try:
        giorno = date.fromisoformat(valore.strip())
    except ValueError:
        raise _errore(f"Parametro '{nome}' non valido: {valore!r} non è una data AAAA-MM-GG esistente.") from None
    if not ANNO_MIN <= giorno.year <= ANNO_MAX:
        raise _errore(f"Parametro '{nome}' fuori dagli anni coperti: sono ammessi solo il {ANNO_MIN} e il {ANNO_MAX}.")
    return giorno


def crea_app() -> FastAPI:
    app = FastAPI(title="Servizi date e scadenze")
    festivita = carica_festivita()
    corsi = carica_catalogo()

    @app.get("/salute")
    def salute() -> dict:
        return {"stato": "ok"}

    @app.get("/giorni-lavorativi")
    def giorni(da: str | None = None, a: str | None = None) -> dict:
        inizio, fine = _data(da, "da"), _data(a, "a")
        if fine < inizio:
            raise _errore("La data finale 'a' precede la data iniziale 'da'.")
        return {
            "da": inizio.isoformat(),
            "a": fine.isoformat(),
            "giorni_lavorativi": giorni_lavorativi(inizio, fine, festivita),
            "nota": NOTA,
        }

    @app.get("/scadenza")
    def scadenza(da: str | None = None, giorni: str | None = None) -> dict:
        inizio = _data(da, "da")
        try:
            n = int((giorni or "").strip())
        except ValueError:
            raise _errore(f"Parametro 'giorni' non valido: serve un intero tra {GIORNI_MIN} e {GIORNI_MAX}.") from None
        if not GIORNI_MIN <= n <= GIORNI_MAX:
            raise _errore(f"Parametro 'giorni' fuori intervallo: sono ammessi da {GIORNI_MIN} a {GIORNI_MAX}.")
        risultato = calcola_scadenza(inizio, n, festivita)
        if risultato.year > ANNO_MAX:
            raise _errore(f"La scadenza uscirebbe dagli anni coperti (fino al 31/12/{ANNO_MAX}): festività non note.")
        return {"da": inizio.isoformat(), "giorni": n, "data_scadenza": risultato.isoformat(), "nota": NOTA}

    @app.get("/catalogo")
    def catalogo(q: str | None = None, max_risultati: str | None = None) -> dict:
        testo = (q or "").strip()
        if not testo:
            raise _errore("Parametro 'q' mancante: serve una parola chiave (titolo, settore o sede).")
        if len(testo) > Q_MAX_CARATTERI:
            raise _errore(f"Parametro 'q' troppo lungo: al massimo {Q_MAX_CARATTERI} caratteri.")
        massimo = RISULTATI_PREDEFINITI
        if max_risultati is not None:
            try:
                massimo = int(max_risultati.strip())
            except ValueError:
                raise _errore(
                    f"Parametro 'max_risultati' non valido: serve un intero tra {RISULTATI_MIN} e {RISULTATI_MAX}."
                ) from None
        if not RISULTATI_MIN <= massimo <= RISULTATI_MAX:
            raise _errore(f"Parametro 'max_risultati' fuori intervallo: sono ammessi da {RISULTATI_MIN} a {RISULTATI_MAX}.")
        totale, risultati = cerca(corsi, testo, massimo)
        return {"totale": totale, "risultati": risultati, "nota": NOTA_CATALOGO}

    @app.get("/catalogo/{codice}")
    def dettaglio(codice: str) -> dict:
        corso = trova(corsi, codice)
        if corso is None:
            raise HTTPException(status_code=404, detail=f"Corso {codice} non trovato.")
        return {**corso, "nota": NOTA_CATALOGO}

    return app
