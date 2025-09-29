# RESTifAI

We present RESTifAI, a LLM-workflow-based API testing tool whose novelty derives from automatically generating positive tests (happy paths), which confirm correct system behavior under valid inputs, and systematically deriving negative tests from these happy paths that validate robustness under invalid or unexpected conditions. 

RESTifAI provides two ways of interaction: using the CLI for automated usage and a frontend app for more interactive usage. When using the CLI option, tests are generated for all operations of the specification and automatically executed afterwards. Depending on the number of operations, length of the specification, and number of tests generated, automatic CLI execution may take several minutes.

## Setup

### LLM Provider

Create a `.env` file in the `tools/RESTifAI/` directory and configure:

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
```

### OpenAPI Specification

To generate API test cases for a service you need to add the OpenAPI specification file in `.json` or `.yaml` format into the `./specifications/` folder.

### Environment initialization scripts (optional)

To ensure independent test generation and execution, you can add custom scripts to the `./env_init_scripts/` folder. These scripts can be provided in the following formats: `.py, .ps1, .bat, .cmd, .sh`. 

These scripts should ensure, for example, that the database is set to a known state. The execution time of the script directly influences the generation and execution time of the test cases. Each time a happy path is generated or a test case gets executed via the tool, the script also gets executed.

If the service is initialized with pre-provisioned data, you can provide the tool with information about this data via the user input arguments to use this information for happy path generation. 

## Docker Usage (CLI only)

### Building the Docker Container

```bash
# Build the Docker image
docker compose build
```

### Running with Docker Compose

```bash
# Start the container
docker compose up -d

# Run test generation
docker compose exec restifai uv run python ./src/cli_scripts/generate_tests.py --help

# View logs
docker compose logs restifai

# Stop the container
docker compose down
```

## Without docker (CLI/GUI)

### Prerequisites
- **Python 3.11+**
- **Node.js** (for Newman CLI)

### Installation

1. **Install Newman CLI**
   ```bash
   npm install -g newman
   ```

2. **Setup Project**
   ```bash
   # Clone the repository (if not already done)
   # cd RESTifAI/tools/RESTifAI

   # create a virtual environment and activate it
   python3 -m venv venv
   source venv/bin/activate

   # Install required packages
   pip install -r requirements.txt
   ```

### GUI Application (Recommended)

```bash
python3 src/app.py
```

**Workflow:**
1. Configure base URL and set optional environment initialization script and user input
2. Load OpenAPI specification file
3. Select endpoints for testing and generate Structural and/or functional test cases
4. Execute tests
5. View results in reports tab

### CLI Scripts (For Automation)

```bash
python3 ./src/cli_scripts/generate_tests.py --help

# Complete test generation and execution
python3 ./src/cli_scripts/generate_tests.py -s specifications/openapi.json -u http://localhost:8080
# Or with optional environment setup script and optional user input
python3 ./src/cli_scripts/generate_tests.py -s specifications/openapi.json -u http://localhost:8080 -e env_init_scripts/env_init.sh -i "custom user input used for happy path generation"
```

### MCP Server

```bash
python3 ./src/mcp_server.py
```

## Project Configuration

The application uses a centralized configuration system via `config.py` for all folder paths and other static parameters.

To change default folder locations, modify `config.py`.

## Acknowledgments
This work was supported by and done within the scope of the ITEA4
GENIUS project, which was national funded by FFG with grant
921454.