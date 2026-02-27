import dotenv
import weaviate
from langchain_openai import OpenAIEmbeddings
from langchain_weaviate import WeaviateVectorStore

dotenv.load_dotenv()

# 1.连接weaviate向量数据库
client = weaviate.connect_to_local("localhost", 8080)

# client = weaviate.connect_to_weaviate_cloud(
#     cluster_url="egqmx48kr5a2srw1uvjhxw.c0.asia-southeast1.gcp.weaviate.cloud",
#     auth_credentials=weaviate.classes.init.Auth.api_key(
#         "RDVTVFVnaG1aSkxhbTJlZ19leE1IY0E3elVGZEN4VEVTSzg2RHhHaWl0K01kK2JmQkRmZTBqOGNGd3NFPV92MjAw"),
# )

# 2.实例化WeaviateVectorStore
embedding = OpenAIEmbeddings(model="text-embedding-3-small")
db = WeaviateVectorStore(
    client=client,
    index_name="Dataset",
    text_key="text",
    embedding=embedding,
)

# 3.新增数据
# ids = db.add_texts(
#     [
#         "笨笨是一只很喜欢睡觉的猫咪",
#         "我喜欢在夜晚听音乐，这让我感到放松。",
#         "猫咪在窗台上打盹，看起来非常可爱。",
#         "学习新技能是每个人都应该追求的目标。",
#         "我最喜欢的食物是意大利面，尤其是番茄酱的那种。",
#         "昨晚我做了一个奇怪的梦，梦见自己在太空飞行。",
#         "我的手机突然关机了，让我有些焦虑。",
#         "阅读是我每天都会做的事情，我觉得很充实。",
#         "他们一起计划了一次周末的野餐，希望天气能好。",
#         "我的狗喜欢追逐球，看起来非常开心。",
#     ],
# )

try:
    # 4.检索数据
    print(db.similarity_search_with_score("笨笨"))
finally:
    client.close()
