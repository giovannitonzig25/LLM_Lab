"""Invoca due volte di seguito aggiungi_nota sul server avviato a parte."""

import asyncio

from fastmcp import Client


async def main() -> None:
    async with Client("http://127.0.0.1:8001/mcp") as client:
        print([t.name for t in await client.list_tools()])
    for testo in ("prima nota", "seconda nota"):
        async with Client("http://127.0.0.1:8001/mcp") as client:
            risultato = await client.call_tool("aggiungi_nota", {"testo": testo})
            print(risultato.content[0].text)


asyncio.run(main())
