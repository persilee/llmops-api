import pytest

from pkg.response.http_code import HTTP_STATUS_OK, HttpCode


class TestBuiltinToolHandler:
    """内置工具处理器测试类"""

    def test_get_categories(self, client) -> None:
        """测试获取内置工具分类"""
        resp = client.get("/builtin-tools/categories")
        assert resp.status_code == HTTP_STATUS_OK
        assert resp.json.get("code") == HttpCode.SUCCESS
        assert len(resp.json.get("data")) > 0

    def test_get_builtin_tools(self, client) -> None:
        """测试获取内置工具"""
        resp = client.get("/builtin-tools/")
        assert resp.status_code == HTTP_STATUS_OK
        assert resp.json.get("code") == HttpCode.SUCCESS
        assert len(resp.json.get("data")) > 0

    @pytest.mark.parametrize(
        ("provider_name", "tool_name"),
        [("google", "google_serper"), ("bing", "bing_search")],
    )
    def test_get_provider_tool(self, provider_name, tool_name, client) -> None:
        """测试获取指定提供者工具"""
        resp = client.get(f"/builtin-tools/{provider_name}/tools/{tool_name}")
        assert resp.status_code == HTTP_STATUS_OK
        if provider_name == "google":
            assert resp.json.get("code") == HttpCode.SUCCESS
            assert len(resp.json.get("data")) > 0
            assert resp.json.get("data").get("name") == tool_name
        elif provider_name == "bing":
            assert resp.json.get("code") == HttpCode.NOT_FOUND

    @pytest.mark.parametrize("provider_name", ["google", "bing"])
    def test_get_provider_icon(self, provider_name, client) -> None:
        """测试获取指定提供者图标"""
        resp = client.get(f"/builtin-tools/{provider_name}/icon")
        assert resp.status_code == HTTP_STATUS_OK
        if provider_name == "google":
            assert resp.content_type == "image/svg+xml; charset=utf-8"
            assert resp.data is not None
        elif provider_name == "bing":
            assert resp.json.get("code") == HttpCode.NOT_FOUND
