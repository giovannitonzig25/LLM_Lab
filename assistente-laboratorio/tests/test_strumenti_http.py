import httpx
import pytest

from assistente.strumenti_http import crea_strumenti_http

BASE = "http://servizi:8000"


def costruisci(gestore, timeout=3.0):
    richieste = []

    def con_registro(richiesta):
        richieste.append(richiesta)
        return gestore(richiesta)

    client = httpx.Client(transport=httpx.MockTransport(con_registro))
    strumenti = {t.name: t for t in crea_strumenti_http(BASE, timeout, client=client)}
    return strumenti, richieste


def risposta_giorni(richiesta):
    return httpx.Response(200, json={
        "da": "2026-11-02", "a": "2026-11-20", "giorni_lavorativi": 15, "nota": "Risultato non normativo."})


def test_nomi_e_descrizioni():
    strumenti, _ = costruisci(risposta_giorni)
    assert set(strumenti) == {"giorni_lavorativi", "calcola_scadenza", "cerca_catalogo", "dettaglio_catalogo"}
    assert "ora attuale" in strumenti["giorni_lavorativi"].description
    assert "data_inizio" in strumenti["giorni_lavorativi"].args and "data_fine" in strumenti["giorni_lavorativi"].args
    assert "giorni" in strumenti["calcola_scadenza"].args


def test_giorni_lavorativi_richiesta_e_risultato():
    strumenti, richieste = costruisci(risposta_giorni)
    testo = strumenti["giorni_lavorativi"].invoke({"data_inizio": "2026-11-02", "data_fine": "2026-11-20"})
    assert len(richieste) == 1
    r = richieste[0]
    assert r.method == "GET" and r.url.path == "/giorni-lavorativi"
    assert dict(r.url.params) == {"da": "2026-11-02", "a": "2026-11-20"}
    assert "15" in testo and "2026-11-02" in testo and "non normativo" in testo
    assert not testo.startswith("Errore")


def test_scadenza_richiesta_e_risultato():
    def gestore(richiesta):
        return httpx.Response(200, json={
            "da": "2026-11-09", "giorni": 10, "data_scadenza": "2026-11-23", "nota": "Risultato non normativo."})

    strumenti, richieste = costruisci(gestore)
    testo = strumenti["calcola_scadenza"].invoke({"data_inizio": "2026-11-09", "giorni": 10})
    assert richieste[0].url.path == "/scadenza"
    assert dict(richieste[0].url.params) == {"da": "2026-11-09", "giorni": "10"}
    assert "2026-11-23" in testo and "non normativo" in testo


def test_422_riporta_il_dettaglio():
    strumenti, _ = costruisci(lambda r: httpx.Response(422, json={"detail": "Parametro 'da' non valido."}))
    testo = strumenti["giorni_lavorativi"].invoke({"data_inizio": "x", "data_fine": "y"})
    assert testo.startswith("Errore:") and "Parametro 'da' non valido." in testo


@pytest.mark.parametrize("codice", [404, 500, 503])
def test_altri_errori_http(codice):
    strumenti, _ = costruisci(lambda r: httpx.Response(codice, text="boom"))
    testo = strumenti["calcola_scadenza"].invoke({"data_inizio": "2026-11-09", "giorni": 3})
    assert testo.startswith("Errore:") and str(codice) in testo


def test_servizio_spento():
    def gestore(richiesta):
        raise httpx.ConnectError("rifiutata")

    strumenti, _ = costruisci(gestore)
    testo = strumenti["giorni_lavorativi"].invoke({"data_inizio": "2026-11-02", "data_fine": "2026-11-20"})
    assert testo.startswith("Errore: servizio non raggiungibile")
    assert BASE in testo


def test_timeout():
    def gestore(richiesta):
        raise httpx.ReadTimeout("lento")

    strumenti, _ = costruisci(gestore, timeout=2.0)
    testo = strumenti["calcola_scadenza"].invoke({"data_inizio": "2026-11-09", "giorni": 3})
    assert testo.startswith("Errore:") and "timeout" in testo and "2" in testo


@pytest.mark.parametrize("risposta", [
    httpx.Response(200, text="non json"),
    httpx.Response(200, json={"altro": 1}),
    httpx.Response(200, json=[1, 2]),
])
def test_risposta_non_valida(risposta):
    strumenti, _ = costruisci(lambda r: risposta)
    testo = strumenti["giorni_lavorativi"].invoke({"data_inizio": "2026-11-02", "data_fine": "2026-11-20"})
    assert testo.startswith("Errore:") and "non valida" in testo


def test_argomenti_di_tipo_sbagliato_danno_errore_chiaro():
    strumenti, richieste = costruisci(risposta_giorni)
    testo = strumenti["calcola_scadenza"].invoke({"data_inizio": "2026-11-09", "giorni": "abc"})
    assert testo.startswith("Errore:") and "calcola_scadenza" in testo and "giorni" in testo
    assert "\n" not in testo and richieste == []


def test_base_url_con_barra_finale():
    client = httpx.Client(transport=httpx.MockTransport(risposta_giorni))
    strumenti = {t.name: t for t in crea_strumenti_http(BASE + "/", 3.0, client=client)}
    strumenti["giorni_lavorativi"].invoke({"data_inizio": "2026-11-02", "data_fine": "2026-11-20"})


@pytest.mark.parametrize("corpo", [
    {"giorni_lavorativi": 5},
    {"da": "2026-11-02", "giorni_lavorativi": 5},
    {"da": "2026-11-02", "a": "2026-11-20", "giorni_lavorativi": "molti"},
])
def test_risposta_con_campi_mancanti_non_solleva(corpo):
    strumenti, _ = costruisci(lambda r: httpx.Response(200, json=corpo))
    testo = strumenti["giorni_lavorativi"].invoke({"data_inizio": "2026-11-02", "data_fine": "2026-11-20"})
    assert testo.startswith("Errore:") and "non valida" in testo


def test_scadenza_con_campi_mancanti_non_solleva():
    strumenti, _ = costruisci(lambda r: httpx.Response(200, json={"data_scadenza": "2026-11-23"}))
    testo = strumenti["calcola_scadenza"].invoke({"data_inizio": "2026-11-09", "giorni": 10})
    assert testo.startswith("Errore:") and "non valida" in testo


def test_url_malformato_non_solleva():
    strumenti = {t.name: t for t in crea_strumenti_http("http://host:abc", 3.0)}
    testo = strumenti["giorni_lavorativi"].invoke({"data_inizio": "2026-11-02", "data_fine": "2026-11-20"})
    assert testo.startswith("Errore:") and "SERVIZI_BASE_URL" in testo
