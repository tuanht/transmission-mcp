import base64

import httpx
import pytest

from transmission_mcp.client import TransmissionClient, TransmissionError, verdict
from transmission_mcp.magnet import InvalidMagnet, parse_magnet

HASH = "c12fe1c06bba254a9dc9f519b335aa7c1367a88a"


def test_parse_hex():
    assert parse_magnet(f"magnet:?xt=urn:btih:{HASH.upper()}&dn=Foo+Bar") == (HASH, "Foo Bar")


def test_parse_base32():
    b32 = base64.b32encode(bytes.fromhex(HASH)).decode()
    assert parse_magnet(f"magnet:?xt=urn:btih:{b32}")[0] == HASH


@pytest.mark.parametrize("bad", ["http://x", "magnet:?dn=x", "magnet:?xt=urn:btih:xyz"])
def test_parse_invalid(bad):
    with pytest.raises(InvalidMagnet):
        parse_magnet(bad)


def t(**kw):
    base = {"status": 4, "percentDone": 0.5, "metadataPercentComplete": 1, "rateDownload": 1000, "error": 0}
    return {**base, **kw}


@pytest.mark.parametrize("torrent,expected", [
    (t(), "downloading"),
    (t(rateDownload=0), "stalled"),
    (t(metadataPercentComplete=0), "fetching_metadata"),
    (t(status=0), "paused"),
    (t(status=0, percentDone=1), "complete"),
    (t(status=3), "queued"),
    (t(status=2), "checking"),
    (t(status=6), "seeding"),
    (t(error=3), "error"),
])
def test_verdict(torrent, expected):
    assert verdict(torrent) == expected


async def test_session_handshake_and_duplicate():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers.get("X-Transmission-Session-Id"))
        if request.headers.get("X-Transmission-Session-Id") != "abc":
            return httpx.Response(409, headers={"X-Transmission-Session-Id": "abc"})
        return httpx.Response(200, json={"result": "success", "arguments": {
            "torrent-duplicate": {"id": 7, "hashString": HASH, "name": "n"}}})

    c = TransmissionClient("http://x/rpc")
    c._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    res = await c.add_magnet(f"magnet:?xt=urn:btih:{HASH}")
    assert res["duplicate"] is True and res["id"] == 7
    assert calls == ["", "abc"]


async def test_unreachable():
    def handler(request):
        raise httpx.ConnectError("boom")

    c = TransmissionClient("http://x/rpc")
    c._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(TransmissionError):
        await c.call("session-get")
