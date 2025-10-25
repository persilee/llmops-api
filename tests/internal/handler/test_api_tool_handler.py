import pytest

from pkg.response.http_code import HTTP_STATUS_OK, HttpCode

openapi_schema_str = """
{
  "server": "https://baidu.com",
  "description": "123",
  "paths": {
    "/location": {
      "get": {
        "description": "获取本地位置",
        "operationId": "xxx",
        "parameters": [
          {
            "name": "location",
            "in": "query",
            "description": "参数描述",
            "required": "true",
            "type": "str"
          }
        ]
      }
    }
  }
}
"""


class TestApiToolHandler:
    @pytest.mark.parametrize(
        "openapi_schema",
        ["openapi_schema.json", openapi_schema_str],
    )
    def test_validate_openapi_schema(self, openapi_schema, client) -> None:
        resp = client.post(
            "/api-tools/validate-openapi-schema",
            json={"openapi_schema": openapi_schema},
        )
        assert resp.status_code == HTTP_STATUS_OK
        if openapi_schema == "openapi_schema.json":
            assert resp.json.get("code") == HttpCode.VALIDATE_ERROR
        elif openapi_schema == openapi_schema_str:
            assert resp.json.get("code") == HttpCode.SUCCESS
