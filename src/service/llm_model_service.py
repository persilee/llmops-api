import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import current_app
from injector import inject

from pkg.sqlalchemy import SQLAlchemy
from src.core.llm_model.entities.model_entity import BaseLanguageModel
from src.core.llm_model.llm_model_manager import LLMModelManager
from src.exception import NotFoundException
from src.lib.helper import convert_model_to_dict

from .base_service import BaseService

logger = logging.getLogger(__name__)


@inject
@dataclass
class LLMModelService(BaseService):
    """语言模型服务类，负责处理语言模型相关的业务逻辑。

    主要功能包括：
    1. 获取所有可用的语言模型列表
    2. 获取指定提供商的特定语言模型信息
    3. 获取语言模型提供商的图标
    4. 加载指定的语言模型
    5. 加载默认的语言模型
    """

    db: SQLAlchemy
    llm_model_manager: LLMModelManager

    def get_language_models(self) -> list[dict[str, Any]]:
        """获取LLMOps项目中的所有模型列表信息"""
        # 1.调用语言模型管理器获取提供商列表
        providers = self.llm_model_manager.get_providers()

        # 2.构建语言模型列表，循环读取数据
        language_models = []
        for provider in providers:
            # 3.获取提供商实体和模型实体列表
            provider_entity = provider.provider_entity
            model_entities = provider.get_model_entities()

            # 4.构建响应字典结构
            language_model = {
                "name": provider_entity.name,
                "position": provider.position,
                "label": provider_entity.label,
                "icon": provider_entity.icon,
                "description": provider_entity.description,
                "background": provider_entity.background,
                "support_model_types": provider_entity.supported_model_types,
                "models": convert_model_to_dict(model_entities),
            }
            language_models.append(language_model)

        return language_models

    def get_language_model(self, provider_name: str, model_name: str) -> dict[str, Any]:
        """根据传递的提供者名字+模型名字获取模型详细信息"""
        # 1.获取提供者+模型实体信息
        provider = self.llm_model_manager.get_provider(provider_name)
        if not provider:
            error_msg = f"该服务提供者不存在: {provider_name}"
            raise NotFoundException(error_msg)

        # 2.获取模型实体
        model_entity = provider.get_model_entity(model_name)
        if not model_entity:
            error_msg = f"该模型不存在: {model_name}"
            raise NotFoundException(error_msg)

        return convert_model_to_dict(model_entity)

    def get_language_model_icon(self, provider_name: str) -> tuple[bytes, str]:
        """根据传递的提供者名字获取提供商对应的图标信息"""
        # 1.获取提供者信息
        provider = self.llm_model_manager.get_provider(provider_name)
        if not provider:
            error_msg = f"该服务提供者不存在: {provider_name}"
            raise NotFoundException(error_msg)

        # 2.获取项目的根路径信息
        root_path = Path(current_app.root_path).parent.parent

        # 3.拼接得到提供者所在的文件夹
        provider_path = (
            root_path / "src" / "core" / "llm_model" / "providers" / provider_name
        )

        # 4.拼接得到icon对应的路径
        icon_path = provider_path / "_asset" / provider.provider_entity.icon

        # 5.检测icon是否存在
        if not icon_path.exists():
            error_msg = "该模型提供者_asset下未提供图标"
            raise NotFoundException(error_msg)

        # 6.读取icon的类型
        mimetype, _ = mimetypes.guess_type(icon_path)
        mimetype = mimetype or "application/octet-stream"

        # 7.读取icon的字节数据
        with icon_path.open("rb") as f:
            byte_data = f.read()
            return byte_data, mimetype

    def load_language_model(self, model_config: dict[str, Any]) -> BaseLanguageModel:
        """根据传递的模型配置加载大语言模型，并返回其实例"""
        try:
            # 1.从model_config中提取出provider、model、parameters
            provider_name = model_config.get("provider", "")
            model_name = model_config.get("model", "")
            parameters = model_config.get("parameters", {})

            # 2.从模型管理器获取提供者、模型实体、模型类
            provider = self.llm_model_manager.get_provider(provider_name)
            model_entity = provider.get_model_entity(model_name)
            model_class = provider.get_model_class(model_entity.model_type)

            # 3.实例化模型后并返回
            return model_class(
                **model_entity.attributes,
                **parameters,
                features=model_entity.features,
                metadata=model_entity.metadata,
            )
        except Exception as e:
            error_msg = f"加载模型失败: {e!s}"
            logger.exception(error_msg)
            return self.load_default_language_model()

    def load_default_language_model(self) -> BaseLanguageModel:
        """加载默认的大语言模型，在模型管理器中获取不到模型或者出错时使用默认模型进行兜底"""
        # 1.获取openai服务提供者与模型类
        provider = self.llm_model_manager.get_provider("openai")
        model_entity = provider.get_model_entity("gpt-4o-mini")
        model_class = provider.get_model_class(model_entity.model_type)

        # bug:原先写法使用的是LangChain封装的LLM类，
        # 需要替换成自定义封装的类，否则会识别到模型不存在features
        # return ChatOpenAI(model="gpt-4o-mini", temperature=1, max_tokens=8192)

        # 2.实例化模型并返回
        return model_class(
            **model_entity.attributes,
            temperature=1,
            max_tokens=8192,
            features=model_entity.features,
            metadata=model_entity.metadata,
        )
