from datetime import datetime, timezone

from assistente.note import ArchivioNote
from assistente.server_mcp import crea_server
from assistente.verifica_mcp import main, verifica
from server_reale import avvia_server_mcp, porta_chiusa, porta_muta


def server_di_prova(tmp_path):
    return crea_server(ArchivioNote(str(tmp_path / "note.db")))


def test_server_reale_esce_con_0_e_elenca_i_nomi(tmp_path, capsys):
    with avvia_server_mcp(server_di_prova(tmp_path)) as url:
        codice = verifica(url)

    assert codice == 0
    uscita = capsys.readouterr().out
    for nome in ("aggiungi_nota", "elenca_note", "elimina_nota"):
        assert nome in uscita


def test_porta_chiusa_esce_con_1(capsys):
    assert verifica(porta_chiusa(), timeout=2) == 1
    assert capsys.readouterr().err.strip()


def test_porta_aperta_che_non_parla_mcp_esce_con_1(capsys):
    with porta_muta() as url:  # una semplice connessione TCP riuscirebbe: la discovery no
        assert verifica(url, timeout=0.5) == 1
    assert capsys.readouterr().err.strip()


def test_server_senza_strumenti_esce_con_1(capsys):
    from fastmcp import FastMCP

    with avvia_server_mcp(FastMCP("vuoto")) as url:
        assert verifica(url) == 1
    assert "nessuno strumento" in capsys.readouterr().err


def test_main_legge_mcp_url_e_timeout(tmp_path, monkeypatch):
    with avvia_server_mcp(server_di_prova(tmp_path)) as url:
        monkeypatch.setenv("MCP_URL", url)
        monkeypatch.setenv("MCP_TIMEOUT", "5")
        assert main() == 0


def test_main_con_timeout_non_valido_esce_con_1(monkeypatch, capsys):
    monkeypatch.setenv("MCP_TIMEOUT", "abc")

    assert main() == 1
    assert "MCP_TIMEOUT" in capsys.readouterr().err
