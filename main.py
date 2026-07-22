from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal

from proxy.config import ConfigError, load_config
from proxy.router import MinecraftRouter


async def run(config_path: str) -> None:
    config = load_config(config_path)
    router = MinecraftRouter(config)
    server = await asyncio.start_server(router.handle_client, config.listen.host, config.listen.port)
    addresses = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    logging.info("Listening on %s", addresses)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(signum, stop_event.set)

    await stop_event.wait()
    logging.info("Shutdown requested; stopping new connections")
    server.close()
    await server.wait_closed()
    router.close_active_connections()
    await router.wait_for_connections()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A small hostname-based Minecraft TCP router")
    parser.add_argument("-c", "--config", default="config.json", help="path to JSON configuration (default: config.json)")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = parse_args()
    try:
        asyncio.run(run(args.config))
    except KeyboardInterrupt:
        pass
    except ConfigError as exc:
        logging.error("Configuration error: %s", exc)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
