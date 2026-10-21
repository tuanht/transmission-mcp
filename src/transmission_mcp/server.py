"""MCP server exposing Transmission: add magnets, check status, pause/resume."""

import os
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from .client import TransmissionClient, TransmissionError, summarize
from .magnet import InvalidMagnet, parse_magnet

mcp = MCPServer("transmission")
_client: TransmissionClient | None = None


def client() -> TransmissionClient:
    global _client
    if _client is None:
        _client = TransmissionClient()
    return _client


async def _find(hash_or_id: str) -> dict[str, Any]:
    ident: int | str = int(hash_or_id) if hash_or_id.isdigit() and len(hash_or_id) < 10 else hash_or_id.lower()
    torrents = await client().get_torrents([ident])
    if not torrents:
        raise TransmissionError(f"no torrent matches {hash_or_id!r}")
    return torrents[0]


@mcp.tool()
async def add_magnet(magnet: str, download_dir: str | None = None, paused: bool = False) -> dict:
    """Send a magnet link to Transmission to start downloading.

    Returns the torrent id and infohash (use either with get_torrent_status). If the torrent
    was already added, `duplicate` is true and nothing new is started. Metadata for a fresh
    magnet takes a few seconds, so call get_torrent_status shortly after to confirm it is
    actually downloading. download_dir defaults to Transmission's configured location.
    """
    try:
        infohash, _ = parse_magnet(magnet)
    except InvalidMagnet as e:
        return {"ok": False, "error": str(e)}
    try:
        added = await client().add_magnet(magnet, download_dir, paused)
    except TransmissionError as e:
        return {"ok": False, "error": str(e)}
    return {
        "ok": True,
        "duplicate": added["duplicate"],
        "id": added["id"],
        "hash": added.get("hashString", infohash),
        "name": added.get("name"),
    }


@mcp.tool()
async def get_torrent_status(hash_or_id: str) -> dict:
    """Check whether a torrent is downloading.

    Accepts the infohash (40-char hex) or the numeric id from add_magnet. `verdict` is one of:
    downloading, stalled (active but 0 B/s), fetching_metadata, queued, checking, paused,
    complete, seeding, error.
    """
    try:
        return {"ok": True, **summarize(await _find(hash_or_id))}
    except TransmissionError as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
async def list_torrents(verdict: str | None = None) -> dict:
    """List all torrents with a compact status each; optionally filter by verdict (e.g. "downloading")."""
    try:
        items = [summarize(t) for t in await client().get_torrents()]
    except TransmissionError as e:
        return {"ok": False, "error": str(e)}
    if verdict:
        items = [i for i in items if i["verdict"] == verdict]
    return {"ok": True, "count": len(items), "torrents": items}


@mcp.tool()
async def pause_torrent(hash_or_id: str) -> dict:
    """Pause a torrent (stop transferring, keep the files)."""
    return await _act("torrent-stop", hash_or_id)


@mcp.tool()
async def resume_torrent(hash_or_id: str) -> dict:
    """Resume a paused torrent."""
    return await _act("torrent-start", hash_or_id)


async def _act(method: str, hash_or_id: str) -> dict:
    try:
        t = await _find(hash_or_id)
        await client().action(method, [t["id"]])
        return {"ok": True, **summarize((await client().get_torrents([t["id"]]))[0])}
    except TransmissionError as e:
        return {"ok": False, "error": str(e)}


def main() -> None:
    mcp.run(
        "streamable-http",
        host=os.environ.get("MCP_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_PORT", "8650")),
        # Reached by IP/loopback from other containers; DNS-rebinding host checks would reject that.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )


if __name__ == "__main__":
    main()
