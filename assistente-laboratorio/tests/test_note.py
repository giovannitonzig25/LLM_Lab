from datetime import datetime, timezone

import sqlite3

import pytest

from assistente.note import ArchivioNote, ErroreNote, Nota

ISTANTE = datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)


def crea_archivio(tmp_path):
    return ArchivioNote(str(tmp_path / "note.db"), adesso=lambda: ISTANTE)


def test_aggiungi_restituisce_id_e_data(tmp_path):
    archivio = crea_archivio(tmp_path)

    prima = archivio.aggiungi("consegnare il report venerdì")
    seconda = archivio.aggiungi("telefonare al fornitore")

    assert prima == Nota(1, "consegnare il report venerdì", "2026-11-09 10:00:00")
    assert seconda.id == 2


def righe(tmp_path):
    return sqlite3.connect(tmp_path / "note.db").execute("SELECT testo FROM note").fetchall()


def test_elenca_ordine_filtro_limite(tmp_path):
    archivio = crea_archivio(tmp_path)
    archivio.aggiungi("consegnare il report venerdì")
    archivio.aggiungi("comprare il caffè")
    archivio.aggiungi("rivedere il REPORT finale")

    assert [n.id for n in archivio.elenca()] == [3, 2, 1]
    assert [n.id for n in archivio.elenca(filtro="report")] == [3, 1]
    assert [n.id for n in archivio.elenca(limite=2)] == [3, 2]
    for limite in (0, 101):
        with pytest.raises(ErroreNote):
            archivio.elenca(limite=limite)


def test_filtro_tratta_i_caratteri_speciali_alla_lettera(tmp_path):
    archivio = crea_archivio(tmp_path)
    archivio.aggiungi("sconto del 50% oggi")
    archivio.aggiungi("nota qualsiasi")

    assert [n.testo for n in archivio.elenca(filtro="50%")] == ["sconto del 50% oggi"]
    assert archivio.elenca(filtro="%") == [Nota(1, "sconto del 50% oggi", "2026-11-09 10:00:00")]


def test_testo_vuoto_e_troppo_lungo(tmp_path):
    archivio = crea_archivio(tmp_path)
    archivio.aggiungi("prima")

    for testo in ("", "   ", "x" * 501):
        with pytest.raises(ErroreNote):
            archivio.aggiungi(testo)
    assert righe(tmp_path) == [("prima",)]
    assert archivio.aggiungi("x" * 500).id == 2


def test_testo_speciale_salvato_letteralmente(tmp_path):
    archivio = crea_archivio(tmp_path)
    testi = ["l'ordine; DROP TABLE note;--", "città ☂\nriga due"]
    for testo in testi:
        archivio.aggiungi(testo)

    assert [n.testo for n in archivio.elenca()] == testi[::-1]
    assert len(righe(tmp_path)) == 2  # la tabella esiste ancora


def test_archivio_non_accessibile(tmp_path):
    archivio = ArchivioNote(str(tmp_path))  # una cartella, non un file

    with pytest.raises(ErroreNote, match="archivio non accessibile"):
        archivio.aggiungi("ciao")
    with pytest.raises(ErroreNote, match="archivio non accessibile"):
        archivio.elenca()


def test_persistenza_dopo_riavvio(tmp_path):
    crea_archivio(tmp_path).aggiungi("sopravvive")

    seconda = crea_archivio(tmp_path)

    assert [n.testo for n in seconda.elenca()] == ["sopravvive"]
    assert seconda.aggiungi("altra").id == 2


def test_elimina_rimuove_la_nota(tmp_path):
    archivio = crea_archivio(tmp_path)
    archivio.aggiungi("prima")
    archivio.aggiungi("seconda")

    assert archivio.elimina(1) is None

    assert [n.testo for n in archivio.elenca()] == ["seconda"]


def test_elimina_id_inesistente(tmp_path):
    archivio = crea_archivio(tmp_path)
    archivio.aggiungi("prima")

    with pytest.raises(ErroreNote, match="nota 99 non trovata"):
        archivio.elimina(99)
    assert righe(tmp_path) == [("prima",)]
