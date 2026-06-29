from cue_mark.telegram.formatting import format_search_reply, markdown_to_telegram_html


def test_markdown_bold():
    assert markdown_to_telegram_html("**For Developers:** guide") == (
        "<b>For Developers:</b> guide"
    )


def test_markdown_link():
    result = markdown_to_telegram_html("See [WisdomPlan](https://wisdomplan.ai/) today.")
    assert result == 'See <a href="https://wisdomplan.ai/">WisdomPlan</a> today.'


def test_markdown_bullet_with_bold():
    result = markdown_to_telegram_html("* **For Developers:** The guide")
    assert result == "* <b>For Developers:</b> The guide"


def test_markdown_heading():
    assert markdown_to_telegram_html("## AI Literacy") == "<b>AI Literacy</b>"


def test_markdown_escapes_html():
    assert markdown_to_telegram_html("Tom & Jerry <3") == "Tom &amp; Jerry &lt;3"


def test_markdown_inline_code():
    assert markdown_to_telegram_html("Use `SKILL20` at checkout") == (
        "Use <code>SKILL20</code> at checkout"
    )


def test_format_search_reply_truncates():
    long_answer = "x" * 5000
    assert len(format_search_reply(long_answer)) == 4096
