"""Small deterministic intent classifier for CE's initial CPU-only runtime."""
from __future__ import annotations

import re
from typing import Any

PROFILE_NAME = "default-intents"
PROFILE_VERSION = "0.1"
INTENTS = (
    "memory_recall",
    "knowledge_lookup",
    "relationship_exploration",
    "troubleshooting",
    "explanation",
    "decision_support",
    "general",
)
MAX_TEXT_CHARS = 262_144

# This intentionally stays small and inspectable. Scores are rule-strength indicators,
# not probabilities produced by a trained model.
_RULES: dict[str, tuple[float, tuple[str, ...]]] = {
    "memory_recall": (0.88, (
        "remember", "recall", "previously", "last time", "earlier", "we discussed",
        "what did i say", "what did we decide", "our previous", "from before",
    )),
    "troubleshooting": (0.87, (
        "troubleshoot", "error", "failed", "failure", "broken", "bug", "fix",
        "not working", "doesn't work", "does not work", "exception", "stack trace",
        "crash", "crashed", "503",
    )),
    "relationship_exploration": (0.84, (
        "relationship", "related", "connected", "depends on", "dependency",
        "dependencies", "linked to", "references", "graph traversal",
    )),
    "decision_support": (0.83, (
        "should i", "recommend", "compare", "which", "best", "pros and cons",
        "tradeoff", "trade-off", "evaluate", "choose", "price out", "worth it",
    )),
    "explanation": (0.81, (
        "explain", "why", "how does", "how do", "what causes", "what does",
        "what is meant by", "meaning", "walk me through", "describe",
    )),
    "knowledge_lookup": (0.79, (
        "look up", "lookup", "find", "list", "tell me about", "specs",
        "documentation", "search", "what is", "how many", "when was", "current",
        "show me",
    )),
}


class IntentClassificationError(ValueError):
    """An intent-classification request violates the v1 contract."""

    def __init__(self, code: str, message: str, *, status: int = 422):
        super().__init__(message)
        self.code = code
        self.status = status


def _object(value: Any, name: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or not required.issubset(value) or not set(value).issubset(allowed):
        raise IntentClassificationError("invalid_parameter", f"{name} has missing, unknown, or invalid fields", status=400)
    return value


def _has_phrase(text: str, phrase: str) -> bool:
    if " " in phrase or any(not char.isalnum() and char != "_" for char in phrase):
        return phrase in text
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, flags=re.UNICODE) is not None


def classify(value: Any) -> dict[str, Any]:
    request = _object(value, "request",
        {"request_id", "text", "profile", "allowed_intents"},
        {"request_id", "text", "profile", "allowed_intents"})
    request_id = request["request_id"]
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
        raise IntentClassificationError("invalid_parameter", "request_id must be a string of 1 to 128 characters", status=400)
    text = request["text"]
    if not isinstance(text, str) or not text.strip():
        raise IntentClassificationError("invalid_parameter", "text must be a non-empty string", status=400)
    if len(text) > MAX_TEXT_CHARS:
        raise IntentClassificationError("source_too_large", "text exceeds the character limit", status=413)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise IntentClassificationError("invalid_parameter", "text contains invalid Unicode", status=400) from exc

    profile = _object(request["profile"], "profile", {"name", "version"}, {"name", "version"})
    if profile != {"name": PROFILE_NAME, "version": PROFILE_VERSION}:
        raise IntentClassificationError("unsupported_profile", "intent profile or version is not supported")

    allowed = request["allowed_intents"]
    if not isinstance(allowed, list) or not 1 <= len(allowed) <= len(INTENTS):
        raise IntentClassificationError("invalid_parameter", "allowed_intents must contain between 1 and 7 labels", status=400)
    if any(not isinstance(item, str) or item not in INTENTS for item in allowed):
        raise IntentClassificationError("invalid_parameter", "allowed_intents contains an unsupported label", status=400)
    if len(set(allowed)) != len(allowed):
        raise IntentClassificationError("invalid_parameter", "allowed_intents contains a duplicate label", status=400)

    normalized = text.casefold()
    matches: list[tuple[float, str, tuple[str, ...]]] = []
    for intent, (base_score, phrases) in _RULES.items():
        if intent not in allowed:
            continue
        matched_phrases = tuple(phrase for phrase in phrases if _has_phrase(normalized, phrase))
        if matched_phrases:
            # Additional independent signals increase the heuristic score slightly,
            # but never turn the score into a statistical probability.
            score = min(0.96, base_score + 0.02 * (len(matched_phrases) - 1))
            matches.append((score, intent, matched_phrases))

    if not matches:
        if "general" in allowed:
            chosen, confidence, uncertain = "general", 0.35, True
            evidence = [{"kind": "fallback-general", "version": PROFILE_VERSION}]
        else:
            chosen, confidence, uncertain = allowed[0], 0.25, True
            evidence = [{"kind": "no-matching-allowed-rule", "version": PROFILE_VERSION}]
    else:
        matches.sort(key=lambda item: (-item[0], item[1]))
        confidence, chosen, _ = matches[0]
        uncertain = confidence < 0.60 or (len(matches) > 1 and confidence - matches[1][0] <= 0.05)
        evidence = [
            {"kind": f"keyword-rule:{intent}", "version": PROFILE_VERSION}
            for _, intent, _ in matches
        ][:20]

    return {
        "profile": {"name": PROFILE_NAME, "version": PROFILE_VERSION},
        "results": [{"intent": chosen, "confidence": confidence}],
        "uncertain": uncertain,
        "evidence": evidence,
    }
