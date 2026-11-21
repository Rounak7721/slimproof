"""Count tokens in MCP tool definitions."""

import json
import math

from mcp import types

DEFAULT_RATIO = 4.0

CLAUDE_MODEL = "claude-opus-5-5"


def tool_text(tool: types.Tool) -> str:
    """Serialize the parts of a tool the model sees, as compact JSON."""
    fields = {"name", "description", "input_schema"}
    data = tool.model_dump(include=fields, exclude_none=True, by_alias=True)
    return json.dumps(data, separators=(",", ":"))


def estimate_tokens(text: str, ratio: float = DEFAULT_RATIO) -> int:
    """Estimate tokens as characters / ratio, rounded up."""
    return math.ceil(len(text) / ratio)


def count_claude_tokens(tool: types.Tool, model: str = CLAUDE_MODEL) -> int:
    """Exact tokens `tool` adds to a Claude request, via the free count_tokens API."""
    try:
        from anthropic import Anthropic
        from anthropic.types import MessageParam, ToolParam
    except ImportError as e:
        raise RuntimeError("Install the extra: pip install 'slimproof[claude]'") from e

    client = Anthropic()

    messages: list[MessageParam] = [{"role": "user", "content": "hi"}]
    anchor: ToolParam = {"name": "anchor", "input_schema": {"type": "object"}}

    fields = {"name", "description", "input_schema"}
    target = ToolParam(**tool.model_dump(include=fields, exclude_none=True))
    base = client.messages.count_tokens(model=model, messages=messages, tools=[anchor])
    full = client.messages.count_tokens(model=model, messages=messages, tools=[anchor, target])

    return full.input_tokens - base.input_tokens
