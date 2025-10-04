import pytest

from pkg.response import HttpCode


@pytest.mark.parametrize("query", [None, "你好，你是谁？"])
class TestAppHandler:
    def test_completion(self, query, client):
        response = client.post('/completion', json={
            "query": query
        })
        assert response.status_code == 200
        if query is None:
            assert response.json.get('code') == HttpCode.VALIDATE_ERROR
        else:
            assert response.json.get('code') == HttpCode.SUCCESS
