from __future__ import annotations

from xmcp_manager import __version__
from xmcp_manager.models import AppSettings, McpClientId
from xmcp_manager.store_validation import (
    format_store_validation,
    is_store_build,
    run_store_validation,
    validation_is_current,
)


def test_is_store_build_reads_environment(monkeypatch) -> None:
    monkeypatch.delenv("XMCP_STORE_BUILD", raising=False)
    assert is_store_build() is False

    monkeypatch.setenv("XMCP_STORE_BUILD", "true")
    assert is_store_build() is True


def test_run_store_validation_populates_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        "xmcp_manager.store_validation.check_external_config_writable",
        lambda _: True,
    )
    monkeypatch.setattr("xmcp_manager.store_validation.check_loopback_available", lambda _: True)
    monkeypatch.setattr(
        "xmcp_manager.store_validation.check_credential_store_available",
        lambda: True,
    )
    monkeypatch.setattr("xmcp_manager.store_validation.check_user_data_writable", lambda: True)

    validation = run_store_validation(AppSettings())

    assert validation.app_version == __version__
    assert validation.external_config_writable[McpClientId.CLAUDE_DESKTOP.value] is True
    assert validation.external_config_writable[McpClientId.CODEX_DESKTOP.value] is True
    assert validation.loopback_available is True
    assert validation.credential_store_available is True
    assert validation.user_data_writable is True
    assert validation.validated_at is not None


def test_validation_current_and_format() -> None:
    settings = AppSettings()
    assert validation_is_current(settings) is False
    settings.store_validation.app_version = __version__
    assert validation_is_current(settings) is True
    text = format_store_validation(settings.store_validation)
    assert f"app version: {__version__}" in text
