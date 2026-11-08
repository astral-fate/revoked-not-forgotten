"""Flat (single-prompt) rendering of an executor conversation.

Used by experiment 08: the fine-tuning rows are (prompt = this rendering of the conversation so far,
completion = the next executor turn), and at evaluation time both the tuned model and its untuned base
receive the conversation in exactly this rendering as one user message.
"""
from __future__ import annotations

HEAD = {"system": "### SYSTEM", "user": "### USER", "assistant": "### ASSISTANT"}
TAIL = "### ASSISTANT (next turn: one JSON tool call)"


def render_prompt(messages: list[dict]) -> str:
    parts = [f"{HEAD[m['role']]}\n{m['content'].strip()}" for m in messages]
    return "\n\n".join(parts + [TAIL])
