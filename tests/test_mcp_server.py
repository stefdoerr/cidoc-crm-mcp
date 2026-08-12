import json

import pytest


def _server():
    from mcp_server import build_server
    return build_server()


async def _call(name, args):
    result = await _server().call_tool(name, args)
    return result.content[0].text


@pytest.mark.asyncio
async def test_every_ontology_tool_is_registered():
    tools = {t.name for t in await _server().list_tools()}
    assert {"crm_concept", "crm_list", "crm_connect", "crm_validate_link",
            "crm_validate_rdf", "crm_validate_xml"} <= tools


@pytest.mark.asyncio
async def test_concept_returns_the_definition():
    text = await _call("crm_concept", {"identifier": "E22"})
    assert "Human-Made Object" in text


@pytest.mark.asyncio
async def test_concept_reports_an_unknown_identifier_without_raising():
    text = await _call("crm_concept", {"identifier": "E999"})
    assert "E999" in text


@pytest.mark.asyncio
async def test_validate_rdf_accepts_content_and_passes_a_good_document():
    ttl = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
<urn:s> a crm:E52_Time-Span ; crm:P82a_begin_of_the_begin "0600-01-01" .
"""
    text = await _call("crm_validate_rdf", {"content": ttl})
    assert "ok_literal" in text
    assert "unknown_name" not in text


@pytest.mark.asyncio
async def test_validate_rdf_reports_a_reversed_link():
    ttl = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
<urn:o> a crm:E22_Human-Made_Object ; crm:P108_has_produced <urn:p> .
<urn:p> a crm:E12_Production .
"""
    assert "illegal" in (await _call("crm_validate_rdf", {"content": ttl})).lower()


@pytest.mark.asyncio
async def test_validate_rdf_reports_a_stale_class_uri():
    # The check added after a reviewer typed a renamed CRMsci class. It lives
    # in class_labels, which the tool must populate -- an easy step to omit,
    # and omitting it is silent.
    ttl = """
@prefix crmsci: <http://www.cidoc-crm.org/extensions/crmsci/> .
<urn:e> a crmsci:S4_Observation .
"""
    assert "UNKNOWN_CLASS" in await _call("crm_validate_rdf", {"content": ttl})


@pytest.mark.asyncio
async def test_validate_rdf_content_and_path_agree(tmp_path):
    ttl = """
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
<urn:o> a crm:E22_Human-Made_Object ; crm:P108i_was_produced_by <urn:p> .
<urn:p> a crm:E12_Production .
"""
    f = tmp_path / "m.ttl"
    f.write_text(ttl, encoding="utf-8")
    assert (await _call("crm_validate_rdf", {"content": ttl})
            == await _call("crm_validate_rdf", {"path": str(f)}))


@pytest.mark.asyncio
async def test_validate_rdf_requires_exactly_one_source():
    for args in ({}, {"content": "x", "path": "y"}):
        text = await _call("crm_validate_rdf", args)
        assert "content" in text and "path" in text


@pytest.mark.asyncio
async def test_the_schema_marks_the_right_arguments_required():
    by = {t.name: t for t in await _server().list_tools()}
    assert by["crm_concept"].input_schema["required"] == ["identifier"]
    assert "model" not in by["crm_list"].input_schema.get("required", [])


@pytest.mark.asyncio
async def test_the_archive_layer_is_absent_without_its_data():
    from mcp_server import build_server

    tools = {t.name for t in await build_server(archive=False).list_tools()}
    assert "crm_search" not in tools
    assert "crm_concept" in tools          # the ontology layer is unaffected


@pytest.mark.asyncio
async def test_the_archive_layer_registers_when_the_data_is_there():
    from lib.config import DATA_DIR
    from mcp_server import build_server

    if not (DATA_DIR / "clean.jsonl").exists():
        pytest.skip("archive data not built in this checkout")
    tools = {t.name for t in await build_server().list_tools()}
    assert {"crm_search", "crm_show", "crm_thread", "crm_docs",
            "crm_quote", "crm_issue"} <= tools


@pytest.mark.asyncio
async def test_search_returns_hits():
    from lib.config import DATA_DIR
    if not (DATA_DIR / "clean.jsonl").exists():
        pytest.skip("archive data not built in this checkout")
    text = await _call("crm_search", {"query": "multiple instantiation", "k": 3})
    assert text.strip()


@pytest.mark.asyncio
async def test_completeness_is_off_by_default_and_never_changes_the_verdict():
    # The specification calls quantifiers "semantic clarification only" and
    # asks that every property be implemented as optional, so a missing
    # `necessary` property is guidance, not a failure. It must not appear
    # unasked, and asking for it must not turn a passing document into a
    # failing one.
    ttl = ('@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .\n'
           '<urn:p> a crm:E12_Production ; crm:P4_has_time-span <urn:t> .\n'
           '<urn:t> a crm:E52_Time-Span .\n')
    plain = await _call("crm_validate_rdf", {"content": ttl})
    asked = await _call("crm_validate_rdf", {"content": ttl,
                                             "completeness": True})
    assert "P108" not in plain
    assert "P108" in asked
    assert "Verdict: PASSED" in plain
    assert "Verdict: PASSED" in asked


@pytest.mark.asyncio
async def test_both_validators_advertise_the_completeness_argument():
    by = {t.name: t for t in await _server().list_tools()}
    for name in ("crm_validate_rdf", "crm_validate_xml"):
        props = by[name].input_schema["properties"]
        assert "completeness" in props
        assert props["completeness"]["default"] is False


def test_a_real_client_can_drive_the_server_over_stdio(tmp_path):
    """End to end through the actual protocol, not the in-process API.

    Every other test here calls `server.call_tool` directly, which never
    starts a process, never speaks JSON-RPC and never touches stdout. That
    left the whole transport untested, and the one bug found by hand was
    exactly there: the wire format spells the schema key `inputSchema` while
    the SDK's Python object spells it `input_schema`, so a client reading
    the wire crashed on a tool listing that the in-process tests were happy
    with.

    Drives tools/mcp_call.py, which is a real client: it spawns the server,
    initializes, calls, and reads a response frame.
    """
    import subprocess
    import sys

    from lib.config import PROJECT_ROOT

    listing = subprocess.run(
        [sys.executable, "tools/mcp_call.py", "--list"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=180)
    assert listing.returncode == 0, listing.stderr
    for tool in ("crm_concept", "crm_validate_rdf", "crm_connect"):
        assert tool in listing.stdout

    ttl = tmp_path / "m.ttl"
    ttl.write_text(
        '@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .\n'
        '<urn:o> a crm:E22_Human-Made_Object ;\n'
        '    crm:P108i_was_produced_by <urn:p> .\n'
        '<urn:p> a crm:E12_Production .\n', encoding="utf-8")
    called = subprocess.run(
        [sys.executable, "tools/mcp_call.py", "crm_validate_rdf",
         json.dumps({"path": str(ttl)})],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=180)
    assert called.returncode == 0, called.stderr
    assert "1 ok" in called.stdout
    assert "Verdict: PASSED" in called.stdout


@pytest.mark.asyncio
async def test_crm_list_advertises_the_spellings_it_returns():
    """A tool description is how an agent decides what to call.

    crm_list gained RDF local names and a namespace header, and its
    description still described the older behaviour. An agent pulled the
    full catalogue -- its own report calls the result "full catalogue +
    namespaces" -- and then wrote that it could not ask for RDF-ready local
    names in a batch, so it guessed from convention and let the validator
    arbitrate. It was holding the answer. Descriptions have to keep up with
    output or the capability may as well not exist.
    """
    by = {t.name: t for t in await _server().list_tools()}
    described = by["crm_list"].description
    assert "local name" in described
    assert "namespace" in described
    # And it must warn that the unfiltered listing is too big to be
    # practical. The first description promising "ONE call spells every
    # identifier you need" led an agent to call it with no model; the reply
    # is 936 identifiers and ~130KB, and its client truncated it partway
    # through CRMact. The server was fine; the advice was not.
    assert "truncate" in described
    returned = await _call("crm_list", {"model": "CRMsci"})
    assert "Namespaces" in returned
    assert "S19_Encounter_Event" in returned


@pytest.mark.asyncio
async def test_archive_tools_say_when_to_reach_for_them():
    """Descriptions are how an agent decides what to call.

    Measured across nine modelling runs: only four touched an archive tool
    at all, and the descriptions were the likeliest reason -- they described
    mechanism ("hybrid search", "read a thread") and never the occasion. The
    one agent that did read a thread had it settle a class choice, so the
    capability was real and unadvertised.
    """
    by = {t.name: t.description for t in await _server().list_tools()}
    if "crm_search" not in by:
        pytest.skip("archive data not built in this checkout")
    # each says what question it answers, not just how it searches
    assert "what it is FOR" in by["crm_search"]
    assert "modelling question" in by["crm_thread"]
    # ...but WITHOUT naming a worked answer. The first version of this
    # description cited the case that motivated it -- a 2013 thread deciding
    # S19 Encounter Event for a find -- and the next agent to model an
    # excavation chose S19 and said the description pointed it there. A tool
    # description is read before every decision, so an example drawn from a
    # finding is an answer key handed to the thing being measured. The
    # description states the principle; the archive supplies the answer.
    for leak in ("S19", "Encounter Event", "Discovery class"):
        assert leak not in by["crm_thread"], leak
    assert "decision record" in by["crm_issue"]
    assert "modelling question directly" in by["crm_docs"]
    # and crm_docs warns that a subject-matter query is the wrong shape
    assert "domain-agnostic" in by["crm_docs"]


@pytest.mark.asyncio
async def test_the_modelling_prompt_is_offered_and_parameterised():
    srv = _server()
    names = {p.name for p in await srv.list_prompts()}
    assert "model_an_object" in names
    result = await srv.get_prompt("model_an_object",
                                  {"subject": "the Rosetta Stone"})
    text = result.messages[0].content.text
    assert "the Rosetta Stone" in text


@pytest.mark.asyncio
async def test_the_modelling_prompt_carries_no_worked_answer():
    """A prompt is read before every decision, so it is the worst place for
    an example drawn from a finding.

    An earlier crm_thread description illustrated itself with the class one
    agent had chosen; the next agent to face that situation chose the same
    class and said the description sent it there. The prompt states the
    principles and names no class as the answer to any modelling situation.
    """
    result = await _server().get_prompt("model_an_object", {"subject": "a vase"})
    text = result.messages[0].content.text
    for leak in ("S19", "Encounter Event", "Discovery class", "A9 "):
        assert leak not in text, leak
    # Nor any test subject. The context-free-subject advice was first drafted
    # with the case that prompted it, and every candidate example named one
    # of the eight modelled objects -- so an agent modelling that object
    # would be handed the answer at exactly the point the error happens. The
    # example in the prompt is a chair, which is nothing this corpus models.
    import re
    for subject in ("taotie", "uffington", "helmet", "tapestry", "bianzhong",
                    "geoglyph", "chalk"):
        assert subject not in text.lower(), subject
    assert not re.search(r"\bding\b", text, re.I)


@pytest.mark.asyncio
async def test_the_prompt_is_a_file_and_the_module_holds_no_second_copy():
    """One copy, in prompts/. Two would drift, and the file would lose."""
    from pathlib import Path
    import mcp_server

    packaged = Path(mcp_server.__file__).resolve().parent / "prompts"
    assert (packaged / "model_an_object.md").exists()

    served = (await _server().get_prompt(
        "model_an_object", {"subject": "a vase"})).messages[0].content.text
    on_disk = (packaged / "model_an_object.md").read_text(encoding="utf-8")
    assert served.strip() == (
        on_disk.replace("{subject}", "a vase")
               .replace("{source}", "the material you have been given").strip())

    # And the module is not still carrying it. The prompt opens with this
    # line; if it appears in the source too, there are two copies again.
    source = Path(mcp_server.__file__).read_text(encoding="utf-8")
    assert "Produce a CIDOC CRM model of" not in source


@pytest.mark.asyncio
async def test_an_override_dir_replaces_the_packaged_prompt(tmp_path, monkeypatch):
    # The whole point of the container's /prompts mount: improve the advice
    # without rebuilding a 2.5GB image.
    (tmp_path / "model_an_object.md").write_text(
        "Model {subject} from {source}. Mind the braces: { } ex:x a crm:E22 .",
        encoding="utf-8")
    monkeypatch.setenv("CRM_PROMPT_DIR", str(tmp_path))

    text = (await _server().get_prompt(
        "model_an_object", {"subject": "a kylix"})).messages[0].content.text
    assert text.startswith("Model a kylix from the material you have been given.")
    # Substitution is replace, not format: a prompt that grows a Turtle
    # example must not become a KeyError.
    assert "{ } ex:x a crm:E22 ." in text


@pytest.mark.asyncio
async def test_an_override_dir_missing_the_file_falls_back(tmp_path, monkeypatch):
    # An empty mount is the default state of the image's /prompts. It must
    # serve the packaged prompt, not fail.
    monkeypatch.setenv("CRM_PROMPT_DIR", str(tmp_path))
    text = (await _server().get_prompt(
        "model_an_object", {"subject": "a vase"})).messages[0].content.text
    assert "Getting the vocabulary right" in text


@pytest.mark.asyncio
async def test_editing_an_override_takes_effect_without_a_restart(tmp_path, monkeypatch):
    # Re-read per request rather than cached at import, so the edit-and-retry
    # loop does not need a container restart per paragraph.
    override = tmp_path / "model_an_object.md"
    override.write_text("first version, modelling {subject}", encoding="utf-8")
    monkeypatch.setenv("CRM_PROMPT_DIR", str(tmp_path))

    srv = _server()  # one server instance across both calls
    before = (await srv.get_prompt("model_an_object",
                                   {"subject": "a vase"})).messages[0].content.text
    override.write_text("second version, modelling {subject}", encoding="utf-8")
    after = (await srv.get_prompt("model_an_object",
                                  {"subject": "a vase"})).messages[0].content.text

    assert before.startswith("first version")
    assert after.startswith("second version")


@pytest.mark.asyncio
async def test_the_modelling_prompt_keeps_the_findings_that_transfer():
    # The experiment's controls (do not read the repository, use this cached
    # article) are not advice and are deliberately absent. What the runs
    # actually established is present.
    result = await _server().get_prompt("model_an_object", {"subject": "a vase"})
    text = result.messages[0].content.text
    assert "crm_list" in text                      # one call per model, not per id
    assert "whole document" in text                # not a link at a time
    assert "NOT EXAMINED" in text                  # not_crm/unchecked misread
    assert "completeness" in text                  # and that it is not an error
    assert "FORMALISING" in text and "INVENTING" in text
    for control in ("cached", "do not read the repository", "mcp_call.py"):
        assert control not in text, control
    # And no provenance either. A prompt is instructions to whoever is
    # reading it now; how it came to say what it says is repository history,
    # means nothing to a user, and dates the text the moment it changes.
    for meta in ("eight", "measured", "runs that did", "an earlier"):
        assert meta not in text.lower(), meta


def test_the_http_flag_serves_without_exposing_a_path():
    """stdio needs the project directory in the client's config; --http does not.

    The client is told a URL and nothing about where the project lives. This
    starts the real server as a subprocess on a spare port and speaks the
    protocol to it over HTTP, because the host and port are run() kwargs
    rather than Settings fields -- assigning them as settings raises, which
    is how the first attempt at this flag failed.
    """
    import subprocess
    import sys
    import time
    import urllib.error
    import urllib.request

    from lib.config import PROJECT_ROOT

    port = 8791
    proc = subprocess.Popen(
        [sys.executable, "mcp_server.py", "--http", "--port", str(port)],
        cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        body = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "t", "version": "1"}}}).encode()
        deadline = time.time() + 90
        reply = None
        while time.time() < deadline:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/mcp", data=body,
                headers={"Content-Type": "application/json",
                         "Accept": "application/json, text/event-stream"})
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    reply = r.read().decode()
                break
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(1)
        assert reply is not None, "server never accepted a connection"
        assert '"protocolVersion"' in reply or '"capabilities"' in reply, reply[:300]
    finally:
        proc.terminate()
        proc.wait(timeout=30)


def test_http_accepts_a_notification_without_a_session_id():
    """The failure that made the server look absent to a real client.

    A stateful streamable-http session rejects any request arriving without
    the `mcp-session-id` header, with a bare 400. Antigravity opens fresh
    connections and does not always carry it: its first post-handshake
    message, notifications/roots/list_changed, came back 400 and it dropped
    the session --

        MCP server connection closed unexpectedly for cidoc-crm:
          sending "notifications/roots/list_changed": Bad Request

    -- after which the agent had a cached tool manifest and no callable
    tools, and went hunting the filesystem for a CLI instead. Nothing here
    needs a session: every tool is a pure function over one shared read-only
    ontology, so the server runs stateless and a notification is accepted
    (202) rather than refused.
    """
    import subprocess
    import sys
    import time
    import urllib.error
    import urllib.request

    from lib.config import PROJECT_ROOT

    port = 8793
    proc = subprocess.Popen(
        [sys.executable, "mcp_server.py", "--http", "--port", str(port)],
        cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def post(payload):
        # HTTPError subclasses URLError, so a status must be returned rather
        # than raised -- otherwise the wait-for-startup loop below cannot
        # tell "connection refused, retry" from "the server answered 400",
        # and swallows the very failure this test exists to catch.
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/mcp",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     # urllib sends no Accept at all and the transport
                     # answers 406; every real client sends one.
                     "Accept": "application/json, text/event-stream"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            try:
                assert post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {"protocolVersion": "2025-06-18",
                                        "capabilities": {},
                                        "clientInfo": {"name": "t",
                                                       "version": "1"}}}) == 200
                break
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(1)
        else:
            raise AssertionError("server never came up")

        # No session header on either of these, which is the whole point.
        assert post({"jsonrpc": "2.0",
                     "method": "notifications/roots/list_changed"}) == 202
        assert post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) == 200
    finally:
        proc.terminate()
        proc.wait(timeout=30)


@pytest.mark.asyncio
async def test_class_arguments_accept_the_spellings_the_tools_print():
    """crm_concept prints a URI and crm_list prints a local name; both must
    then be accepted as input.

    Observed: an agent read `E22_Human-Made_Object` off this server and
    passed it to crm_connect four times in a row, getting "No such concept:
    E22_HUMAN-MADE_OBJECT" each time, before giving up and guessing the bare
    id. The inconsistency arrived with the URI output -- the more useful the
    printing got, the more obviously wrong the parsing looked.
    """
    for spelling in ("E22", "E22_Human-Made_Object", "crm:E22_Human-Made_Object",
                     "http://www.cidoc-crm.org/cidoc-crm/E22_Human-Made_Object"):
        out = await _call("crm_connect", {"subject_class": spelling,
                                          "object_class": "E53_Place"})
        assert out.startswith("Properties joining E22 and E53"), (spelling, out[:90])


@pytest.mark.asyncio
async def test_an_unknown_class_says_which_spellings_work():
    out = await _call("crm_connect", {"subject_class": "E999_Nonsense",
                                      "object_class": "E53"})
    assert "No such concept: E999_Nonsense" in out
    assert "local name" in out


@pytest.mark.asyncio
async def test_validate_link_accepts_a_local_name_too():
    out = await _call("crm_validate_link", {"subject": "E12_Production",
                                            "crm_property": "P108",
                                            "object_class": "E22_Human-Made_Object"})
    assert "E22_HUMAN" not in out          # the old uppercase mangling
    assert "P108" in out


@pytest.mark.asyncio
async def test_validate_link_takes_the_property_spellings_the_tools_print():
    """The classes accepted a local name before the property did, so
    `crm_list` could print `P111_added` as the name to write and this tool
    would answer "no property matches" for it -- and `P111 added`, the pair
    `crm_concept` prints in adjacent columns, matched nothing either."""
    for spelling in ("P111", "P111_added", "P111 added", "crm:P111_added"):
        out = await _call("crm_validate_link", {"subject": "E79",
                                                "crm_property": spelling,
                                                "object_class": "E22"})
        assert "LEGAL" in out, f"{spelling}: {out}"
        assert "no property matches" not in out


@pytest.mark.asyncio
async def test_validate_link_names_the_property_when_the_pair_disagrees():
    """"P111 augmented" is a real id beside another property's name. Resolving
    it to P111 would answer LEGAL about a property the caller did not name."""
    out = await _call("crm_validate_link", {"subject": "E79",
                                            "crm_property": "P111 augmented",
                                            "object_class": "E22"})
    assert "LEGAL" not in out
    assert "no property matches" in out
    assert "'added'" in out                # what P111 is really called
