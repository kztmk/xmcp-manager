import json

from xmcp_manager.account_store import (
    get_credentials_status,
    load_credentials_for_start,
    save_credentials,
)
from xmcp_manager.models import CredentialStatus


def test_save_credentials_create_and_update(monkeypatch) -> None:
    store: dict[tuple[str, str], str] = {}

    monkeypatch.setattr(
        "keyring.get_password", lambda service, account: store.get((service, account))
    )
    monkeypatch.setattr(
        "keyring.set_password",
        lambda service, account, password: store.__setitem__((service, account), password),
    )

    save_credentials(
        "account-id",
        {"consumerKey": "key", "consumerSecret": "secret", "bearerToken": "bearer"},
        mode="create",
    )
    save_credentials("account-id", {"bearerToken": "new-bearer"}, mode="update")

    credentials = load_credentials_for_start("account-id")
    raw = json.loads(store[("XMCP Manager", "account-id")])
    assert credentials.consumer_key == "key"
    assert credentials.consumer_secret == "secret"
    assert credentials.bearer_token == "new-bearer"
    assert raw["version"] == 1
    assert get_credentials_status("account-id") is CredentialStatus.OK
