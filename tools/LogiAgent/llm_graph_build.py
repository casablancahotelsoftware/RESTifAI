import json
import os
import random
import time
import argparse
import sys

import pydot

from rest_graph import RESTGraph, APINode
from swagger_helper import swagger_to_text
from autogen import ConversableAgent
from openai import OpenAI, AzureOpenAI
from dotenv import load_dotenv

import numpy as np

load_dotenv()

real_llm_call = 0

# Initialize OpenAI client
openai_raw_client = None

def init_openai_client():
    """Initialize OpenAI client"""
    global openai_raw_client
    if not openai_raw_client:
        if os.getenv("PROVIDER") == "azure":
            openai_raw_client = AzureOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_ENDPOINT"),
                api_version="2025-01-01-preview",
                timeout=60
            )
        else:
            openai_raw_client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                timeout=60
            )

def get_word_embedding(api_name, api_swagger) -> list[float]:
    """
    1. 先去本地文件系统查找是否有相同的 hash(api_name+api_swagger).embedding.file，有的话代表之前已经处理过了，可以直接用
      file format: {"api_name": "xxx", "api_swagger": "xxx", "embedding": [0.1, 0.2, 0.3, ...]}
    2. 若没有则调用openai embedding api
    :param api_name:
    :param api_swagger:
    :return: embedding array
    """
    hash_id = hash(api_name + api_swagger)
    embedding_file_name = f"./apis/openai_embedding/{hash_id}.embedding.json"
    if os.path.exists(embedding_file_name):
        print(f"find embedding file: for api_name: {api_name}")
        with open(embedding_file_name, "r") as f:
            embedding = json.load(f)
            return embedding["embedding"]
    else:
        # Call OpenAI embedding API
        init_openai_client()
        response = openai_raw_client.embeddings.create(
            input=api_name + api_swagger,
            model="text-embedding-3-small"
        )
        print(f"request openai api for embedding: {api_name}")
        embedding = response.data[0].embedding
        with open(embedding_file_name, "w") as f:
            json.dump({"api_name": api_name, "api_swagger": api_swagger, "embedding": embedding}, f)

        return embedding

def consine_similarity(v1, v2):
    """
    计算两个向量的余弦相似度, 使用numpy
    :param v1:
    :param v2:
    :return:
    """
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))


def have_relationship(api1_name, api1_swagger, api2_name, api2_swagger):
    # add similarity check before call llm
    embedding1 = get_word_embedding(api1_name, api1_swagger)
    embedding2 = get_word_embedding(api2_name, api2_swagger)
    similarity = consine_similarity(embedding1, embedding2)
    print(f"similarity: {similarity}")
    if similarity < 0.5:
        print(f"similarity is too low, skip llm call for {api1_name} and {api2_name} relationship check")
        return False
    else:
        global real_llm_call
        real_llm_call += 1
        print(f"{real_llm_call=} times llm call for relationship check")

    graph_build_prompt = f"""
Evaluate whether two REST APIs are highly related based on their Swagger documentation.

Consider the structural, functional, and semantic elements of each Swagger file to determine the relationship. Analyze components such as the endpoints, methods, parameters, request/response types, and overall purpose, looking for similarities or overlaps that suggest a close relationship between these APIs.

# Parameters for Evaluation:

- **Endpoints & Paths**: Compare similarities in endpoints, path names, and URI formats.
- **Request Methods**: Identify shared use of HTTP verbs (GET, POST, PUT, DELETE, etc.) for the same or similar paths.
- **Parameters**: Compare query, path, and body parameters for shared data fields, types, or formats.
- **Response Structure & Data Schema**: Identify similarities in the response structure (e.g. JSON schemas, data models).
- **Authentication & Security Schemes**: Observe whether both APIs use similar authentication methods (e.g., OAuth2, API keys).
- **Use Case or Purpose**: Determine whether both APIs serve a similar use case or function, described in descriptions or summaries.

# Steps to Follow:

1. **Compare Endpoints**: Extract the endpoints from both Swagger files. Identify overlap in naming/structure.
2. **Analyze Methods**: Cross-check whether similar endpoints use similar methods across the two APIs.
3. **Compare Parameters**: Evaluate the similarity of parameters in both APIs for matching endpoints.
4. **Evaluate Responses**: Compare the response structures and data types defined in responses.
5. **Assess Semantic Similarity**: Read through the descriptions and tags to understand how both APIs describe their functionality. 
6. **Result Decision**: Based on points 1-5, determine whether the two APIs are highly related.

# Output Format

Provide a detailed explanation about the similarities or differences found during the assessment, followed by a **Yes** or **No** answer regarding whether the APIs are highly related.

Explanation: [Provide a description explaining the reasons behind your determination, specifically mentioning similarities or differences found during the assessment in relevant parts.]

Related: True/False

# Examples

**Example 1**:

**Example API 1**:
- Name: `GET /users`
- Swagger Information: ...
    
**Example API 2**:
- Name: `GET /accounts`
- Swagger Information: ...

**Output**:

Explanation: The APIs are related because both deal with similar entities (users/accounts) and have similar endpoint and method. The intention seems to be to retrieve user information, suggesting these APIs serve similar purposes.
Related: True (Must is `Related: True` or `Related: False`)
"""

    real_api_info_prompt = f"""
**Swagger Information of 2 APIs**:

**API 1**: 
- **Name: {api1_name}**
- **Swagger Info:** {api1_swagger}

**API 2**: 
- **Name: {api2_name}**
- **Swagger Info:** {api2_swagger} 
"""

    init_openai_client()
    completion = openai_raw_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{'role': 'system', 'content': graph_build_prompt},
                  {'role': 'user', 'content': real_api_info_prompt}],
        seed=2048
    )

    result_json = completion.model_dump()
    result = result_json["choices"][0]["message"]["content"]  # type: str
    print(result)

    idx = result.find("Related")
    if idx > -1:
        related_result = result[idx:]
    else:
        related_result = result
    related_result = related_result.replace("**", '')

    if "Related: True" in related_result:
        return True
    elif "Related: False" in related_result:
        return False
    else:
        raise Exception("No Related bool values")


def generate_edge(config_summary):
    """Generate edges between APIs using the provided configuration"""
    edge_results = []

    rest_graph = RESTGraph(None,
                           swagger_path=config_summary['CONFIG_OPENAPI_JSON'],
                           base_url=config_summary['CONFIG_BASE_URL'])

    print(f"API cnt:{len(rest_graph.api_swagger_map.items())}")

    for i, (key, swagger_info) in enumerate(rest_graph.api_swagger_map.items()):
        body_schema_text = swagger_to_text(swagger_info)
        print(f"{i=} OUT API: {key}")
        inner_cnt = i + 1

        for key2, swagger_info2 in list(rest_graph.api_swagger_map.items())[i + 1:]:
            body_schema_text2 = swagger_to_text(swagger_info2)
            have = have_relationship(key, body_schema_text, key2, body_schema_text2)
            inner_cnt += 1
            print(f">>>>>>>>>>>>>>>>>>{inner_cnt=} Compare Result: {key} and {key2}. have_relationship:{have}")
            if have:
                edge_results.append([key, key2])

        print("================================================================================\n")

    with open(config_summary['CONFIG_EDGE_JSON_PATH'], "w") as f:
        f.write(json.dumps({"edge_results": edge_results}))


def generate_svg_graph(config_summary):
    """Generate SVG graph using the provided configuration"""
    rest_graph = RESTGraph(None,
                           swagger_path=config_summary['CONFIG_OPENAPI_JSON'],
                           base_url=config_summary['CONFIG_BASE_URL'],
                           edges_json_path=config_summary['CONFIG_EDGE_JSON_PATH'])
    rest_graph.generate_svg_graph(config_summary['CONFIG_EDGE_JSON_PATH']+".svg")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='LLM Graph Builder - Generate API relationship edges')

    parser.add_argument('--system-name', dest='system_name', type=str, required=True, help='System (service) name to analyze')
    parser.add_argument('--base-url', dest='base_url', type=str, required=True, help='Base URL for the REST API')
    parser.add_argument('--openapi-json', dest='openapi_json', type=str, help='Path to OpenAPI spec JSON (overrides derived path)')
    parser.add_argument('--edges-json', dest='edges_json', type=str, help='Path to edges.json (overrides derived path)')
    parser.add_argument('--generate-svg', dest='generate_svg', action='store_true', help='Also generate SVG graph visualization')
    
    return parser.parse_args()


if __name__ == '__main__':
    if os.getenv("OPENAI_API_KEY") is None:
        print("Please export OPENAI_API_KEY environment variable")
        sys.exit(1)

    args = parse_arguments()

    # Apply configuration using the global_vars_funcs_configs module
    config_summary = {
        'CONFIG_OPENAPI_JSON': args.openapi_json,
        'CONFIG_BASE_URL': args.base_url,
        'CONFIG_EDGE_JSON_PATH': args.edges_json
    }


    print(f"Config Applied: {config_summary}")
    
    # Ensure embedding directory exists
    embedding_dir = "./apis/openai_embedding"
    if not os.path.exists(embedding_dir):
        os.makedirs(embedding_dir, exist_ok=True)

    print("Generating edges...")
    generate_edge(config_summary)
    print(f"Edges saved to: {config_summary['CONFIG_EDGE_JSON_PATH']}")

    if args.generate_svg:
        print("Generating SVG graph...")
        generate_svg_graph(config_summary)
        print(f"SVG graph saved to: {config_summary['CONFIG_EDGE_JSON_PATH']}.svg")
