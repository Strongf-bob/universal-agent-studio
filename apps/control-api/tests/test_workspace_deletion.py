import pytest
from conftest import MemoryAuthStore
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_workspace_deletion_requires_password_csrf_and_exact_confirmation(
    client: AsyncClient,
    bootstrapped_session: tuple[str, str],
    auth_store: MemoryAuthStore,
) -> None:
    _, csrf_token = bootstrapped_session
    assert auth_store.owner is not None
    workspace_id = auth_store.owner.workspace_id

    wrong_confirmation = await client.request(
        "DELETE",
        "/api/v1/workspace",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "current_password": "correct horse battery staple",
            "confirmation": "delete local workspace",
        },
    )
    wrong_password = await client.request(
        "DELETE",
        "/api/v1/workspace",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "current_password": "incorrect password value",
            "confirmation": "DELETE LOCAL WORKSPACE",
        },
    )
    accepted = await client.request(
        "DELETE",
        "/api/v1/workspace",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "current_password": "correct horse battery staple",
            "confirmation": "DELETE LOCAL WORKSPACE",
        },
    )

    assert wrong_confirmation.status_code == 400
    assert wrong_confirmation.json()["code"] == "confirmation_mismatch"
    assert wrong_password.status_code == 401
    assert wrong_password.json()["code"] == "authentication_failed"
    assert accepted.status_code == 204
    assert auth_store.deleted_workspace_id == workspace_id
    assert client.cookies.get("uas_session") is None
