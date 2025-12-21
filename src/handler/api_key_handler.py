from dataclasses import dataclass
from uuid import UUID

from flasgger import swag_from
from flask import request
from flask_login import current_user, login_required
from injector import inject

from pkg.paginator.paginator import PageModel, PaginatorReq
from pkg.response.response import (
    Response,
    success_json,
    success_message_json,
    validate_error_json,
)
from pkg.swagger.swagger import get_swagger_path
from src.router.redprint import route
from src.schemas.api_key_schema import (
    CreateApiKeyReq,
    GetApiKeysWithPageResp,
    UpdateApiKeyIsActiveReq,
    UpdateApiKeyReq,
)
from src.service.api_key_service import ApiKeyService


@inject
@dataclass
class ApiKeyHandler:
    """API Key处理器类

    负责处理所有与API Key相关的HTTP请求，包括：
    - 创建新的API Key
    - 删除现有的API Key
    - 更新API Key信息
    - 更新API Key的激活状态
    - 分页查询API Key列表
    """

    api_key_service: ApiKeyService

    @route("/create", methods=["POST"])
    @swag_from(
        get_swagger_path("api_key_handler/create_api_key.yaml"),
    )
    @login_required
    def create_api_key(self) -> Response:
        # 创建API Key请求验证对象
        req = CreateApiKeyReq()
        # 验证请求数据是否符合规范
        if not req.validate():
            # 如果验证失败，返回错误信息
            return validate_error_json(req.errors)

        # 调用服务层方法创建API Key
        self.api_key_service.create_api_key(req, current_user)

        # 返回创建成功的消息
        return success_message_json("创建API Key成功")

    @route("/<uuid:api_key_id>/delete", methods=["POST"])
    @swag_from(
        get_swagger_path("api_key_handler/delete_api_key.yaml"),
    )
    @login_required
    def delete_api_key(self, api_key_id: UUID) -> Response:
        """删除API Key

        Args:
            api_key_id (UUID): 要删除的API Key的ID

        Returns:
            Response: 包含成功消息的响应对象

        """
        self.api_key_service.delete_api_key(api_key_id, current_user)

        return success_message_json("删除API Key成功")

    @route("/<uuid:api_key_id>/update", methods=["POST"])
    @swag_from(
        get_swagger_path("api_key_handler/update_api_key.yaml"),
    )
    @login_required
    def update_api_key(self, api_key_id: UUID) -> Response:
        """更新API Key信息

        Args:
            api_key_id: 要更新的API Key的UUID

        Returns:
            Response: 包含更新结果的响应对象

        """
        # 创建请求数据验证对象
        req = UpdateApiKeyReq()
        # 验证请求数据是否有效
        if not req.validate():
            return validate_error_json(req.errors)

        # 调用服务层方法更新API Key信息
        self.api_key_service.update_api_key(api_key_id, current_user, **req.data)

        # 返回成功消息
        return success_message_json("更新API Key成功")

    @route("/<uuid:api_key_id>/update/active", methods=["POST"])
    @swag_from(
        get_swagger_path("api_key_handler/update_api_key_is_active.yaml"),
    )
    @login_required
    def update_api_key_is_active(self, api_key_id: UUID) -> Response:
        """更新API Key的启用状态

        Args:
            api_key_id (UUID): 要更新的API Key的ID

        Returns:
            Response: 包含操作结果的响应对象

        """
        # 创建请求数据验证对象
        req = UpdateApiKeyIsActiveReq()
        # 验证请求数据是否有效
        if not req.validate():
            # 如果验证失败，返回验证错误信息
            return validate_error_json(req.errors)

        # 调用服务层方法更新API Key状态
        self.api_key_service.update_api_key(api_key_id, current_user, **req.data)

        # 返回成功消息
        return success_message_json("更新API Key启用状态成功")

    @route("/keys", methods=["GET"])
    @swag_from(
        get_swagger_path("api_key_handler/get_api_keys_with_page.yaml"),
    )
    @login_required
    def get_api_keys_with_page(self) -> Response:
        """分页获取当前用户的 API 密钥列表

        Args:
            self: ApiKeyHandler 实例

        Returns:
            Response: 包含分页后的 API 密钥列表和分页信息的响应对象
                - list: API 密钥列表，每个密钥包含
                id、name、created_at、is_active 等信息
                - paginator: 分页信息，包含当前页、每页数量、总数量等

        Raises:
            ValidationError: 当分页参数验证失败时

        """
        req = PaginatorReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        api_keys, paginator = self.api_key_service.get_api_keys_with_page(
            req,
            current_user,
        )

        resp = GetApiKeysWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(api_keys), paginator=paginator))
