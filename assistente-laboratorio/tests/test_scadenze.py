from datetime import date

import pytest

from assistente.servizi_http.scadenze import calcola_scadenza, giorni_lavorativi

NESSUNA = set()
NATALE = {date(2026, 12, 25), date(2026, 12, 26)}


def test_settimana_piena_vale_cinque():
    assert giorni_lavorativi(date(2026, 11, 2), date(2026, 11, 6), NESSUNA) == 5


def test_weekend_e_festivita_non_contano():
    # 1/11/2026 è domenica e festivo, 2/11 è lunedì
    assert giorni_lavorativi(date(2026, 11, 1), date(2026, 11, 2), {date(2026, 11, 1)}) == 1


def test_festivita_infrasettimanale_esclusa():
    assert giorni_lavorativi(date(2026, 12, 24), date(2026, 12, 28), NATALE) == 2


def test_stesso_giorno_lavorativo_e_festivo():
    assert giorni_lavorativi(date(2026, 11, 2), date(2026, 11, 2), NESSUNA) == 1
    assert giorni_lavorativi(date(2026, 11, 1), date(2026, 11, 1), NESSUNA) == 0
    assert giorni_lavorativi(date(2026, 11, 2), date(2026, 11, 2), {date(2026, 11, 2)}) == 0


def test_intervallo_invertito_solleva():
    with pytest.raises(ValueError):
        giorni_lavorativi(date(2026, 11, 6), date(2026, 11, 2), NESSUNA)


def test_scadenza_salta_festivi_e_weekend():
    assert calcola_scadenza(date(2026, 12, 24), 1, NATALE) == date(2026, 12, 28)


def test_scadenza_il_giorno_di_partenza_non_conta():
    # lunedì 9/11/2026 + 10 giorni lavorativi = lunedì 23/11
    assert calcola_scadenza(date(2026, 11, 9), 10, NESSUNA) == date(2026, 11, 23)


def test_scadenza_da_giorno_festivo():
    # sabato 7/11 + 1 giorno lavorativo = lunedì 9/11
    assert calcola_scadenza(date(2026, 11, 7), 1, NESSUNA) == date(2026, 11, 9)


def test_scadenza_giorni_non_positivi_solleva():
    with pytest.raises(ValueError):
        calcola_scadenza(date(2026, 11, 9), 0, NESSUNA)
