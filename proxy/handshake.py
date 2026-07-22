from __future__ import annotations

import asyncio
from dataclasses import dataclass


MAX_HANDSHAKE_PACKET_SIZE = 1_048_576
MAX_VARINT_BYTES = 5


class HandshakeError(ValueError):
    """Raised if client does not send a valid handshake."""


@dataclass(frozen=True)
class Handshake:
    protocol_version: int
    server_address: str
    server_port: int
    next_state: int
    raw_packet: bytes


def decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    value = 0
    for index in range(MAX_VARINT_BYTES):
        if offset + index >= len(data):
            raise HandshakeError("truncated VarInt")
        byte = data[offset + index]
        value |= (byte & 0x7F) << (7 * index)
        if not byte & 0x80:
            if value & (1 << 31):
                value -= 1 << 32
            return value, offset + index + 1
    raise HandshakeError("VarInt is longer than 5 bytes")


async def _read_varint_raw(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    raw = bytearray()
    for _ in range(MAX_VARINT_BYTES):
        byte = await reader.readexactly(1)
        raw.extend(byte)
        if not byte[0] & 0x80:
            value, _ = decode_varint(bytes(raw))
            return value, bytes(raw)
    raise HandshakeError("VarInt is longer than 5 bytes")


def _require(data: bytes, offset: int, length: int) -> bytes:
    if length < 0 or offset + length > len(data):
        raise HandshakeError("truncated handshake packet")
    return data[offset : offset + length]


async def read_handshake(reader: asyncio.StreamReader) -> Handshake:
    packet_length, length_raw = await _read_varint_raw(reader)
    if not 0 <= packet_length <= MAX_HANDSHAKE_PACKET_SIZE:
        raise HandshakeError(f"invalid handshake packet length: {packet_length}")
    payload = await reader.readexactly(packet_length)
    offset = 0

    packet_id, offset = decode_varint(payload, offset)
    if packet_id != 0:
        raise HandshakeError(f"expected handshake packet ID 0, got {packet_id}")
    protocol_version, offset = decode_varint(payload, offset)
    address_length, offset = decode_varint(payload, offset)
    address_bytes = _require(payload, offset, address_length)
    offset += address_length
    try:
        server_address = address_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HandshakeError("hostname is not valid UTF-8") from exc

    server_port = int.from_bytes(_require(payload, offset, 2), "big")
    offset += 2
    next_state, offset = decode_varint(payload, offset)
    if offset != len(payload):
        raise HandshakeError("unexpected trailing data in handshake packet")

    return Handshake(protocol_version, server_address, server_port, next_state, length_raw + payload)
