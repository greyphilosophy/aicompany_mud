"""
Tests for Qwen3-14B-NVFP4 thinking tag handling in LLMClient.

Problem: Qwen3 models output <thinking> tags around reasoning content,
e.g. `<thinking>Let me consider...<\/thinking>{"desc": "..."}`.
The old `_extract_json_from_text` regex `\\{[^{}]*\\}` finds the JSON
inside the thinking block first, missing the real answer after the tag.

Solution: Strip thinking tags before JSON extraction via `_strip_thinking_tags`.
"""

import pytest

from utils.llm_client import LLMClient


# ─── Test 1: Reproduce the problem ───


def test_qwen3_thinking_tags_json_inside_tags_works():
    """PROBLEM: When thinking tags contain valid JSON, the regex matches
    the thinking content instead of the real response JSON after the tag.

    This test proves the fix handles thinking-tagged responses correctly.
    """
    client = LLMClient()

    # Simulated Qwen3-14B-NVFP4 response with thinking tags
    qwen3_response = """<thinking>
The user wants a catgirl statue. I should consider the appearance:
- Ears on head, tail, feline features
- Pose should be dynamic
</thinking>
{"desc": "A beautiful catgirl statue with perked ears and a flowing tail"}"""

    result = client._extract_json_from_text(qwen3_response, label="QWEN3")
    assert result is not None
    assert result.get("desc") == "A beautiful catgirl statue with perked ears and a flowing tail"


def test_qwen3_thinking_tags_no_json_in_thinking():
    """Thinking tags with text-only content, JSON after tags.

    The regex should find the JSON block after stripping thinking tags.
    """
    client = LLMClient()

    response = """<thinking>
Let me think about this room...
It has a desk and a window.
</thinking>
{"desc": "A room with a desk and window"}"""

    result = client._extract_json_from_text(response, label="QWEN3")
    assert result is not None
    assert result.get("desc") == "A room with a desk and window"


def test_qwen3_thinking_tags_nested_braces_in_thinking():
    """Thinking tags contain braces that confuse the regex.

    If the thinking text contains `{` or `}` characters, the regex
    `\\{[^{}]*\\}` might match a partial thinking fragment.
    """
    client = LLMClient()

    response = """<thinking>
The {desk} needs a lamp and some books.
</thinking>
{"desc": "A study with a desk, lamp, and books"}"""

    result = client._extract_json_from_text(response, label="QWEN3")
    assert result is not None
    assert result.get("desc") == "A study with a desk, lamp, and books"


# ─── Test 2: Verify _strip_thinking_tags works correctly ───


def test_strip_thinking_tags_removes_standard_tags():
    """SOLUTION: Strip <thinking>...</thinking> blocks before JSON extraction."""
    client = LLMClient()

    response = """<thinking>
Let me consider the room layout.
</thinking>
{"desc": "A cozy room"}"""

    stripped = client._strip_thinking_tags(response)
    assert "<thinking>" not in stripped
    assert "</thinking>" not in stripped

    # JSON extraction should work on the result
    result = client._extract_json_from_text(response, label="QWEN3")
    assert result is not None
    assert result["desc"] == "A cozy room"


def test_strip_thinking_tags_handles_multiple_blocks():
    """SOLUTION: Multiple thinking blocks should all be stripped."""
    client = LLMClient()

    response = """<thinking>First thought</thinking>
<thinking>Second thought</thinking>
{"desc": "Final answer"}"""

    stripped = client._strip_thinking_tags(response)
    assert "<thinking>" not in stripped
    assert "First thought" not in stripped
    assert "Second thought" not in stripped

    result = client._extract_json_from_text(response, label="QWEN3")
    assert result is not None
    assert result["desc"] == "Final answer"


def test_strip_thinking_tags_multiline_content():
    """SOLUTION: Thinking tags with multiline content should be fully stripped."""
    client = LLMClient()

    response = """<thinking>
Line 1: Consider the layout
Line 2: Think about lighting
Line 3: Check the exits
</thinking>
{"desc": "A well-lit room"}"""

    result = client._extract_json_from_text(response, label="QWEN3")
    assert result is not None
    assert result["desc"] == "A well-lit room"


def test_no_thinking_tags_passthrough():
    """SOLUTION: Responses without thinking tags should pass through unchanged."""
    client = LLMClient()

    response = """{"desc": "A room"}"""

    stripped = client._strip_thinking_tags(response)
    assert stripped == response

    result = client._extract_json_from_text(response, label="QWEN3")
    assert result is not None
    assert result["desc"] == "A room"


# ─── Test 3: Integration with _extract_json_from_text ───


def test_extract_json_with_thinking_tags_end_to_end():
    """END-TO-END: Full pipeline should handle thinking-tagged responses."""
    client = LLMClient()

    response = """<thinking>
The user wants a catgirl statue. Key features:
- Cat ears on head
- Tail with fluffy end
- Cute, playful expression
- Standing pose
</thinking>
{
  "desc": "A cute catgirl statue standing with perked ears and a fluffy tail",
  "props": ["cat_ears", "tail"],
  "pose": "standing"
}"""

    result = client._extract_json_from_text(response, label="QWEN3")
    assert result is not None
    assert result["desc"] == "A cute catgirl statue standing with perked ears and a fluffy tail"
    assert result["props"] == ["cat_ears", "tail"]
    assert result["pose"] == "standing"


def test_extract_json_complex_response_with_thinking():
    """END-TO-END: Complex room creation with thinking tags."""
    client = LLMClient()

    response = """<thinking>
Analyzing the request: a workshop room with a workbench, tools, and good lighting.
The workbench should be central with tools hanging nearby.
</thinking>
{
  "desc": "A workshop with a large workbench, hanging tools, and warm overhead lighting",
  "objects": ["workbench", "tool_rack", "lamp"],
  "exits": ["corridor_north", "door_south"]
}"""

    result = client._extract_json_from_text(response, label="QWEN3")
    assert result is not None
    assert "workshop" in result["desc"]
    assert "workbench" in result["objects"]
    assert "door_south" in result["exits"]
