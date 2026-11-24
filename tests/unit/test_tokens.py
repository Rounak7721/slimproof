import os

import pytest
from mcp import types

from slimproof.core.tokens import count_claude_tokens, estimate_tokens, tool_text


def test_estimate_rounds_up() -> None:
    assert estimate_tokens("abcde") == 2
    assert estimate_tokens("") == 0


def test_tool_text_has_only_model_visible_fields() -> None:
    tool = types.Tool(name="ping", description="Pong.", input_schema={"type": "object"})
    expected = '{"name":"ping","description":"Pong.","inputSchema":{"type":"object"}}'
    assert tool_text(tool) == expected


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not found.")
def test_claude_count_is_positive_and_small() -> None:
    tool = types.Tool(name="ping", description="Pong.", input_schema={"type": "object"})
    big = types.Tool(name="find", description="Find files. " * 20, input_schema={"type": "object"})
    small_count, big_count = count_claude_tokens([tool, big])
    assert 0 < small_count < 50
    assert big_count > small_count
