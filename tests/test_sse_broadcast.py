"""Regression tests for bounded live-sighting delivery."""

import asyncio

import pytest

from bluewatch.webapp.server import WebServer


class _Response:
    def __init__(self, *, block=False, on_write=None):
        self.block = block
        self.on_write = on_write
        self.payloads = []

    async def write(self, payload):
        if self.on_write:
            self.on_write()
        if self.block:
            await asyncio.Event().wait()
        self.payloads.append(payload)


@pytest.mark.asyncio
async def test_broadcast_drops_slow_client_without_blocking_healthy_client():
    server = WebServer()
    healthy = _Response()
    slow = _Response(block=True)
    server._sse_clients = {healthy, slow}

    await asyncio.wait_for(server.broadcast_sighting({"mac": "AA:BB:CC:DD:EE:FF"}), 1)

    assert healthy.payloads
    assert healthy in server._sse_clients
    assert slow not in server._sse_clients


@pytest.mark.asyncio
async def test_broadcast_tolerates_client_removal_during_write():
    server = WebServer()
    departing = _Response()
    remaining = _Response(on_write=lambda: server._sse_clients.discard(departing))
    server._sse_clients = {remaining, departing}

    await server.broadcast_sighting({"mac": "AA:BB:CC:DD:EE:FF"})

    assert remaining.payloads
