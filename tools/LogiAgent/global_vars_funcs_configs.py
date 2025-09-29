import os

from rest_graph import RESTGraph

# # ABLATION: No-Relevant-Parameter, No-Reflection
CONFIG_ABLATION = os.getenv('CONFIG_ABLATION')
ABLATION_NO_RELEVANT_PARAMETER = "No-Relevant-Parameter"
ABLATION_NO_REFLECTION = "No-Reflection"

CONFIG_SYSTEM_NAME = ""
CONFIG_OPENAPI_JSON = ""
CONFIG_BASE_URL = ""
CONFIG_LOG_PATH = ""
CONFIG_EDGE_JSON_PATH = ""

# ohsome
# CONFIG_SYSTEM_NAME = "ohsome"
# CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
# CONFIG_BASE_URL = "https://api.ohsome.org/v1"
# CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
# CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"

# # my-petstore
# CONFIG_SYSTEM_NAME = "my-petstore"
# CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
# CONFIG_BASE_URL = "https://petstore.swagger.io/v2"
# CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
# CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"


# genome-nexus
# CONFIG_SYSTEM_NAME = "genome-nexus"
# CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
# CONFIG_BASE_URL = "https://www.genomenexus.org"
# CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
# CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"
# 

# bills-api
# CONFIG_SYSTEM_NAME = "bills-api"
# CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
# CONFIG_BASE_URL = "https://bills-api.parliament.uk/api/v1"
# CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
# CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"
# 

# news
# CONFIG_SYSTEM_NAME = "news"
# CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
# CONFIG_BASE_URL = "http://127.0.0.1:50103"
# CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
# CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"
# 

# feature service
# CONFIG_SYSTEM_NAME = "feature"
# CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
# CONFIG_BASE_URL = "http://127.0.0.1:50100"
# CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
# CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"
# 

# scs
# CONFIG_SYSTEM_NAME = "scs"
# CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
# CONFIG_BASE_URL = "http://127.0.0.1:50108"
# CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
# CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"
# 

# restcountries
# CONFIG_SYSTEM_NAME = "restcountries"
# CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
# CONFIG_BASE_URL = "http://127.0.0.1:50106/rest"
# CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
# CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"
# 

# CONFIG_SYSTEM_NAME = "language-tool"
# CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
# CONFIG_BASE_URL = "http://127.0.0.1:49981/v2"
# CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
# CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"
# 

# ncs
# CONFIG_SYSTEM_NAME = "ncs"
# CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
# CONFIG_BASE_URL = "http://127.0.0.1:50102/api"
# CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
# CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"
# 

# person-controller
# CONFIG_SYSTEM_NAME = "person-controller"
# CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
# CONFIG_BASE_URL = "http://127.0.0.1:50111"
# CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
# CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"
# 

# project-track
# CONFIG_SYSTEM_NAME = "project-track"
# CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
# CONFIG_BASE_URL = "http://127.0.0.1:50118"
# CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
# CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"
# 

# user-management
# CONFIG_SYSTEM_NAME = "user-management"
# CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
# CONFIG_BASE_URL = "http://127.0.0.1:50115"
# CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
# CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"
# 

#######################################################################################################################


# def init_config_from_env():
#     global CONFIG_SYSTEM_NAME, CONFIG_OPENAPI_JSON, CONFIG_BASE_URL, CONFIG_LOG_PATH, CONFIG_EDGE_JSON_PATH

#     if os.getenv("CONFIG_SYSTEM_NAME") is not None and os.getenv("CONFIG_SYSTEM_NAME") != CONFIG_SYSTEM_NAME:
#         CONFIG_SYSTEM_NAME = os.getenv("CONFIG_SYSTEM_NAME")
#         CONFIG_OPENAPI_JSON = f'apis/{CONFIG_SYSTEM_NAME}/specifications/openapi.json'
#         CONFIG_LOG_PATH = f"./logs/{CONFIG_SYSTEM_NAME}"
#         CONFIG_EDGE_JSON_PATH = f"apis/{CONFIG_SYSTEM_NAME}/edges/edges.json"

#     if os.getenv("CONFIG_BASE_URL") is not None and os.getenv("CONFIG_BASE_URL")!= CONFIG_BASE_URL:
#         CONFIG_BASE_URL = os.getenv("CONFIG_BASE_URL")

#     if CONFIG_ABLATION is not None and CONFIG_ABLATION != "":
#         CONFIG_LOG_PATH = f"{CONFIG_LOG_PATH}/{CONFIG_ABLATION}"


# init_config_from_env()
# if not os.path.exists(CONFIG_LOG_PATH):
#     try:
#         os.makedirs(CONFIG_LOG_PATH)
#     except FileExistsError:
#         pass

# print(f"TestSystemInfo: {CONFIG_SYSTEM_NAME=} {CONFIG_BASE_URL=} {CONFIG_ABLATION=}")

# # rest_graph = RESTGraph(None,
# #                        swagger_path=CONFIG_OPENAPI_JSON,
# #                        base_url=CONFIG_BASE_URL,
# #                        edges_json_path=CONFIG_EDGE_JSON_PATH)

# # openai_raw_client = OpenAI(
# #     api_key=os.getenv("OPENAI_API_KEY"),
# #     timeout=60
# # )