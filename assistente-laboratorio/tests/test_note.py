from datetime import datetime, timezone

from assistente.note import ArchivioNote, Nota

ISTANTE = datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)


def crea_archivio(tmp_path):
    return ArchivioNote(str(tmp_path / "note.db"), adesso=lambda: ISTANTE)


def test_aggiungi_restituisce_id_e_data(tmp_path):
    archivio = crea_archivio(tmp_path)

    prima = archivio.aggiungi("consegnare il report venerdì")
    seconda = archivio.aggiungi("telefonare al fornitore")

    assert prima == Nota(1, "consegnare il report venerdì", "2026-11-09 10:00:00")
    assert seconda.id == 2
