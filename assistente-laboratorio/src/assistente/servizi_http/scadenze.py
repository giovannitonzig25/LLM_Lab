"""Calcoli sui giorni lavorativi: funzioni pure, senza I/O."""
from datetime import date, timedelta


def _lavorativo(giorno: date, festivita: set[date]) -> bool:
    return giorno.weekday() < 5 and giorno not in festivita


def giorni_lavorativi(da: date, a: date, festivita: set[date]) -> int:
    """Conta i giorni lavorativi tra `da` e `a`, estremi inclusi."""
    if a < da:
        raise ValueError("la data finale precede la data iniziale")
    totale = (a - da).days + 1
    return sum(1 for i in range(totale) if _lavorativo(da + timedelta(days=i), festivita))


def calcola_scadenza(da: date, giorni: int, festivita: set[date]) -> date:
    """N-esimo giorno lavorativo successivo a `da` (il giorno di partenza non conta)."""
    if giorni < 1:
        raise ValueError("i giorni devono essere almeno 1")
    corrente = da
    contati = 0
    while contati < giorni:
        corrente += timedelta(days=1)
        if _lavorativo(corrente, festivita):
            contati += 1
    return corrente
