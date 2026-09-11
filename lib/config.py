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


def model_kwargs_for(device: str) -> dict:
    """`model_kwargs` for HuggingFaceEmbeddings on this device.

    float32 on CPU, deliberately. gte-modernbert-base publishes
    `torch_dtype: float16`, so transformers loads it in fp16 -- and a CPU
    with no native fp16 matmul emulates every one of the 88 matmuls the
    model runs per forward. Measured on an Ampere A1 (Neoverse-N1, ARMv8.2;
    fp16 matmul arrived with V1/N2), the same [11,768]@[768,2304]:

        fp16   83.74ms        one query embedding, fp16   5,318ms
        fp32    0.50ms        one query embedding, fp32      70ms

    End to end that was `crm_search` at 4.7s and `crm_docs` at 22s against
    roughly 0.2s and 0.4s. x86 is emulated too, just far less visibly.

    Left alone on CUDA, where fp16 is native, fast, and halves resident
    memory.

    The dtype does not change what comes back. Four queries across the
    message and document stores returned identical, identically ordered
    chunk ids under fp16 and fp32 -- against stores whose vectors were
    embedded elsewhere -- so this needs no rebuild and no re-embedding.
    """
    kwargs: dict = {"device": device}
    if device == "cpu":
        # Nested on purpose: sentence-transformers forwards its own
        # `model_kwargs` to AutoModel.from_pretrained, and that is the one
        # that decides the dtype.
        kwargs["model_kwargs"] = {"torch_dtype": "float32"}
    return kwargs
