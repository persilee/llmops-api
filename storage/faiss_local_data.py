import logging

import dotenv
from langchain_community.document_loaders import DirectoryLoader
from langchain_community.vectorstores.faiss import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

dotenv.load_dotenv()
logger.info("开始初始化向量数据库构建流程")
# 创建目录加载器，用于加载指定路径下的文档
# path: 指定要加载的目录路径
# glob: 使用通配符模式匹配文件，"[!.]*" 表示排除隐藏文件（以.开头的文件）
loader = DirectoryLoader(path="./storage/vector_store", glob="**/[!.]*")
logger.info("已创建目录加载器，准备从 ./storage/vector_store 加载文档")

# 创建文本分割器，用于将长文本分割成更小的块
# separators: 定义分割文本的优先级顺序，从上到下依次尝试
#   - 首先尝试按空行分割
#   - 然后尝试按换行符分割
#   - 然后尝试按中文标点符号分割
#   - 最后尝试按空格分割
# is_separator_regex: 标记分隔符是否为正则表达式
# chunk_size: 每个文本块的最大字符数
# chunk_overlap: 相邻文本块之间的重叠字符数，确保上下文的连续性
# add_start_index: 是否在元数据中添加每个块的起始位置
text_splitter = RecursiveCharacterTextSplitter(
    separators=[
        "\n\n",  # 空行
        "\n",  # 换行符
        "。|！|？",  # 中文句号、感叹号、问号
        r"\.\s|\!\s|\?\s",  # 英文句号、感叹号、问号（后跟空格）
        r"；|;\s",  # 中文分号或英文分号（后跟空格）
        r"，|,\s",  # 中文逗号或英文逗号（后跟空格）
        " ",  # 空格
        "",  # 如果以上都无法分割，则按字符分割
    ],
    is_separator_regex=True,
    chunk_size=500,
    chunk_overlap=50,
    add_start_index=True,
)
logger.info("已创建文本分割器，配置参数: chunk_size=500, chunk_overlap=50")

# 加载文档并进行分割
logger.info("开始加载文档并进行文本分割...")
# load_and_split会自动加载目录中的所有文档，并使用text_splitter进行分割
documents = loader.load_and_split(text_splitter)
logger.info("文档加载完成！共加载 %d 个文档块", len(documents))

# 创建FAISS向量数据库
logger.info(
    "开始创建FAISS向量数据库，使用OpenAI text-embedding-3-small模型进行向量化...",
)
# 使用OpenAI的embedding模型将文档转换为向量
# model="text-embedding-3-small" 是OpenAI提供的文本嵌入模型
db = FAISS.from_documents(
    documents=documents,
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)
logger.info("FAISS向量数据库创建完成！")

# 将向量数据库保存到本地
logger.info("正在保存向量数据库到本地...")
# folder_path: 保存目录路径
# index_name: 索引文件的名称（不包含扩展名）
db.save_local(folder_path="./src/core/vector_store", index_name="index")
logger.info("FAISS索引维度: %d", db.index.d)
logger.info("向量数据库已成功保存到 ./src/core/vector_store/index")
