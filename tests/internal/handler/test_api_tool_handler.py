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

    def test_delete_api_tool_provider(self, client, db) -> None:
        provider_id = "8d256a05-827f-4c45-be00-0f77d7e55d48"
        resp = client.post(f"/api-tools/{provider_id}/delete")
        assert resp.status_code == HTTP_STATUS_OK

        from src.model import ApiToolProvider

        api_tool_provider = db.session.query(ApiToolProvider).get(provider_id)
        assert api_tool_provider is None

    @pytest.mark.parametrize(
        "query",
        [
            {},
            {"current_page": 2},
            {"search_word": "高德"},
            {"search_word": "google"},
        ],
    )
    def test_get_api_tool_providers_with_page(self, query, client) -> None:
        resp = client.get("/api-tools", query_string=query)
        assert resp.status_code == HTTP_STATUS_OK
        if query.get("current_page") == 2 or query.get("search_word") == "高德":  # noqa: PLR2004
            assert len(resp.json.get("data").get("list")) == 0
        elif query.get("search_word") == "google":
            assert len(resp.json.get("data").get("list")) == 1
        else:
            assert resp.json.get("code") == HttpCode.SUCCESS

    @pytest.mark.parametrize(
        "provider_id",
        [
            "6aa64a60-014b-473b-89d3-4005ac0a825c",
            "3944eee4-9d5a-4ca5-91c1-e56654cbc1e5",
        ],
    )
    def test_get_api_tool_provider(self, provider_id, client) -> None:
        resp = client.get(f"/api-tools/get-api-tool-provider/{provider_id}")
        assert resp.status_code == HTTP_STATUS_OK
        if provider_id.endswith("c"):
            assert resp.json.get("code") == HttpCode.SUCCESS
        elif provider_id.endswith("5"):
            assert resp.json.get("code") == HttpCode.NOT_FOUND

    @pytest.mark.parametrize(
        ("provider_id", "tool_name"),
        [
            ("6aa64a60-014b-473b-89d3-4005ac0a825c", "get_position"),
            ("6aa64a60-014b-473b-89d3-4005ac0a825c", "test"),
        ],
    )
    def test_get_api_tool(self, provider_id, tool_name, client) -> None:
        resp = client.get(f"/api-tools/get-api-tool/{provider_id}/tools/{tool_name}")
        assert resp.status_code == HTTP_STATUS_OK
        if tool_name == "get_position":
            assert resp.json.get("code") == HttpCode.SUCCESS
        elif tool_name == "test":
            assert resp.json.get("code") == HttpCode.NOT_FOUND

    def test_create_api_tool_provider(self, client, db) -> None:
        data = {
            "name": "test工具包",
            "icon": "https://test.com/icon.png",
            "openapi_schema": '{"description":"查询ip所在地、天气预报、路线规划等高德工具包","server":"https://gaode.example.com","paths":{"/weather":{"get":{"description":"根据传递的城市名获取指定城市的天气预报，例如：广州","operationId":"GetCurrentWeather","parameters":[{"name":"location","in":"query","description":"需要查询天气预报的城市名","required":true,"type":"str"}]}},"/ip":{"post":{"description":"根据传递的ip查询ip归属地","operationId":"GetCurrentIp","parameters":[{"name":"ip","in":"request_body","description":"需要查询所在地的标准ip地址，例如:201.52.14.23","required":true,"type":"str"}]}}}}',
            "headers": [{"key": "Authorization", "value": "Bearer access_token"}],
        }
        resp = client.post("/api-tools/create-api-tool-provider", json=data)
        assert resp.status_code == HTTP_STATUS_OK

        from src.model import ApiToolProvider

        api_tool_provider = (
            db.session.query(ApiToolProvider).filter_by(name="test工具包").one_or_none()
        )
        assert api_tool_provider is not None

    def test_update_api_tool_provider(self, client, db) -> None:
        provider_id = "6aa64a60-014b-473b-89d3-4005ac0a825c"
        data = {
            "name": "test工具包",
            "icon": "https://test.com/icon.png",
            "openapi_schema": '{"description":"查询ip所在地、天气预报、路线规划等高德工具包","server":"https://gaode.example.com","paths":{"/weather":{"get":{"description":"根据传递的城市名获取指定城市的天气预报，例如：广州","operationId":"GetCurrentWeather","parameters":[{"name":"location","in":"query","description":"需要查询天气预报的城市名","required":true,"type":"str"}]}},"/ip":{"post":{"description":"根据传递的ip查询ip归属地","operationId":"GetLocationForIp","parameters":[{"name":"ip","in":"request_body","description":"需要查询所在地的标准ip地址，例如:201.52.14.23","required":true,"type":"str"}]}}}}',
            "headers": [{"key": "Authorization", "value": "Bearer access_token"}],
        }
        resp = client.post(f"/api-tools/{provider_id}", json=data)
        assert resp.status_code == HTTP_STATUS_OK

        from src.model import ApiToolProvider

        api_tool_provider = db.session.get(ApiToolProvider, provider_id)
        assert api_tool_provider.name == data.get("name")
