from __future__ import annotations

import asyncio
import contextlib
import logging

from .config import RouterConfig
from .handshake import HandshakeError, read_handshake
from .tunnel import tunnel


def _normalise_hostname(hostname: str) -> str:
    return hostname.lower().rstrip(".")


class MinecraftRouter:
    def __init__(self, config: RouterConfig) -> None:
        self.config = config
        self._connections: set[asyncio.Task[None]] = set()

    def close_active_connections(self) -> None:
        for task in tuple(self._connections):
            task.cancel()

    async def wait_for_connections(self) -> None:
        if self._connections:
            await asyncio.gather(*tuple(self._connections), return_exceptions=True)

    async def handle_client(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._connections.add(task)
        peer = client_writer.get_extra_info("peername")
        peer_label = peer[0] if isinstance(peer, tuple) else str(peer or "unknown")
        logging.info("Connection from %s", peer_label)
        backend_writer: asyncio.StreamWriter | None = None

        try:
            handshake = await read_handshake(client_reader)
            hostname = handshake.server_address
            logging.info("Requested hostname: %s", hostname)
            backend = self.config.routes.get(_normalise_hostname(hostname))
            if backend is None:
                logging.warning("Unknown hostname from %s: %s", peer_label, hostname)
                return

            logging.info("Connecting to backend %s:%s", backend.host, backend.port)
            try:
                backend_reader, backend_writer = await asyncio.open_connection(backend.host, backend.port)
            except OSError as exc:
                logging.warning("Backend unavailable for %s (%s:%s): %s", hostname, backend.host, backend.port, exc)
                return

            backend_writer.write(handshake.raw_packet)
            await backend_writer.drain()
            logging.info("Tunnel established for %s", hostname)
            await tunnel(client_reader, client_writer, backend_reader, backend_writer)
        except asyncio.IncompleteReadError:
            logging.info("Client %s disconnected before completing handshake", peer_label)
        except HandshakeError as exc:
            logging.warning("Invalid handshake from %s: %s", peer_label, exc)
        except (ConnectionError, OSError) as exc:
            logging.info("Connection for %s closed: %s", peer_label, exc)
        except asyncio.CancelledError:
            raise
        finally:
            if backend_writer is not None and not backend_writer.is_closing():
                backend_writer.close()
                with contextlib.suppress(ConnectionError):
                    await backend_writer.wait_closed()
            if not client_writer.is_closing():
                client_writer.close()
                with contextlib.suppress(ConnectionError):
                    await client_writer.wait_closed()
            if task is not None:
                self._connections.discard(task)
