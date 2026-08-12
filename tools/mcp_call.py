#!/usr/bin/env python3
"""Call one tool on the cidoc-crm MCP server and print the text it returns.

    uv run python tools/mcp_call.py --list
    uv run python tools/mcp_call.py crm_concept '{"identifier": "E22"}'
    uv run python tools/mcp_call.py crm_validate_rdf '{"path": "m.ttl"}'

The server speaks JSON-RPC over stdio and is meant to be driven by an MCP
client, which makes it awkward to exercise by hand or from a shell. This is
that client, reduced to one call: spawn the server, initialize, call, print,
exit. One process per call is wasteful -- the server exists partly so the
ontology is loaded once -- but it keeps this usable from a terminal or a
script, and correctness here matters more than the second it costs.

Arguments are a single JSON object, quoted. Anything the server writes to
stderr (the archive layer announcing itself absent, for instance) is passed
through to stderr, so stdout carries only the tool's own text and can be
piped.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL = "2025-06-18"


def _rpc(proc, obj):
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()


def _read(proc):
    """The next JSON-RPC frame, skipping anything that is not one.

    The server is careful to keep stdout clean, but a dependency that logs
    on import would corrupt the stream, and a client that dies on it is
    harder to debug than one that says what it saw.
    """
    while True:
        line = proc.stdout.readline()
        if not line:
            return None
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        raise SystemExit(0)

    proc = subprocess.Popen(
        [sys.executable, "mcp_server.py"], cwd=ROOT,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1)
    try:
        _rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": PROTOCOL, "capabilities": {},
                               "clientInfo": {"name": "mcp_call",
                                              "version": "1"}}})
        if _read(proc) is None:
            raise SystemExit("server exited during initialize:\n"
                             + proc.stderr.read())
        _rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        if args[0] == "--list":
            _rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            for tool in _read(proc)["result"]["tools"]:
                # `inputSchema` on the wire, `input_schema` on the Python
                # object the SDK builds -- the protocol is camelCase and the
                # binding is not. Both spellings accepted so this keeps
                # working whichever side of that a future SDK lands on.
                schema = tool.get("inputSchema") or tool.get("input_schema") or {}
                required = schema.get("required", [])
                params = ", ".join(
                    name + ("" if name in required else "?")
                    for name in schema.get("properties", {}))
                print(f"{tool['name']}({params})")
                print(f"    {tool['description']}")
            return

        name = args[0]
        try:
            arguments = json.loads(args[1]) if len(args) > 1 else {}
        except json.JSONDecodeError as e:
            raise SystemExit(f"arguments must be one JSON object: {e}")

        _rpc(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": name, "arguments": arguments}})
        reply = _read(proc)
        if reply is None:
            raise SystemExit("server exited during the call:\n"
                             + proc.stderr.read())
        if "error" in reply:
            raise SystemExit(f"{name}: {reply['error'].get('message')}")
        for block in reply["result"].get("content", []):
            if block.get("type") == "text":
                print(block["text"])
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.terminate()
        err = proc.stderr.read().strip()
        if err:
            print(err, file=sys.stderr)


if __name__ == "__main__":
    main()
