"""Model-specific context token counting with an explicit conservative fallback.

CE's lexical Tokenization service is intentionally not used here: lexical terms
are not model token IDs and do not predict a provider context window.
"""
from __future__ import annotations

from functools import lru_cache
import json
import os
from typing import Any


@lru_cache(maxsize=32)
def _load_tokenizer(local_path: str) -> Any:
    """Load an explicitly provisioned Hugging Face tokenizer without network access."""
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(
        local_path,
        local_files_only=True,
        trust_remote_code=False,
    )


def count_context_tokens(text: str, model: str) -> tuple[int, str, str | None]:
    """Return (count, method, fallback_reason) for one serialized context fragment.

    CE_GATEWAY_TOKENIZER_MAP is a JSON object mapping the exact request model
    name to a locally provisioned tokenizer directory. No tokenizer is
    downloaded at request time. If no usable mapping exists, UTF-8 byte length
    is used as a conservative byte-token upper-bound estimate and is explicitly
    identified as an estimate rather than provider-token accuracy.
    """
    mapping_text = os.environ.get("CE_GATEWAY_TOKENIZER_MAP", "")
    if mapping_text:
        try:
            mapping = json.loads(mapping_text)
            if not isinstance(mapping, dict) or any(
                not isinstance(key, str) or not isinstance(value, str) or not value
                for key, value in mapping.items()
            ):
                raise ValueError("tokenizer map must map model names to non-empty local paths")
        except (TypeError, ValueError, json.JSONDecodeError):
            return len(text.encode("utf-8")), "conservative_utf8_byte_upper_bound", "invalid_tokenizer_map"
        local_path = mapping.get(model)
        if local_path:
            try:
                tokenizer = _load_tokenizer(local_path)
                return len(tokenizer.encode(text, add_special_tokens=False)), "configured_model_tokenizer", None
            except Exception:
                return len(text.encode("utf-8")), "conservative_utf8_byte_upper_bound", "configured_tokenizer_unavailable"
    return len(text.encode("utf-8")), "conservative_utf8_byte_upper_bound", "no_configured_tokenizer"
