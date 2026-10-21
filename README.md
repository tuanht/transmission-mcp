# transmission-mcp

MCP server (streamable HTTP, `/mcp` on port 8650) that lets an agent send magnet links to
Transmission and check whether they are downloading.

## Tools
- `add_magnet(magnet, download_dir?, paused?)`: validates the magnet, adds it, reports duplicates.
- `get_torrent_status(hash_or_id)`: verdict (`downloading`, `stalled`, `fetching_metadata`, `queued`, `checking`, `paused`, `complete`, `seeding`, `error`) plus progress, speed, peers, ETA.
- `list_torrents(verdict?)`
- `pause_torrent(hash_or_id)` / `resume_torrent(hash_or_id)`

## Config (environment)
| Variable | Default |
|--|--|
| `TRANSMISSION_URL` | `http://host.containers.internal:9091/transmission/rpc` |
| `TRANSMISSION_USER` / `TRANSMISSION_PASSWORD` | unset (no auth) |
| `MCP_HOST` / `MCP_PORT` | `0.0.0.0` / `8650` |

## Develop
    uv sync && uv run pytest
    uv run transmission-mcp

## Container
    podman build -t localhost/transmission-mcp:latest .

The Quadlet unit lives in the `hermes-desktop` repo (`quadlet/transmission-mcp.container`), joins the
`hermes` pod, and is reached by Hermes at `http://127.0.0.1:8650/mcp`. There is no auth; do not expose the port.
