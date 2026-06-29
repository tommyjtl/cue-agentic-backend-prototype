import pytest

from cue_mark.parser import MarkParseError, parse_generated_note


def test_parse_generated_note_json():
    parsed = parse_generated_note(
        '{"title":"MLX Agents","body":"## Highlights\\n\\n- Useful patterns"}',
        fallback_title="Fallback",
    )
    assert parsed.title == "MLX Agents"
    assert "## Highlights" in parsed.body


def test_parse_generated_note_fenced_json():
    parsed = parse_generated_note(
        '```json\n{"title":"Test","body":"## Highlights\\n\\nBody"}\n```',
        fallback_title="Fallback",
    )
    assert parsed.title == "Test"


def test_parse_generated_note_requires_substance():
    with pytest.raises(MarkParseError):
        parse_generated_note('{"title":"Test","body":"## Highlights"}')


def test_parse_generated_note_balanced_json_with_brace_in_body():
    parsed = parse_generated_note(
        'Here you go:\n{"title":"Test","body":"## Highlights\\n\\nUse brace } safely"}',
        fallback_title="Fallback",
    )
    assert parsed.title == "Test"
    assert "brace } safely" in parsed.body
