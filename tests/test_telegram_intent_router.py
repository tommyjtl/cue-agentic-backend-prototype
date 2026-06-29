import pytest

from cue_mark.telegram.intent_router import IntentParseError, parse_intent_response


def test_parse_intent_response_search():
    parsed = parse_intent_response(
        '{"intent":"search","confidence":"high","reason":"User asked about saved notes.",'
        '"search_query":"AI agents"}'
    )
    assert parsed.intent == "search"
    assert parsed.confidence == "high"
    assert parsed.search_query == "AI agents"
    assert parsed.reason


def test_parse_intent_response_fenced_json():
    parsed = parse_intent_response(
        '```json\n{"intent":"reindex","confidence":"medium","reason":"User wants to refresh the index."}\n```'
    )
    assert parsed.intent == "reindex"
    assert parsed.confidence == "medium"


def test_parse_intent_response_rejects_mark():
    with pytest.raises(IntentParseError, match="Unsupported intent"):
        parse_intent_response(
            '{"intent":"mark","confidence":"high","reason":"User wants to save a thought."}'
        )


def test_parse_intent_response_requires_search_query():
    with pytest.raises(IntentParseError, match="search_query"):
        parse_intent_response(
            '{"intent":"search","confidence":"high","reason":"Looks like search."}'
        )


def test_parse_intent_response_requires_reason():
    with pytest.raises(IntentParseError, match="reason"):
        parse_intent_response('{"intent":"unknown","confidence":"low","reason":""}')


def test_parse_intent_response_rejects_invalid_intent():
    with pytest.raises(IntentParseError, match="intent"):
        parse_intent_response(
            '{"intent":"delete","confidence":"high","reason":"Nope.","search_query":""}'
        )
