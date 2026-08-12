"""Archive registry loader. Mirrors vectordb/build.py's collections.yaml pattern."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "archives.yaml"
DATA_DIR = PROJECT_ROOT / "data"
STORES_DIR = PROJECT_ROOT / "stores"

_DEFAULTS = {
    "embedding_model": "Alibaba-NLP/gte-modernbert-base",
    "chunk_size": 2000,
    "chunk_overlap": 200,
    "description": "",
    "documents": [],
}
_ONTOLOGY_DEFAULTS = {
    "id_pattern": r"\b([EP]\d{1,3})(?:\.\d)?\b",
    "family_pattern": r"\b(LRM-?[EPR]\d{1,3}|[A-Z]{1,3}\d{1,3})(?:\.\d)?i?\b",
    "family": None,
    "stop_labels": [],
}
_EPISODE_DEFAULTS = {
    "min_thread_size": 2,
}


def load_config(name: str = "crm-sig") -> dict:
    """Load one archive's config, with defaults filled in.

    Raises KeyError if the archive is not in the registry.
    """
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        registry = yaml.safe_load(f) or {}
    if name not in registry:
        raise KeyError(f"Unknown archive '{name}'. Available: {', '.join(registry)}")

    cfg = {**_DEFAULTS, **registry[name]}
    cfg["ontology"] = {**_ONTOLOGY_DEFAULTS, **cfg.get("ontology", {})}
    cfg["episodes"] = {**_EPISODE_DEFAULTS, **cfg.get("episodes", {})}
    cfg["name"] = name
    return cfg


def pick_device() -> str:
    """'cuda' when a GPU is usable, else 'cpu'.

    Device is not recorded in meta.json and does not need to match between
    build and query: it changes throughput, not the vectors.
    """
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"
