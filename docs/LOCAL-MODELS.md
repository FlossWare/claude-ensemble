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

Provision model files before starting CE, then configure:

- `CE_EMBEDDING_MODEL_PATH`: filesystem path to the complete local model directory.
- `CE_EMBEDDING_MODEL_VERSION`: deployment-pinned version or revision identifier.
- `CE_EMBEDDING_MODEL_ID`: required value `nomic-ai/nomic-embed-text-v1.5`.

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
