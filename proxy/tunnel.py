from __future__ import annotations

import asyncio
import contextlib


async def _pipe(source: asyncio.StreamReader, destination: asyncio.StreamWriter) -> None:
    try:
        while data := await source.read(65_536):
            destination.write(data)
            await destination.drain()
    except (ConnectionError, asyncio.IncompleteReadError):
        pass


async def tunnel(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    backend_reader: asyncio.StreamReader,
    backend_writer: asyncio.StreamWriter,
) -> None:
    client_to_backend = asyncio.create_task(_pipe(client_reader, backend_writer))
    backend_to_client = asyncio.create_task(_pipe(backend_reader, client_writer))
    done, pending = await asyncio.wait(
        {client_to_backend, backend_to_client}, return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
    await asyncio.gather(*done, *pending, return_exceptions=True)

    for writer in (backend_writer, client_writer):
        writer.close()
    for writer in (backend_writer, client_writer):
        with contextlib.suppress(ConnectionError):
            await writer.wait_closed()
