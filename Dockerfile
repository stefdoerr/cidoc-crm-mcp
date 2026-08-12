# The CIDOC CRM MCP server, corpus and all, as one self-contained image.
#
# Everything the running server opens is baked in: the ontology built from
# tracked sources/, the archive and its FTS indexes, the vector stores, and
# the embedding model itself. The container needs no network and no volume.
#
# Two decisions account for most of the size, and both are deliberate:
#
#   CPU torch. The default PyPI torch on linux/amd64 is the CUDA build and
#   drags in 2.7GB of nvidia/* plus 691MB of triton -- 3.4GB of GPU machinery
#   for a container that has no GPU. `--torch-backend=cpu` drops all of it.
#   Nothing is lost: warm vector queries measure 50-90ms on CPU, and
#   pick_device() already returns "cpu" wherever there is no card.
#
#   The model is baked, not downloaded. sentence-transformers would otherwise
#   fetch ~288MB on the first vector query of every fresh container. It is
#   pulled at build time using the name in the store's own meta.json -- never
#   a literal here -- so the image cannot ship a model that disagrees with the
#   vectors it was built to query.

ARG PYTHON_VERSION=3.13

########################  builder  ############################################
FROM python:${PYTHON_VERSION}-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8.14 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    HF_HOME=/opt/hf \
    HF_HUB_DISABLE_PROGRESS_BARS=1 \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app

# Dependencies before source, so editing a .py does not re-resolve or
# re-download 1.4GB of wheels. Only pyproject.toml is copied at this point.
COPY pyproject.toml ./
RUN uv venv /opt/venv --python "$(which python3)" \
 && uv pip install --python /opt/venv --torch-backend=cpu \
        -r pyproject.toml --extra archive

ENV PATH="/opt/venv/bin:$PATH"

# Layer order is load-bearing. The corpus is 876MB and the model 288MB, and
# neither depends on the prompt text or the server module -- so both are
# fetched before the source is copied. `COPY . .` last means editing a prompt
# or a tool rebuilds seconds of layers instead of re-downloading a gigabyte.
# Only the fetcher's own inputs come in early.
COPY build.py ./
COPY lib/ ./lib/
COPY config/ ./config/

# The corpus. A build ARG so a fork can point at its own dataset; public, so
# no credential is needed or accepted here.
ARG CORPUS_REPO=stefdoerr/cidoc-crm-corpus
RUN python build.py fetch --repo "${CORPUS_REPO}"

# The embedding model, fetched by loading it exactly as the server loads it.
#
# Deliberately NOT `snapshot_download(model_name)`. That takes the whole
# repo, and this one publishes nine ONNX variants plus both a
# `pytorch_model.bin` and a `model.safetensors`: 2.4GB, of which
# sentence-transformers reads 288MB. Measured, after it had been written the
# other way and the build sat on it for twenty minutes.
#
# Going through Retriever.warm() takes precisely what the runtime takes, and
# does it by opening the real stores with the model named in their own
# meta.json -- so a corpus and a model that disagree fail the build here
# instead of returning confident nonsense to a user later.
RUN python -c "from lib.retrieve import Retriever; print('[model] baked for', Retriever().warm())"

COPY . .

# Rebuilt from the tracked sources/, never copied from the host: it takes
# 0.9s and is deterministic, and a copied one could silently shadow the
# inputs it derives from.
RUN python build.py ontology

# What corpus is in here, recorded from what actually landed.
#
# This image is unusual in carrying data as well as code, and the data is the
# part that silently changes what a search returns. Two images built from the
# same commit against a rebuilt corpus answer differently and look identical.
# Labels cannot help -- buildkit will not compute one from a build step -- so
# the provenance is a file, derived from each store's own meta.json:
#
#     docker run --rm IMAGE cat /app/corpus-provenance.json
RUN python - <<'PY'
import hashlib, json, pathlib
stores = {}
for p in sorted(pathlib.Path("stores").glob("*/meta.json")):
    m = json.loads(p.read_text())
    stores[p.parent.name] = {k: m.get(k) for k in
                             ("embedding_model", "source_sha256", "normalize")}
if not stores:
    raise SystemExit("no stores/*/meta.json -- corpus fetch did not land")

# What this digest can and cannot tell you, stated in the file rather than
# left for someone to assume. Only crm-sig currently records a
# source_sha256; crm-sig-docs and crm-sig-episodes ship an empty one, so a
# rebuild of either changes what search returns WITHOUT changing this
# digest. A provenance string that silently under-detects is worse than one
# that says where it is blind.
blind = sorted(n for n, s in stores.items() if not s.get("source_sha256"))
digest = hashlib.sha256(
    json.dumps(stores, sort_keys=True).encode()).hexdigest()[:16]
out = {"corpus_digest": digest, "stores": stores}
if blind:
    out["incomplete"] = {
        "stores_without_source_sha256": blind,
        "meaning": "a rebuild of these changes retrieval without changing "
                   "corpus_digest; compare them by image digest instead",
    }
pathlib.Path("corpus-provenance.json").write_text(json.dumps(out, indent=2))
print("[provenance]", digest, "blind:", blind or "none")
PY

# Wheels, uv's cache and the .git dir are all in the builder and none of them
# are copied forward.
RUN find /opt/venv -name '__pycache__' -type d -prune -exec rm -rf {} + \
 && find /opt/venv -name '*.pyc' -delete

########################  runtime  ############################################
FROM python:${PYTHON_VERSION}-slim AS runtime

# Supplied by CI; harmless blanks in a local build.
ARG VCS_REF=""
ARG VERSION="dev"
LABEL org.opencontainers.image.title="cidoc-crm-mcp" \
      org.opencontainers.image.description="CIDOC CRM ontology, validator, and 26 years of CRM-SIG discussion, over MCP" \
      org.opencontainers.image.source="https://github.com/stefdoerr/cidoc-crm-mcp" \
      org.opencontainers.image.licenses="See repository; the indexed mailing list remains its authors'" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${VERSION}"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/hf \
    HF_HUB_DISABLE_PROGRESS_BARS=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    # Everything is present; a lookup that reaches the network here means
    # something is wrong, and failing beats silently downloading at runtime.
    HF_HUB_OFFLINE=1 \
    # No GPU in this image, and torch is the CPU wheel regardless. Stated so
    # pick_device() cannot be fooled by a stray runtime.
    CUDA_VISIBLE_DEVICES="" \
    # A conventional mount point for improving the modelling prompt without
    # rebuilding: put model_an_object.md here and it wins. Safe to leave
    # empty -- any prompt not found here falls back to the packaged
    # /app/prompts, so the image works mounted or not. Re-read per request,
    # so an edit needs no restart either.
    CRM_PROMPT_DIR=/prompts

RUN useradd --system --create-home --uid 10001 crm

# --chown on the COPY, not a `chown -R` afterwards: the latter rewrites the
# ownership of 876MB of corpus into a second layer, doubling it in the image
# for a metadata change. Done this way it costs nothing.
#
# The store has to be writable, which is not what reading a corpus suggests.
# This project's own code writes nothing at runtime -- no open(...,'w'), no
# write_text, no mkdir -- but Chroma opens its SQLite read-write even to
# query it, and fails the open outright if it cannot:
#
#     chromadb.errors.InternalError: error returned from database:
#       (code: 8) attempt to write a readonly database
#
# So `docker run --read-only` does NOT work, and neither does leaving the
# tree root-owned under USER crm. Both were tried; both fail at warm-up,
# before the port is bound, which is at least the honest place to fail.
COPY --from=builder --chown=crm:crm /opt/venv /opt/venv
COPY --from=builder --chown=crm:crm /opt/hf   /opt/hf
COPY --from=builder --chown=crm:crm /app      /app

WORKDIR /app
USER crm

EXPOSE 8000

# --warm loads all three vector stores (~9.5s) before the port is bound, so
# nothing that answers a request has to pay for it. start-period covers that
# window: the container reports "starting", not "unhealthy", while it loads.
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD ["python", "/app/docker/healthcheck.py"]

# 0.0.0.0 because a container port is unreachable otherwise. Note that there
# is NO AUTHENTICATION in this server: publish it behind a reverse proxy that
# has some, or keep the published port bound to the host's loopback.
CMD ["python", "mcp_server.py", "--http", "--host", "0.0.0.0", "--port", "8000", "--warm"]
