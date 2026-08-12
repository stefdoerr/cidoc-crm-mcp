"""The CIDOC CRM concept graph: parsing, hierarchy queries, and validation.

This package was one 2,266-line module, `lib/ontology.py`, split by concern
into eight files: `parse` (the specification XML into a model), `family`
(the extension models and retired vocabulary), `graph` (questions about the
hierarchy), `uris` (identifiers as URIs), `validate` (is one link legal),
`documents` (checking a whole document), `rdf` (reading RDF), and `sources`
(folding in a source the spec XML is not).

Every name the old module exposed is re-exported here explicitly, so
`from lib.ontology import X` keeps working for all 16 importers across this
repository -- including the eight names that look private (a leading
underscore) but are imported deliberately by tests and tools. Nothing
outside this package needs to know the split exists.
"""

import json
import re
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

from .parse import (
    _TAG,
    _WS,
    _check_declared_counts,
    _examples,
    _ids,
    _one_id,
    _properties_of_property,
    parse_ontology,
    strip_html,
)
from .family import (
    FAMILY_SUPPLEMENT,
    MAX_FALLBACK_NUMBER,
    _DECLARATION_FIELDS,
    _PREFIX,
    add_extensions,
    add_historical,
    family_of,
    family_prefixes,
    load_family,
)

# A bare re-annotation, matching the one `family.py` itself carries on this
# name. The original single-file module picked up a module-level
# `__annotations__` dict as a side effect of declaring
# `FAMILY_SUPPLEMENT: dict[str, tuple[str, str]] = {...}` at top level; a
# plain `from .family import FAMILY_SUPPLEMENT` does not, so without this
# line `__annotations__` silently drops out of `dir(lib.ontology)`.
FAMILY_SUPPLEMENT: dict[str, tuple[str, str]]
from .graph import (
    _SORT_ID,
    _ancestors_in,
    _distance_to,
    _first_sentence,
    _model_view,
    _property_depth,
    _property_name,
    _sort_key,
    ancestors,
    applicable_properties,
    connecting_properties,
    full_listing,
    is_required,
    ontology_skeleton,
    property_closure,
    required_properties,
    resolve_property_id,
)
from .uris import (
    CRM_NAMESPACE,
    _IdentityCache,
    _NAMESPACE_CACHE,
    _URI_INDEX_CACHE,
    _local_name,
    _namespace_of,
    _owned_namespaces,
    resolve_uri,
    uri_index,
)
from .validate import _property_candidates, validate_link
from .documents import (
    _IN_CLASS,
    _STRUCTURAL_ELEMENTS,
    crm_example_class_uses,
    crm_example_links,
    document_completeness,
    validate_class_labels,
    validate_document,
)
from .rdf import (
    _OWL_INVERSE_OF,
    _RDF_FORMATS,
    _RDF_TYPE,
    _not_invertible_cause,
    crm_inverse_claims,
    crm_rdf_class_uses,
    crm_rdf_links,
)
from .sources import (
    _DECL_ID,
    _decl_section,
    _family_local_id,
    _first_id,
    add_family_rdfs,
    add_rdfs_additions,
    add_spec_additions,
)
