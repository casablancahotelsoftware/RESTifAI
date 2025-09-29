# RESTifAI FastMCP Server

## Features

1. **execute_all_tests(initialize_environment=True)**: Run all test suites
2. **execute_test_suite(test_suite_name, initialize_environment=True)**: Run specific suite
3. **get_all_test_suites()**: List suites with stats
4. **get_test_report(test_suite_name)**: Detailed suite report
5. **get_all_failure_reports()**: Consolidated failures
6. **get_test_suite_summary()**: Aggregated statistics

## Setup

### 1. Run MCP Server (Development Mode)

```bash
uv run mcp dev .\mcp_server.py
```

### 2. Configuration

To use a environment initalization script, set the config.py path:

```python
#Used for MCP server use only
ENVIRONMENT_INIT_SCRIPT="script.sh"
```