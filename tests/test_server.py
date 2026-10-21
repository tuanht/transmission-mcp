import json

import pytest

from transmission_mcp import server

HASH = "c12fe1c06bba254a9dc9f519b335aa7c1367a88a"


def test_tools_registered():
    import asyncio
    tools = asyncio.run(server.mcp.list_tools())
    assert {t.name for t in tools} == {
        "add_magnet", "get_torrent_status", "list_torrents", "pause_torrent", "resume_torrent"}


async def test_add_magnet_rejects_invalid():
    res = await server.add_magnet("nope")
    assert res["ok"] is False


async def test_add_magnet_via_mcp(monkeypatch):
    class Fake:
        async def add_magnet(self, magnet, download_dir, paused):
            return {"duplicate": False, "id": 3, "hashString": HASH, "name": "n"}

    monkeypatch.setattr(server, "_client", Fake())
    result = await server.mcp.call_tool("add_magnet", {"magnet": f"magnet:?xt=urn:btih:{HASH}"})
    body = json.loads(result.content[0].text)
    assert body["ok"] is True and body["id"] == 3 and body["hash"] == HASH
