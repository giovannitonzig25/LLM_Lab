r"""Prova a mano: invoca aggiungi_nota due volte e poi elenca_note sul server avviato a parte.

Server (finestra PowerShell separata, da assistente-laboratorio/):
    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.server_mcp
"""

import asyncio

from fastmcp import Client

URL = "http://127.0.0.1:8001/mcp"


async def chiama(nome: str, argomenti: dict) -> str:
    async with Client(URL) as client:
        return (await client.call_tool(nome, argomenti)).content[0].text


async def main() -> None:
    async with Client(URL) as client:
        print([t.name for t in await client.list_tools()])
    for testo in ("prima nota", "seconda nota"):
        print(await chiama("aggiungi_nota", {"testo": testo}))
    print(await chiama("elenca_note", {}))


asyncio.run(main())
