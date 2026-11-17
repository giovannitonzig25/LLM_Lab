"""Servizio del front-end (Step 8, spec «Servizio `servizio_frontend`»).

Serve la pagina di chat e inoltra `/api/{percorso}` al back-end così com'è (metodo, percorso, query e corpo),
restituendo codice, corpo e content-type del back-end senza modificarli: nessun endpoint ridefinito qui.
"""
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

LOG = logging.getLogger("assistente.servizio_frontend")
STATICI = Path(__file__).parent / "static"


def crea_app(backend: httpx.Client) -> FastAPI:
    """App del front-end; `backend` con `base_url` del back-end delle chat."""
    app = FastAPI(title="Front-end dell'assistente", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=STATICI), name="static")

    @app.get("/", include_in_schema=False)
    def pagina():
        return FileResponse(STATICI / "index.html")

    @app.api_route("/api/{percorso:path}", methods=["GET", "POST", "DELETE"])
    async def inoltra(percorso: str, request: Request):
        corpo = await request.body()
        intestazioni = {}
        if "content-type" in request.headers:
            intestazioni["content-type"] = request.headers["content-type"]
        try:
            # Client sincrono in un thread: un turno lungo (1–3 minuti) non blocca le altre richieste.
            risposta = await run_in_threadpool(
                backend.request,
                request.method,
                "/" + percorso,
                params=request.query_params,
                content=corpo,
                headers=intestazioni,
            )
        except httpx.TransportError as errore:
            LOG.warning("back-end non raggiungibile: %s", errore)
            return JSONResponse(status_code=503, content={"errore": f"Back-end non raggiungibile su {backend.base_url}"})
        return Response(
            content=risposta.content,
            status_code=risposta.status_code,
            media_type=risposta.headers.get("content-type"),
        )

    return app
