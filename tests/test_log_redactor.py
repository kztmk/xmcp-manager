from xmcp_manager.log_redactor import redact_text


def test_redacts_secret_keys_and_authorization_header() -> None:
    text = "\n".join(
        [
            "X_BEARER_TOKEN=abc1234567890123456789012345678901234567890",
            "Authorization: Bearer secret-value",
            "normal line",
        ]
    )

    redacted = redact_text(text)

    assert "abc123" not in redacted
    assert "secret-value" not in redacted
    assert "[REDACTED]" in redacted
    assert "normal line" in redacted
