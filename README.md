# Replication Package for RESTifAI: LLM-Based Workflow for Reusable REST API Testing

This replication package provides the necessary infrastructure for conducting evaluations of **RESTifAI** against existing state-of-the-art LLM-powered REST API testing approaches. The package enables reproducible comparative analysis across multiple service configurations, including both locally deployed and remotely hosted APIs.

**If you just want to use RESTifAI by itself:** [run the frontend app](#restifai-frontend-application) or navigate to the [RESTifAI](tools/RESTifAI/README.md) directory for a more detailed introduction:

```bash
cd ./tools/RESTifAI/
```

Watch the following demonstration video for a quick introduction to RESTifAI's capabilities, setup, configuration, and a running use case example:

<p align="center">
  <a href="https://www.youtube.com/watch?v=2vtQo0T0Lo4">
    <img src="https://img.youtube.com/vi/2vtQo0T0Lo4/maxresdefault.jpg" alt="RESTifAI Demo Video" width="560">
  </a>
</p>

The license applies to `./tools/RESTifAI/`. 

## Available Tools

- **RESTifAI** (`RESTifAI`): A LLM-based REST API testing framework designed to generate reusable and executable production-ready test suites. The approach validates OpenAPI specifications through structural conformance testing and verifying business logic scenarios through functional test case generation.

- **AutoRestTest** (`AutoRestTest`): A mutation-based API testing methodology that leverages LLM-generated request values combined with reinforcement learning techniques to maximize the detection of unique HTTP 500 server errors and successful 2xx responses across distinct API operations.  
  *Reference*: https://doi.org/10.48550/arXiv.2501.08600  
  *Repository*: https://github.com/selab-gatech/AutoRestTest/

- **LogiAgent** (`LogiAgent`): A multi-agent framework-based approach that autonomously generates ad-hoc logical test scenarios designed to validate the semantic business logic constraints of REST API implementations.  
  *Reference*: https://doi.org/10.48550/arXiv.2503.15079  
  *Repository*: https://anonymous.4open.science/r/LogiAgent-5055/README.md

## Evaluation Dataset: API Services

The experimental evaluation encompasses five diverse REST API services, selected to represent varying complexity levels and domain-specific characteristics:

#### Locally Deployed Services

- **genome-nexus**: A bioinformatics service providing genomic variant annotation capabilities  
  *Source*: https://github.com/genome-nexus/genome-nexus
- **language-tool**: A natural language processing service offering grammar and linguistic analysis  
  *Source*: https://github.com/languagetool-org/languagetool  
- **rest-countries**: A geographical information service providing country-specific metadata  
  *Source*: https://github.com/apilayer/restcountries

#### Remotely Hosted Services

- **fdic**: Federal Deposit Insurance Corporation banking institution data service  
  *Documentation*: https://api.fdic.gov/banks/docs/
- **ohsome**: OpenStreetMap geospatial data analysis and statistics service  
  *Documentation*: https://docs.ohsome.org/ohsome-api/v1/

## Quick Start

### 1. Configure LLM Credentials

Create a `.env` file in each tool directory (`tools/<tool>/.env`). You can use either a OpenAI API key or a AzureOpenAI API key. For reference you can see the `.env.example` file available in each tools folder:

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

### 2. Setup Environment

Run the following command to install all necessary packages, set up local services, and build the Docker containers for the tools. This process may take several minutes. Make sure you have root privileges when executing the scripts:

```bash
./setup.sh
```

## Run Tool Evaluation

Usage: `./run.sh --tool <tool> --service <service> --time <time in seconds>`

```bash
# RESTifAI evaluation
./run.sh --tool RESTifAI --service language-tool

# AutoRestTest evaluation with time constraint
./run.sh --tool AutoRestTest --service language-tool --time XY

# LogiAgent evaluation with time constraint
./run.sh --tool LogiAgent --service language-tool --time XY
```
**Time Parameter Configuration**: RESTifAI operates differently from other tools in that it does not accept a time
constraint parameter. Instead, it executes until test cases are generated for all operations defined in the OpenAPI
specification. The total execution time is recorded and returned upon completion. This measured execution time should be
used as the time constraint (`XY` seconds) for AutoRestTest and LogiAgent evaluations to ensure fair comparison across
all tools. The time can be taken from the generated `results.json` file in the `results/<service>/RESTifAI/` folder.

**Empirical Execution Times**: The following execution times (in seconds) were measured during RESTifAI evaluation and used as temporal constraints for comparative tool assessment:

| Service | Execution Time (seconds) |
|---------|---------------------------|
| fdic | 580 |
| genome-nexus | 791 |
| language-tool | 66 |
| ohsome | 7714 |
| rest-countries | 362 |

**Limitation of Time-Based Comparision**
The execution time of the tools can be influenced by external dependencies. These include factors such as the token generation rate (tokens per second) provided by the LLM providers, delays caused by network latency (online-service) or under high-load conditions of the service. 
As future work, it would be valuable to explore strategies for mitigating these limitations.  

**⚠️ Important Note for OhSome Service**: When evaluating the `ohsome` service with `RESTifAI`, due to the extensive
size of the OpenAPI specification, it may be necessary to reduce the `MAX_WORKERS` parameter in the
`tools/RESTifAI/config.py` file from the default value of 10 to a lower value (e.g., 5 or fewer). This
adjustment helps prevent rate limiting and token limit violations from the LLM provider during concurrent request
processing. In our evaluation we set the `MAX_WORKERS` to 5 for the `ohsome` service and 10 for every other service.

**Cost of LLM Invocation**
The cost of usage depends on the size of the OpenAPI specification, and the number of operations and their complexity (correlates with the number of generated test cases). While the total cost of test generation for the `language-tool` service is approximately $0.05 (about 35 test cases), the total cost of test generation for the `ohsome` service is about $28.00 (more than 2200 test cases), using the gpt-4.1-mini LLM.     

### Access Results

<!-- Add a short description of the evaluation results -->
<!-- Add a definition for the metrics e.g what is total cost -> number tokens, Euro, .... -->
<!-- Provide more details about where everything can be found -->
<!-- Provide a folder with all the outcomes of our tests and analysis e.g with jupyster notebooks / csv files -->

Upon completion of each evaluation, the framework generates structured results in the `results/` directory following the
pattern `results/[service-name]/[tool-name]/`. Each evaluation produces:

- **Tool-specific outputs**: Generated test cases, execution logs, and tool-native result formats
- **Standardized metrics**: A `results.json` file containing normalized performance metrics across all tools
- **Code coverage data**: JaCoCo coverage reports (for local services only)

Each tool reports the following metrics:

- **Successful Operation Coverage**: Number of distinct API operations successfully exercised through generated test cases
- **Error Discovery Rate**: Quantity of unique server-side errors (HTTP 5xx responses) identified during test execution
- **Economic Cost**: Total expenditure for LLM inference measured in USD, derived from token consumption and provider pricing models
- **Token Utilization**: Aggregate number of tokens consumed across all LLM interactions (input + output tokens)

`RESTifAI` and `LogiAgent` also include the following additional metrics in the result file:

- **Total Tests**: Number of generated test cases
- **Failed Tests**: Number of failed test cases

To generate a CSV table containing all the generated results including coverage statistics, refer to the `evaluation` folder.

## RESTifAI Frontend Application

While the CLI script provides fully automated test generation and execution, the intuitive RESTifAI frontend offers enhanced control and flexibility for test generation, execution, and review processes, making it more suitable for practical real-world applications. To launch the RESTifAI frontend interface, execute the following commands:

```bash
./run_restifai_app.sh
```

**Prerequisites**: Ensure that the `.env` configuration file is properly configured in the `tools/RESTifAI/` directory and that the OpenAPI specification of the target service is available in the `tools/RESTifAI/specifications/` folder. Make sure you have root privileges when executing the script.


## Repository Modifications for Benchmarking
To adapt the original implemenation of the tools for our benchmarking setup, small changes were made. The LogiAgent and AutoRestTest was modified to be compatible with Azure OpenAI endpoints and to support time-based execution. For LogiAgent we additiaonally enhanced to be configurable via the command-line interface (CLI), allowing for easier parameter adjustments and automated testing in our test-framework. 

During the execution of LogiAgent, occasional 500 errors were encountered. These errors were traced back to a bug in the underlying multi-agent system used by LogiAgent. To handle this issue gracefully, we added a try-catch block to prevent the system from failing completely and to allow for continued execution where possible.



---

**Happy testing! 🚀**

## Acknowledgments
This work was supported by and done within the scope of the ITEA4
GENIUS project, which was national funded by FFG with grant
921454.
