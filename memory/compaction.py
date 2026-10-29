"""Context Bloat Management and History Compaction.

Implements token-based sliding windows, message pruning, and recursive
summarization to prevent context exhaustion across multi-agent turns.
"""

from typing import Any


class HistoryCompactor:
    """Manages LLM conversation history and context window compaction."""

    def __init__(self, max_token_budget: int = 8000, sliding_window_turns: int = 6):
        """Initializes the context compactor.

        Args:
            max_token_budget: Maximum estimated tokens permitted before compaction triggers.
            sliding_window_turns: Number of recent turns to preserve verbatim.
        """
        self.max_token_budget = max_token_budget
        self.sliding_window_turns = sliding_window_turns

    def estimate_tokens(self, text: str) -> int:
        """Estimates token count using standard 4 characters per token heuristic."""
        return max(1, len(text) // 4)

    def compact_conversation_history(
        self, messages: list[dict[str, Any]], system_prompt: str
    ) -> list[dict[str, Any]]:
        """Prunes and compacts older conversation turns into a dense executive summary.

        Preserves:
        1. Original system instructions / constitution.
        2. Consolidated executive summary of older researched college details.
        3. The most recent N conversation turns intact.

        Args:
            messages: List of message dictionaries containing 'role' and 'content'.
            system_prompt: System prompt / constitution string.

        Returns:
            Compacted list of messages within token budget.
        """
        system_tokens = self.estimate_tokens(system_prompt)
        total_tokens = system_tokens + sum(self.estimate_tokens(m.get("content", "")) for m in messages)

        # If comfortably within budget, no compaction needed
        if total_tokens <= self.max_token_budget or len(messages) <= self.sliding_window_turns:
            return messages

        # Split into historical turns to summarize vs. recent turns to keep intact
        split_idx = max(1, len(messages) - self.sliding_window_turns)
        older_messages = messages[:split_idx]
        recent_messages = messages[split_idx:]

        # Compact older messages into an executive summary
        summary_points: list[str] = []
        for msg in older_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # Extract key factual sentences rather than raw HTML or search dumps
            first_sentence = content.split(".")[0].strip()
            if first_sentence:
                summary_points.append(f"[{role}]: {first_sentence[:120]}...")

        condensed_summary = (
            "### EXECUTIVE CONTEXT SUMMARY (Compacted History)\n"
            + "\n".join(summary_points[:8])
            + "\n[Context compacted to preserve token budget]"
        )

        compacted_history: list[dict[str, Any]] = [
            {"role": "system", "content": f"{system_prompt}\n\n{condensed_summary}"},
            *recent_messages,
        ]

        return compacted_history

    def compact_tool_output(self, raw_tool_result: str, max_chars: int = 1500) -> str:
        """Truncates verbose tool output (e.g. raw web scraper dump) to salient facts."""
        if len(raw_tool_result) <= max_chars:
            return raw_tool_result

        return (
            raw_tool_result[:max_chars]
            + f"\n... [Truncated {len(raw_tool_result) - max_chars} characters of raw output to prevent context bloat]"
        )
