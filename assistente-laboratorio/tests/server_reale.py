"""Helper di test: server FastMCP reale su 127.0.0.1 (porta libera), porte chiuse e mute."""

import socket
import threading
import time
from contextlib import contextmanager

import uvicorn


@contextmanager
def avvia_server_mcp(server):
    """Restituisce l'URL http://127.0.0.1:<porta>/mcp; chiude il server in uscita."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    porta = sock.getsockname()[1]
    app = server.http_app(path="/mcp")
    uv = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    thread = threading.Thread(target=uv.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    scadenza = time.monotonic() + 10
    while not uv.started:
        if time.monotonic() > scadenza or not thread.is_alive():
            uv.should_exit = True
            raise RuntimeError("server MCP di prova non avviato")
        time.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{porta}/mcp"
    finally:
        uv.should_exit = True
        thread.join(timeout=10)
        sock.close()


def porta_chiusa() -> str:
    """URL MCP su una porta libera in cui nessuno è in ascolto."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    return f"http://127.0.0.1:{porta}/mcp"


@contextmanager
def porta_muta():
    """Socket in ascolto che accetta connessioni ma non risponde mai (non parla MCP)."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(5)
    try:
        yield f"http://127.0.0.1:{s.getsockname()[1]}/mcp"
    finally:
        s.close()
