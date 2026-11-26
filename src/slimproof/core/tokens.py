"""Count tokens in MCP tool definitions."""

import importlib.util
import json
import math
import os

from mcp import types

# Characters per Claude token for MCP tool JSON: measured 2.24-3.16 on 6 servers (avg 2.59).
DEFAULT_RATIO = 2.5

CLAUDE_MODEL = "claude-opus-5-5"


def tool_text(tool: types.Tool) -> str:
    """Serialize the parts of a tool the model sees, as compact JSON."""
    fields = {"name", "description", "input_schema"}
    data = tool.model_dump(include=fields, exclude_none=True, by_alias=True)
    return json.dumps(data, separators=(",", ":"))


def estimate_tokens(text: str, ratio: float = DEFAULT_RATIO) -> int:
    """Estimate tokens as characters / ratio, rounded up."""
    return math.ceil(len(text) / ratio)


def claude_setup_problem() -> str | None:
    """Why exact Claude counting can't run here, or None if it can."""
    if importlib.util.find_spec("anthropic") is None:
        return "--exact needs the claude extra: pip install 'slimproof[claude]'"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "--exact needs ANTHROPIC_API_KEY set in your environment"
    return None


def count_claude_tokens(tools: list[types.Tool], model: str = CLAUDE_MODEL) -> list[int]:
    """Exact tokens each tool adds to a Claude request, via the free count_tokens API."""
    if not tools:
        return []
    try:
        from anthropic import Anthropic, AnthropicError
        from anthropic.types import MessageParam, ToolParam
    except ImportError as e:
        raise RuntimeError("Install the extra: pip install 'slimproof[claude]'") from e

    messages: list[MessageParam] = [{"role": "user", "content": "hi"}]
    anchor: ToolParam = {"name": "anchor", "input_schema": {"type": "object"}}
    fields = {"name", "description", "input_schema"}
    try:
        # One call per tool; max_retries rides out per-minute rate limits on big servers.
        client = Anthropic(max_retries=5)
        base = client.messages.count_tokens(model=model, messages=messages, tools=[anchor])
        counts = []
        for tool in tools:
            target = ToolParam(**tool.model_dump(include=fields, exclude_none=True))
            full = client.messages.count_tokens(
                model=model, messages=messages, tools=[anchor, target]
            )
            counts.append(full.input_tokens - base.input_tokens)
    except AnthropicError as e:  # bad key, no network, API down: one clear line, no traceback
        raise RuntimeError(f"Can't count tokens with the Claude API: {e}") from None
    return counts


def count_tokens(
    tools: list[types.Tool], exact: bool = False, ratio: float = DEFAULT_RATIO
) -> list[int]:
    """Tokens for each tool: exact via Claude's API, or estimated as characters / `ratio`."""
    if exact:
        return count_claude_tokens(tools)  # blocking calls; fine for a CLI run
    return [estimate_tokens(tool_text(t), ratio) for t in tools]
