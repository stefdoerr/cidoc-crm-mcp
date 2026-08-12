#!/usr/bin/env python3
"""Container healthcheck: is the MCP endpoint actually answering?

Speaks the protocol rather than checking that a port is open. A process that
has bound 8000 but cannot serve a request is exactly the state a TCP probe
calls healthy and a user calls broken.

stdlib only, on purpose -- this runs every 30s inside the image and has no
business importing torch.
"""
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("HEALTHCHECK_URL", "http://127.0.0.1:8000/mcp")
TIMEOUT = float(os.environ.get("HEALTHCHECK_TIMEOUT", "10"))

BODY = json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "healthcheck", "version": "0"},
    },
}).encode()

req = urllib.request.Request(
    URL,
    data=BODY,
    method="POST",
    headers={
        "Content-Type": "application/json",
        # Streamable-http requires both: a client that offers only JSON gets
        # a 406 from the transport before the server sees the request.
        "Accept": "application/json, text/event-stream",
    },
)

try:
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        payload = resp.read().decode("utf-8", "replace")
        if resp.status != 200:
            print(f"unhealthy: HTTP {resp.status}", file=sys.stderr)
            sys.exit(1)
        # The reply is JSON or an SSE frame wrapping it, depending on what the
        # transport negotiated; both carry this field, and neither carries it
        # if the server failed to initialise.
        if "protocolVersion" not in payload:
            print(f"unhealthy: no protocolVersion in reply: {payload[:200]}",
                  file=sys.stderr)
            sys.exit(1)
except urllib.error.HTTPError as exc:
    print(f"unhealthy: HTTP {exc.code} {exc.read()[:200]!r}", file=sys.stderr)
    sys.exit(1)
except Exception as exc:
    print(f"unhealthy: {type(exc).__name__}: {exc}", file=sys.stderr)
    sys.exit(1)

sys.exit(0)
