#!/usr/bin/env python3
"""User-space TCP/UDP network-condition emulator for LOG100 labs."""

from __future__ import annotations

import asyncio
import os
import random
import signal
import socket
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


@dataclass(frozen=True)
class Conditions:
    delay_ms: float
    jitter_ms: float
    bandwidth_mbit: float
    udp_loss_percent: float
    seed: int

    @property
    def bytes_per_second(self) -> float:
        if self.bandwidth_mbit <= 0:
            return 0.0
        return self.bandwidth_mbit * 1_000_000 / 8.0


class DelayModel:
    def __init__(self, conditions: Conditions, salt: int = 0) -> None:
        self.conditions = conditions
        self.random = random.Random(conditions.seed + salt)

    def delay_seconds(self) -> float:
        jitter = 0.0
        if self.conditions.jitter_ms > 0:
            jitter = self.random.uniform(-self.conditions.jitter_ms, self.conditions.jitter_ms)
        return max(0.0, self.conditions.delay_ms + jitter) / 1000.0

    def drop_udp(self) -> bool:
        return self.random.random() < self.conditions.udp_loss_percent / 100.0


async def paced_write(
    writer: asyncio.StreamWriter,
    data: bytes,
    bytes_per_second: float,
    state: Dict[str, float],
) -> None:
    if bytes_per_second > 0:
        loop = asyncio.get_running_loop()
        now = loop.time()
        next_time = max(now, state.get("next_time", now))
        if next_time > now:
            await asyncio.sleep(next_time - now)
        writer.write(data)
        await writer.drain()
        state["next_time"] = max(loop.time(), next_time) + len(data) / bytes_per_second
    else:
        writer.write(data)
        await writer.drain()


async def pipe_stream(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    model: DelayModel,
    conditions: Conditions,
) -> None:
    first_chunk = True
    pacing_state: Dict[str, float] = {}
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            if first_chunk:
                await asyncio.sleep(model.delay_seconds())
                first_chunk = False
            await paced_write(writer, data, conditions.bytes_per_second, pacing_state)
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except ConnectionError:
            pass


async def handle_tcp_client(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    target_host: str,
    target_port: int,
    conditions: Conditions,
    salt: int,
) -> None:
    try:
        server_reader, server_writer = await asyncio.open_connection(target_host, target_port)
    except OSError as exc:
        print(f"ERREUR : impossible de joindre {target_host}:{target_port} : {exc}", flush=True)
        client_writer.close()
        await client_writer.wait_closed()
        return

    upstream_model = DelayModel(conditions, salt)
    downstream_model = DelayModel(conditions, salt + 1)
    tasks = [
        asyncio.create_task(
            pipe_stream(client_reader, server_writer, upstream_model, conditions)
        ),
        asyncio.create_task(
            pipe_stream(server_reader, client_writer, downstream_model, conditions)
        ),
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


class UpstreamProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        downstream_transport: asyncio.DatagramTransport,
        client_addr: Tuple[str, int],
        conditions: Conditions,
        salt: int,
    ) -> None:
        self.downstream_transport = downstream_transport
        self.client_addr = client_addr
        self.conditions = conditions
        self.model = DelayModel(conditions, salt)

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        asyncio.create_task(self._return_to_client(data))

    async def _return_to_client(self, data: bytes) -> None:
        delay = self.model.delay_seconds()
        if self.conditions.bytes_per_second > 0:
            delay += len(data) / self.conditions.bytes_per_second
        await asyncio.sleep(delay)
        self.downstream_transport.sendto(data, self.client_addr)


class UdpProxyProtocol(asyncio.DatagramProtocol):
    def __init__(self, target_host: str, target_port: int, conditions: Conditions) -> None:
        self.target_host = target_host
        self.target_port = target_port
        self.conditions = conditions
        self.transport: asyncio.DatagramTransport | None = None
        self.clients: Dict[Tuple[str, int], asyncio.DatagramTransport] = {}
        self.client_models: Dict[Tuple[str, int], DelayModel] = {}
        self.counter = 0

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        asyncio.create_task(self._forward(data, addr))

    async def _forward(self, data: bytes, addr: Tuple[str, int]) -> None:
        assert self.transport is not None
        model = self.client_models.get(addr)
        if model is None:
            self.counter += 1
            model = DelayModel(self.conditions, 10_000 + self.counter * 10)
            self.client_models[addr] = model

        if model.drop_udp():
            return

        upstream = self.clients.get(addr)
        if upstream is None:
            loop = asyncio.get_running_loop()
            upstream_transport, _ = await loop.create_datagram_endpoint(
                lambda: UpstreamProtocol(
                    self.transport,
                    addr,
                    self.conditions,
                    20_000 + self.counter * 10,
                ),
                remote_addr=(self.target_host, self.target_port),
                family=socket.AF_INET,
            )
            upstream = upstream_transport  # type: ignore[assignment]
            self.clients[addr] = upstream

        delay = model.delay_seconds()
        if self.conditions.bytes_per_second > 0:
            delay += len(data) / self.conditions.bytes_per_second
        await asyncio.sleep(delay)
        upstream.sendto(data)

    def connection_lost(self, exc: Exception | None) -> None:
        for transport in self.clients.values():
            transport.close()


def parse_maps(value: str) -> Iterable[Tuple[int, str, int]]:
    if not value.strip():
        return []
    result = []
    for item in value.split(","):
        listen_part, target_part = item.strip().split("=", 1)
        target_host, target_port = target_part.rsplit(":", 1)
        result.append((int(listen_part), target_host, int(target_port)))
    return result


def load_conditions() -> Conditions:
    return Conditions(
        delay_ms=float(os.getenv("LINK_DELAY_MS", "0")),
        jitter_ms=float(os.getenv("LINK_JITTER_MS", "0")),
        bandwidth_mbit=float(os.getenv("LINK_BANDWIDTH_MBIT", "0")),
        udp_loss_percent=float(os.getenv("LINK_UDP_LOSS_PERCENT", "0")),
        seed=int(os.getenv("LINK_SEED", "1001")),
    )


async def main() -> None:
    conditions = load_conditions()
    tcp_maps = list(parse_maps(os.getenv("LINK_TCP_MAPS", "")))
    udp_maps = list(parse_maps(os.getenv("LINK_UDP_MAPS", "")))

    if not tcp_maps and not udp_maps:
        raise SystemExit("ERREUR : définissez LINK_TCP_MAPS et/ou LINK_UDP_MAPS")

    print(
        "Conditions : "
        f"délai={conditions.delay_ms:g} ms, "
        f"variation=±{conditions.jitter_ms:g} ms, "
        f"capacité={conditions.bandwidth_mbit:g} Mbit/s, "
        f"perte UDP={conditions.udp_loss_percent:g} %, "
        f"seed={conditions.seed}",
        flush=True,
    )

    servers = []
    salt = 0
    for listen_port, target_host, target_port in tcp_maps:
        salt += 100
        server = await asyncio.start_server(
            lambda r, w, h=target_host, p=target_port, s=salt: handle_tcp_client(
                r, w, h, p, conditions, s
            ),
            "0.0.0.0",
            listen_port,
        )
        servers.append(server)
        print(
            f"TCP : 0.0.0.0:{listen_port} -> {target_host}:{target_port}",
            flush=True,
        )

    loop = asyncio.get_running_loop()
    udp_transports = []
    for listen_port, target_host, target_port in udp_maps:
        transport, _ = await loop.create_datagram_endpoint(
            lambda h=target_host, p=target_port: UdpProxyProtocol(h, p, conditions),
            local_addr=("0.0.0.0", listen_port),
            family=socket.AF_INET,
        )
        udp_transports.append(transport)
        print(
            f"UDP : 0.0.0.0:{listen_port} -> {target_host}:{target_port}",
            flush=True,
        )

    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    await stop_event.wait()

    for server in servers:
        server.close()
    await asyncio.gather(*(server.wait_closed() for server in servers))
    for transport in udp_transports:
        transport.close()


if __name__ == "__main__":
    asyncio.run(main())
