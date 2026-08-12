"""The package's import surface, pinned.

`lib/ontology` was one 2,266-line module and is now a package whose
`__init__` re-exports everything. That list is hand-maintained and it fails
silently: a name dropped from it still passes every test that does not
import that name, and the break surfaces somewhere else entirely -- a tool,
the CLI, the MCP server -- at the moment someone runs it.

Eight of the names below are private and look exactly like internal detail
a tidy-up would remove. They are imported deliberately: `_model_view` by
two eval scripts, `_URI_INDEX_CACHE` by a cache-invalidation test,
`_property_candidates` and `_ancestors_in` by tests that check the pieces
rather than the whole. Underscore is not a reliable signal here, which is
the whole reason this file exists.
"""
import lib.ontology as O

# Every name imported BY NAME from lib.ontology anywhere in the repository,
# collected by grep across build.py, search.py, mcp_server.py, lib/, tools/
# and tests/ at the time of the split.
IMPORTED_ELSEWHERE = [
    "add_extensions", "add_family_rdfs", "add_historical",
    "add_rdfs_additions", "ancestors", "_ancestors_in",
    "applicable_properties", "connecting_properties",
    "crm_example_class_uses", "crm_example_links", "crm_inverse_claims",
    "crm_rdf_class_uses", "crm_rdf_links", "full_listing", "load_family",
    "_local_name", "_model_view", "_namespace_of", "ontology_skeleton",
    "_owned_namespaces", "parse_ontology", "_property_candidates",
    "property_closure", "_property_depth", "resolve_property_id",
    "resolve_uri", "uri_index", "_URI_INDEX_CACHE", "validate_class_labels",
    "validate_document", "validate_link",
]


def test_every_name_the_repository_imports_is_still_exported():
    missing = [n for n in IMPORTED_ELSEWHERE if not hasattr(O, n)]
    assert missing == []


def test_the_two_caches_are_shared_not_copied():
    # Both are module-level singletons mutated in place, and `sources.py`
    # calls .drop() on them from a different module than the one that
    # populates them. If the split had given a module its own instance,
    # invalidation would clear one while the other kept serving the stale
    # index -- which is the bug fixed earlier on this branch, reintroduced
    # by the layout instead of by the cache key. Identity, not equality:
    # two empty caches compare fine and behave wrongly.
    from lib.ontology import sources
    from lib.ontology.uris import _NAMESPACE_CACHE, _URI_INDEX_CACHE

    assert O._URI_INDEX_CACHE is _URI_INDEX_CACHE
    assert O._NAMESPACE_CACHE is _NAMESPACE_CACHE
    assert sources._URI_INDEX_CACHE is _URI_INDEX_CACHE
    assert sources._NAMESPACE_CACHE is _NAMESPACE_CACHE


def test_the_layered_modules_do_not_import_backwards():
    # The split assumes a DAG: parse and family depend on nothing internal,
    # graph sits above them, uris above graph, validate above uris, and
    # documents, rdf and sources on top. A cycle would still import -- Python
    # tolerates plenty of them -- but it would mean a definition sits in the
    # wrong module, and the next person to move one would find out the hard
    # way.
    #
    # uris and validate were one rank, as peers, for as long as neither used
    # the other. `_property_candidates` now resolves a property named as a URI,
    # a `crm:` name or an RDF local name by asking `resolve_uri`, rather than
    # parsing those three forms a second time and drifting from it -- so name
    # resolution is genuinely the lower layer and says so here. The guard is
    # unchanged in kind: still a strict DAG, still one direction only.
    import ast
    import pathlib

    layer = {"parse": 0, "family": 0, "graph": 1, "uris": 2, "validate": 3,
             "documents": 4, "rdf": 4, "sources": 4}
    root = pathlib.Path(O.__file__).parent
    backwards = []
    for name, rank in layer.items():
        tree = ast.parse((root / f"{name}.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                other = node.module
                if other in layer and layer[other] >= rank:
                    backwards.append(f"{name} imports {other}")
    assert backwards == []
