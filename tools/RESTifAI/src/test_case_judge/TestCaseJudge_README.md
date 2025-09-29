# TestCaseJudge - AI-Powered Test Case Classification

The `TestCaseJudge` uses an LLM to classify failed test cases as either **True Positive** (legitimate failures indicating bugs in the System Under Test) or **False Positive** (incorrectly designed test cases).

## Configuration

Set up judge-specific environment variables (separate from main LLM):

```bash
# Judge LLM Configuration
JUDGE_AZURE_OPENAI_API_KEY=your_judge_api_key
JUDGE_AZURE_OPENAI_ENDPOINT=your_judge_endpoint
JUDGE_AZURE_OPENAI_API_VERSION=your_api_version
JUDGE_AZURE_OPENAI_DEPLOYMENT_NAME=your_judge_model_deployment
```

## Usage

Execute the `judge_results.py` script to classify all executed test cases. The data in the `test_data` folder cobines test data and execution data of every test case and is used for the evaluation.

```bash
python judge_results.py
```

Results will be stored in the `components` folder for every execution of the judge script.
