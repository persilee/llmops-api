import pytest

from pkg.response import HttpCode
from pkg.response.http_code import HTTP_STATUS_OK


@pytest.mark.parametrize(
    ("app_id", "query"),
    [
        ("9495d2e2-2e7a-4484-8447-03f6b24627f7", None),
        ("9495d2e2-2e7a-4484-8447-03f6b24627f7", "你好，你是谁？"),
    ],
)
class TestAppHandler:
    def test_completion(self, app_id, query, client) -> None:
        response = client.post(
            f"/apps/{app_id}/debug",
            json={
                "query": query,
            },
        )
        assert response.status_code == HTTP_STATUS_OK, (
            f"Expected status code {HTTP_STATUS_OK}, got {response.status_code}"
        )
        if query is None:
            assert response.json.get("code") == HttpCode.VALIDATE_ERROR, (
                f"Expected validation error code, got {response.json.get('code')}"
            )
        else:
            assert response.json.get("code") == HttpCode.SUCCESS, (
                f"Expected success code, got {response.json.get('code')}"
            )
