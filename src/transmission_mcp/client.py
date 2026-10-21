"""Minimal Transmission JSON-RPC client and status verdicts."""

import os
from typing import Any

import httpx

FIELDS = [
    "id", "hashString", "name", "status", "percentDone", "metadataPercentComplete",
    "rateDownload", "rateUpload", "peersConnected", "peersSendingToUs", "eta",
    "error", "errorString", "totalSize", "sizeWhenDone", "leftUntilDone",
    "downloadDir", "addedDate", "isFinished",
]

# Transmission torrent status codes.
STOPPED, CHECK_WAIT, CHECK, DOWNLOAD_WAIT, DOWNLOAD, SEED_WAIT, SEED = range(7)


class TransmissionError(RuntimeError):
    pass


class TransmissionClient:
    def __init__(self, url: str | None = None, user: str | None = None,
                 password: str | None = None, timeout: float = 15.0):
        self.url = url or os.environ.get(
            "TRANSMISSION_URL", "http://host.containers.internal:9091/transmission/rpc")
        user = user if user is not None else os.environ.get("TRANSMISSION_USER")
        password = password if password is not None else os.environ.get("TRANSMISSION_PASSWORD")
        auth = (user, password or "") if user else None
        self._http = httpx.AsyncClient(auth=auth, timeout=timeout)
        self._session_id = ""

    async def call(self, method: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        body = {"method": method, "arguments": arguments or {}}
        for _ in range(2):
            try:
                r = await self._http.post(
                    self.url, json=body, headers={"X-Transmission-Session-Id": self._session_id})
            except httpx.HTTPError as e:
                raise TransmissionError(f"cannot reach Transmission at {self.url}: {e}") from e
            if r.status_code == 409:  # CSRF handshake: pick up the new session id and retry once
                self._session_id = r.headers.get("X-Transmission-Session-Id", "")
                continue
            if r.status_code == 401:
                raise TransmissionError("Transmission rejected credentials (401)")
            r.raise_for_status()
            data = r.json()
            if data.get("result") != "success":
                raise TransmissionError(f"Transmission error: {data.get('result')}")
            return data.get("arguments", {})
        raise TransmissionError("Transmission session handshake failed")

    async def add_magnet(self, magnet: str, download_dir: str | None = None,
                         paused: bool = False) -> dict[str, Any]:
        args: dict[str, Any] = {"filename": magnet, "paused": paused}
        if download_dir:
            args["download-dir"] = download_dir
        res = await self.call("torrent-add", args)
        if "torrent-duplicate" in res:
            return {"duplicate": True, **res["torrent-duplicate"]}
        return {"duplicate": False, **res["torrent-added"]}

    async def get_torrents(self, ids: list[int | str] | None = None) -> list[dict[str, Any]]:
        args: dict[str, Any] = {"fields": FIELDS}
        if ids is not None:
            args["ids"] = ids
        return (await self.call("torrent-get", args)).get("torrents", [])

    async def action(self, method: str, ids: list[int | str]) -> None:
        await self.call(method, {"ids": ids})

    async def aclose(self) -> None:
        await self._http.aclose()


def verdict(t: dict[str, Any]) -> str:
    """Plain answer to "is this torrent downloading?"."""
    if t.get("error"):
        return "error"
    status = t["status"]
    if status == STOPPED:
        return "complete" if t.get("percentDone", 0) >= 1 else "paused"
    if t.get("metadataPercentComplete", 1) < 1:
        return "fetching_metadata" if status != STOPPED else "paused"
    if status in (CHECK_WAIT, CHECK):
        return "checking"
    if status == DOWNLOAD_WAIT:
        return "queued"
    if status == DOWNLOAD:
        return "downloading" if t.get("rateDownload", 0) > 0 else "stalled"
    if status in (SEED_WAIT, SEED):
        return "seeding"
    return "unknown"


def summarize(t: dict[str, Any]) -> dict[str, Any]:
    out = {
        "id": t["id"],
        "hash": t["hashString"],
        "name": t["name"],
        "verdict": verdict(t),
        "percent_done": round(t["percentDone"] * 100, 1),
        "download_kbps": round(t["rateDownload"] / 1000, 1),
        "peers_connected": t["peersConnected"],
        "peers_sending": t["peersSendingToUs"],
        "eta_seconds": t["eta"] if t["eta"] >= 0 else None,
        "size_bytes": t["sizeWhenDone"],
        "download_dir": t["downloadDir"],
    }
    if t.get("error"):
        out["error"] = t.get("errorString")
    return out
