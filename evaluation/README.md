# Evaluation Tool

A lightweight tool to generate CSV reports from test results and JaCoCo coverage data for the Paper: **RESTifAI: LLM-Based Workflow for Reusable REST API Testing**

## Usage

### Basic Usage
```bash
python3 evaluation/evaluate.py --results-dir results --output results/evaluation.csv
```

## Output
The CSV contains metrics like test counts, error rates, execution time, and JaCoCo coverage (instruction, branch, line, method).