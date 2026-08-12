#!/usr/bin/env python3
"""Drive a running MCP server over HTTP and check it actually answers.

    uv run python tools/smoke_mcp_http.py http://127.0.0.1:8000/mcp

Exists for the published container: a health endpoint proves a process is
listening, not that the corpus mounted, the vectors opened, or the model
loaded. This calls the tools -- including a vector search, which is the one
that needs torch, the baked model and the Chroma stores all working at once
-- and fails loudly if any of them is missing.

stdlib only: it runs in CI against a pulled image, where nothing of this
project is installed.
"""
import json
import sys
import time
import urllib.request

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/mcp"
_id = 0


def rpc(method: str, params: dict | None = None, timeout: float = 120) -> dict:
    global _id
    _id += 1
    body = json.dumps({"jsonrpc": "2.0", "id": _id, "method": method,
                       "params": params or {}}).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Content-Type": "application/json",
        # Both, or the streamable-http transport 406s before the server sees
        # the request.
        "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
    for line in raw.splitlines():          # the reply may be an SSE frame
        if line.startswith("data: "):
            return json.loads(line[6:])
    return json.loads(raw)


def call(name: str, args: dict) -> str:
    reply = rpc("tools/call", {"name": name, "arguments": args})
    if "error" in reply:
        raise SystemExit(f"FAIL {name}: {reply['error']}")
    return reply["result"]["content"][0]["text"]


failures = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{'  ' + detail if detail else ''}")
    if not ok:
        failures.append(label)


print(f"driving {URL}")

tools = {t["name"] for t in rpc("tools/list")["result"]["tools"]}
print(f"\ntools advertised: {len(tools)}")
check("both layers registered",
      {"crm_concept", "crm_validate_rdf", "crm_search", "crm_docs"} <= tools,
      f"missing {sorted({'crm_concept', 'crm_validate_rdf', 'crm_search', 'crm_docs'} - tools)}"
      if not {"crm_concept", "crm_validate_rdf", "crm_search", "crm_docs"} <= tools else "")

print("\nontology layer")
check("crm_concept E22", "Human-Made Object" in call("crm_concept", {"identifier": "E22"}))
check("crm_validate_link legal",
      "P108" in call("crm_validate_link", {"subject": "E22", "prop": "P108i",
                                           "obj": "E12"}))

print("\narchive layer")
check("crm_search bm25",
      len(call("crm_search", {"query": "E55 Type versus E57 Material",
                              "mode": "bm25", "top_k": "3"})) > 200)

t0 = time.perf_counter()
vec = call("crm_search", {"query": "why model production as an event",
                          "mode": "vector", "top_k": "3"})
dt = time.perf_counter() - t0
check("crm_search vector", len(vec) > 200, f"[{dt:.2f}s]")
# The point of --warm: a cold store takes ~9.5s to load. If the first vector
# query is slow, the container bound its port before it was ready.
check("server was warmed before serving", dt < 3.0, f"[{dt:.2f}s, want < 3s]")

print("\nprompt")
p = rpc("prompts/get", {"name": "model_an_object",
                        "arguments": {"subject": "a test object"}})
text = p["result"]["messages"][0]["content"]["text"]
check("model_an_object served", "a test object" in text)

print()
if failures:
    raise SystemExit(f"{len(failures)} check(s) failed: {', '.join(failures)}")
print("all checks passed")
