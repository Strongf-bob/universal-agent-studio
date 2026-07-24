import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_browser_mutation_requires_matching_csrf(
    client: AsyncClient,
    bootstrapped_session: tuple[str, str],
) -> None:
    _, csrf_token = bootstrapped_session

    missing = await client.delete("/api/v1/session")
    wrong = await client.delete(
        "/api/v1/session",
        headers={"X-CSRF-Token": "wrong-token"},
    )
    accepted = await client.delete(
        "/api/v1/session",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert accepted.status_code == 204
    assert client.cookies.get("uas_session") is None
