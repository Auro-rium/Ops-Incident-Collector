from opsincident_collector.processors.secret_redactor import redact_text


def test_secret_redactor_replaces_secrets() -> None:
    text = "Bearer abc123\npassword=unsafe\npostgres://user:pass@db/app"
    redacted, summary = redact_text(text)

    assert "[REDACTED_SECRET]" in redacted
    assert "unsafe" not in redacted
    assert summary.redacted_count >= 2
    assert summary.had_possible_secret is True
