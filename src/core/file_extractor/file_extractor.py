import tempfile
from dataclasses import dataclass
from pathlib import Path

from injector import inject
from langchain_community.document_loaders import (
    TextLoader,
    UnstructuredCSVLoader,
    UnstructuredExcelLoader,
    UnstructuredFileLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    UnstructuredPDFLoader,
    UnstructuredPowerPointLoader,
    UnstructuredXMLLoader,
)
from langchain_community.tools import requests
from langchain_core.documents import Document as LCDocument

from src.model.upload_file import UploadFile
from src.service.cos_service import CosService


@inject
@dataclass
class FileExtractor:
    """文件提取器类，用于处理和提取各种格式文件的内容。

    该类支持从多种来源加载文件：
    - 从上传的文件对象加载
    - 从URL加载
    - 从本地文件路径加载

    支持的文件格式包括：
    - Excel (.xlsx, .xls)
    - PDF (.pdf)
    - Markdown (.md, .markdown)
    - HTML (.html, .htm)
    - CSV (.csv)
    - PowerPoint (.ppt, .pptx)
    - XML (.xml)
    - 其他文本文件

    可以选择使用结构化或非结构化的方式加载文件内容，
    并支持返回文档列表或纯文本格式。
    """

    cos_service: CosService

    def load(
        self,
        upload_file: UploadFile,
        *,
        return_text: bool = False,
        is_unstructured: bool = False,
    ) -> list[LCDocument] | str:
        """加载并处理上传的文件内容

        Args:
            upload_file: 上传的文件对象
            return_text: 是否返回纯文本格式，默认为False返回LCDocument列表
            is_unstructured: 是否使用非结构化加载器，默认为False

        Returns:
            list[LCDocument] | str: 根据return_text参数返回文档列表或纯文本

        """
        # 创建临时目录用于存储下载的文件
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 构建临时文件路径，保持原始文件名
            file_path = Path(tmp_dir) / Path(upload_file.key).name

            # 从COS服务下载文件到临时目录
            self.cos_service.download_file(upload_file.key, file_path)

            # 调用load_from_file方法处理文件内容
            return self.load_from_file(
                file_path,
                return_text=return_text,
                is_unstructured=is_unstructured,
            )

    @classmethod
    def load_from_url(
        cls,
        url: str,
        *,
        return_text: bool = False,
    ) -> list[LCDocument] | str:
        """从URL加载文件内容并解析为文档。

        Args:
            url (str): 文件的URL地址
            return_text (bool, optional): 是否返回纯文本格式。默认为False，
            返回LCDocument列表

        Returns:
            list[LCDocument] | str: 根据return_text参数返回文档列表或纯文本

        """
        # 发送HTTP请求获取文件内容
        response = requests.get(url)

        # 创建临时目录用于存储下载的文件
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 从URL中提取文件名并构建临时文件路径
            file_path = Path(tmp_dir) / Path(url).name
            # 将下载的内容写入临时文件
            with file_path.open("wb") as f:
                f.write(response.content)

            # 调用load_from_file方法处理文件内容
            return cls.load_from_file(file_path, return_text=return_text)

    @classmethod
    def load_from_file(
        cls,
        file_path: Path,
        *,
        return_text: bool = False,
        is_unstructured: bool = False,
    ) -> list[LCDocument] | str:
        """从文件路径加载文档内容

        Args:
            file_path (Path): 文件路径
            return_text (bool, optional): 是否返回纯文本内容. 默认为 False
            is_unstructured (bool, optional): 是否使用非结构化加载器. 默认为 False

        Returns:
            list[LCDocument] | str: 返回文档列表或纯文本内容

        """
        delimiter = "\n\n"  # 文档分隔符
        file_extension = Path(file_path).suffix.lower()  # 获取文件扩展名并转为小写

        # 根据文件扩展名选择对应的加载器
        if file_extension in [".xlsx", ".xls"]:
            loader = UnstructuredExcelLoader(file_path)
        elif file_extension == ".pdf":
            loader = UnstructuredPDFLoader(file_path)
        elif file_extension in [".md", ".markdown"]:
            loader = UnstructuredMarkdownLoader(file_path)
        elif file_extension in [".thm", "html"]:
            loader = UnstructuredHTMLLoader(file_path)
        elif file_extension == ".csv":
            loader = UnstructuredCSVLoader(file_path)
        elif file_extension in [".ppt", ".pptx"]:
            loader = UnstructuredPowerPointLoader(file_path)
        elif file_extension == ".xml":
            loader = UnstructuredXMLLoader(file_path)
        else:
            # 对于其他类型文件，根据is_unstructured参数选择加载器
            loader = (
                UnstructuredFileLoader(file_path)
                if is_unstructured
                else TextLoader(file_path)
            )

        # 根据return_text参数决定返回格式
        return (
            delimiter.join([document.page_content for document in loader.load()])
            if return_text
            else loader.load()
        )
