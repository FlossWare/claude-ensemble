# Local model runtime

Claude Ensemble's core inference must run locally. Runtime services must not call
hosted inference APIs or download model files while serving requests.

## Embedding

The Embedding service uses a locally installed Sentence Transformers model and
forces inference onto the CPU. Install the runtime dependency separately from
the contract-test dependencies:

```sh
python -m pip install -r requirements-runtime.txt
```

The default model directory is `~/.FlossWare/models/nomic-embed-text-v1.5`; the expected model ID defaults to `nomic-ai/nomic-embed-text-v1.5`. Override the directory with `CE_EMBEDDING_MODEL_PATH` if needed. Set `CE_EMBEDDING_MODEL_VERSION` to the reviewed immutable revision provisioned locally; it is intentionally required so deployment metadata cannot silently omit the revision.

One-time provisioning example (run manually with network access, never during service startup):

```sh
mkdir -p "$HOME/.FlossWare/models/nomic-embed-text-v1.5"
hf download nomic-ai/nomic-embed-text-v1.5 \\
  --revision "$NOMIC_EMBEDDING_REVISION" \\
  --local-dir "$HOME/.FlossWare/models/nomic-embed-text-v1.5"
export CE_EMBEDDING_MODEL_VERSION="$NOMIC_EMBEDDING_REVISION"
```

Set `NOMIC_EMBEDDING_REVISION` to an immutable revision selected and reviewed for the deployment, and record its license and checksum. Keep model files outside Git.

The configured path must be a local directory. Model loading uses
`local_files_only=True`, `trust_remote_code=False`, and `device="cpu"`.
Missing files or dependencies cause the service readiness check to report
`ready: false`; serving requests never triggers a model download. Do not set
the model path to a remote repository ID.

Keep model files outside the source repository and provision them through the
machine's controlled setup process. Record the model name, version, dimension,
license, and checksum in the deployment's local configuration documentation.


## Optional entity-recognition model

Entity Extraction can use an optional locally installed spaCy NER model in addition to
its deterministic pattern and alias workers. Configure \`CE_ENTITY_NER_MODEL_PATH\`
to a directory containing the installed model. The service calls \`spacy.load()\`
on that local path after requiring CPU execution. It does not run a model-download
command or resolve remote model names at runtime.

If the variable is unset, exact technical extraction remains available and readiness
reports a degraded-but-usable state. If a path is configured but the model cannot be
loaded, readiness reports \`ready: false\`.


## Nomic embedding profile

The intended embedding model is `nomic-ai/nomic-embed-text-v1.5`, configured for 768-dimensional vectors. CE prepends `search_query: ` to query inputs and `search_document: ` to document inputs; callers send raw text without these prefixes. Provision model files outside the source repository through the machine's controlled setup process. Record the exact model revision, dimension, license, and checksum. Real-model integration validation remains outstanding until those exact weights are provisioned and exercised offline.


### Validate the actual model offline

After provisioning the exact model revision and configuring the three environment variables, run:

```sh
python scripts/validate_local_embedding_model.py
```

The check forces Hugging Face/Transformers offline mode before model loading, then exercises both query and document paths on CPU. It verifies the configured model identity, 768 dimensions, finite values, and L2 normalization. It does not download weights. A successful run is the required real-weight validation; CI's fake-model tests alone do not establish that the provisioned files are correct.
