from __future__ import annotations

from typing import Any


def ask_user(question: str = "", response_type: str = "text", options: list[str] | None = None) -> dict[str, Any]:
    response_type = (response_type or "text").strip().lower()
    if response_type not in {"text", "yes_no", "choice"}:
        return {"tool": "clarify", "error": "invalid_response_type", "response_type": response_type}
    options = options or []
    if response_type == "choice" and not options:
        return {"tool": "clarify", "error": "missing_choice_options"}
    return {
        "tool": "clarify",
        "question": question,
        "response_type": response_type,
        "options": options,
        "awaiting_user": True,
    }
