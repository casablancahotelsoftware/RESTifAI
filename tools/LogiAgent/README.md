# LogiAgent

Modification of the Replication Package for paper: LogiAgent: Automated Logical Testing for REST Systems with LLM-Based Multi-Agents


# 1. QuickStart

## Environment Setup

Python Version: 3.9

To use OpenAI models set the following variables:
```env
OPENAI_API_KEY="your_api_key_here"
OPENAI_MODEL_NAME="gpt-4.1-mini"
```

For Azure OpenAI models set these variables:
```env
# Or AzureOpenAI Configuration
AZURE_OPENAI_API_KEY="your_api_key_here"
AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT="gpt-4.1-mini"
AZURE_OPENAI_API_VERSION="2025-01-01-preview"
## Run the Agent

```bash
pip install -r requirements.txt
python logi_agent.py --system-name "SERVICE" --base-url "URL" --max-time TIME
```

### Command-line arguments

These file path needs to be set before execution `apis/{system-name}/specifications/openapi.json` and `apis/{system-name}/edges/edges.json`

- --system-name: Logical service name. If --openapi-json/--edge-json aren’t provided, defaults to:
  - apis/{system-name}/specifications/openapi.json
  - apis/{system-name}/edges/edges.json
- --base-url: Base URL of the target REST API (e.g., https://api.example.com or http://localhost:8080).
- --openapi-json: Path to OpenAPI spec (override default).
- --edge-json: Path to generated edges.json (override default).
- --log-path: Directory to store logs (default: ./logs).
- --max-time: Max execution time in seconds (default: 120).

Note: Ensure edges.json is generated first (see "Generate Edges" below).

### Examples for different services

- Local Petstore (defaults paths by system-name):
```bash
python logi_agent.py \
  --system-name petstore \
  --base-url http://localhost:8080
```

### 2. Generate Edges
Generate potential relationship edges between APIs based on openapi.json, stored in the `edges` subdirectory.

Open `llm_graph_build.py` and run the `generate_edge` function to generate `edges.json` at the location specified by `CONFIG_EDGE_JSON_PATH`.

### 3. Test Results
Test results are generated as JSON files at the location specified by CONFIG_LOG_PATH, recording the execution of each test scenario.

The result file contains:

* `all_cnt`: Total number of requests sent during testing
* `all_request_sequence`: Array recording all sent request information in sequence
* `right_results`: Array containing all correct response results
* `wrong_results`: Array containing all incorrect response results
* `test_scenario_response_message`: Description of the current test scenario

Example:
```json
{
    "all_cnt": 4,
    "all_request_sequence": [...],
    "right_results": [...],
    "wrong_results": [...],
    "test_scenario_response_message": "**Test Scenario: ..."
}
```


