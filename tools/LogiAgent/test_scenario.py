import random
import string
import os

import tools
import utils.bm25_retriver
from swagger_helper import swagger_to_text

# Global variables for configuration
_rest_graph = None
_config_ablation = os.getenv('CONFIG_ABLATION')

# Ablation constants
ABLATION_NO_RELEVANT_PARAMETER = "No-Relevant-Parameter"
ABLATION_NO_REFLECTION = "No-Reflection"

def set_rest_graph(rest_graph):
    """Set the REST graph instance to be used by functions in this module"""
    global _rest_graph
    _rest_graph = rest_graph


def record_test_scenario(summary: str, api_sequence: list) -> str:
    global generated_test_scenarios
    generated_test_scenarios.append({
        "summary": summary,
        "api_sequence": api_sequence
    })

    if len(generated_test_scenarios) > 10:
        generated_test_scenarios = generated_test_scenarios[1:]

    return "record test_scenario success"


def record_test_scenario_result_summary(result_summary: str) -> str:
    global generated_test_scenarios
    generated_test_scenarios[-1]["result_summary"] = result_summary
    return "record current_scenario_result_summary success"


def get_previous_all_test_scenarios_for_llm() -> str:
    """
    Generate a textual representation of all previous test scenarios
    in an LLM-friendly format.
    """

    global generated_test_scenarios

    if not generated_test_scenarios or len(generated_test_scenarios) == 0:
        return "No test scenarios have been recorded yet."

    description = "Here are the previous generated test scenarios:\n"
    for idx, scenario in enumerate(generated_test_scenarios, 1):
        description += (
            f"Scenario {idx}:\n"
            f"  **Summary**: {scenario['summary']}\n"
            f"  **API Sequence**: {', '.join(scenario['api_sequence'])}\n"
        )

        if scenario.get("result_summary"):
            description += f"  **Execution Result Summary**: {scenario['result_summary']}\n"

    return description


def reset_useful_items():
    global useful_items
    useful_items = {}


def get_swagger_info_by_api_endpoint(api_endpoint: str) -> str:
    api_endpoint = api_endpoint.replace("{{", "{")
    api_endpoint = api_endpoint.replace("}}", "}")

    if not _rest_graph:
        return "No REST graph available"
    
    swagger_info = _rest_graph.api_swagger_map.get(api_endpoint)
    if swagger_info:
        text_info = swagger_to_text(swagger_info)
        text_info = f"Endpoint: {api_endpoint}\n" + text_info
        return text_info
    else:
        return "No Swagger Info"


class TestCase:
    def __init__(self, title: str, api_endpoint: str, description: str, expected_resp: str):
        self.title = title
        self.api_endpoint = api_endpoint
        self.description = description
        self.expected_resp = expected_resp
        self.swagger_info = get_swagger_info_by_api_endpoint(api_endpoint)

    def __repr__(self):
        return f"""**TestCase**:{self.title}
**API Endpoint**:{self.api_endpoint}
**Test Description**:{self.description}
**Expected Response**:{self.expected_resp}
**Swagger API Info**:{self.swagger_info}
"""

    def __str__(self):
        return self.__repr__()


class TestScenario:
    def __init__(self, scenario_text=""):
        self.scenario_text = scenario_text
        self.todo_tests = []
        self.todo_resps = []


def add_test_case(test_case_title: str, api_endpoint: str, description: str, expected_resp: str) -> str:
    global scenario
    try:
        test_case = TestCase(test_case_title, api_endpoint, description, expected_resp)
        scenario.todo_tests.append(test_case)
        print(f"ADD CASE: there are {len(scenario.todo_tests)} test cases now.")
        return "success"
    except Exception as e:
        return f"exception: {e}"


def add_test_case_object(test_case: TestCase, idx=0):
    if type(test_case) == TestCase:
        scenario.todo_tests.insert(idx, test_case)
        print(f"ADD CASE: add_test_case_object {idx=} {test_case.title=} there are {len(scenario.todo_tests)} test cases now.")


def get_next_test_case() -> str:
    global scenario, current_test_case

    if len(scenario.todo_tests) == 0:
        return "No more test case"
    else:
        tc = scenario.todo_tests[0]  # type: TestCase
        current_test_case = tc
        print(f"current_test_case changed: {current_test_case.title}")

        tc_info = tc.__repr__()
        useful_item_text = convert_useful_items_to_text()
        if type(useful_item_text) == str and len(useful_item_text) > 0:
            useful_item_text = utils.bm25_retriver.bm25_filter_useful_items(useful_item_text, tc_info)
            tc_info = "\nUseful Information returned by previous REST API:\n" + useful_item_text + "\n\n" + "Test Case Info:" +  tc_info

        reflect_info = get_api_reflections_for_llm(tc.api_endpoint)
        if reflect_info:
            tc_info = tc_info + "\nReflection info for this API:\n" + reflect_info

        return tc_info


def add_next_response_for_validation(item):
    global scenario
    scenario.todo_resps.append(item)
    print(f"ADD RESP: there are {len(scenario.todo_resps)} responses")


def get_next_response_for_validation() -> str:
    """
    :return:
    """
    global scenario

    if len(scenario.todo_resps) > 0:
        item = scenario.todo_resps[0]

        result = ""
        if current_test_case is not None:
            result += "Current Validate Test Case:\n"
            result += current_test_case.__repr__()

        result += f"\nAPI Execution Result:"
        result += f"\tRequest:{item.get('request_data')}\n"
        result += f"\tResponse Code:{item.get('response_code')}\n"
        result += f"\tResponse Data:{item.get('response_data')[:1000] if len(str(item.get('response_data'))) > 1000 else item.get('response_data')}\n"

        return result
    else:
        return "no available response"



def record_useful_items(items: dict) -> str:
    global useful_items  # type: dict[str, list]

    def process_nested(prefix: str, data: dict) -> None:
        for key, value in data.items():
            current_path = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                if "value" in value and "description" in value:
                    # This is a leaf node with value and description
                    process_single_item(current_path, value)
                else:
                    # This is a nested dictionary
                    process_nested(current_path, value)
            elif isinstance(value, list):
                # Handle list of dictionaries
                for item in value:
                    if isinstance(item, dict):
                        process_nested(current_path, item)

    def process_single_item(name: str, details: dict) -> None:
        """Helper function to process a single item with value and description"""
        value = details.get('value')
        description = details.get('description', '')

        if name not in useful_items:
            useful_items[name] = []

        existing_entry = next((entry for entry in useful_items[name] if entry['value'] == value), None)

        if existing_entry:
            existing_entry['description'] = description
        else:
            if len(str(useful_items[name])) <= 500 and len(str(value) + str(description)) <= 500:
                useful_items[name].append({
                    'value': value,
                    'description': description
                })

            if len(useful_items[name]) > 5:
                useful_items[name].pop(0)

    # Start processing from root
    process_nested("", items)
    return "finished record_useful_items"


def convert_useful_items_to_text():
    if _config_ablation == ABLATION_NO_RELEVANT_PARAMETER:
        print(f"{_config_ablation=}, no relevant parameters")
        return None

    global useful_items  # type: dict[str: list]

    if len(useful_items) > 0:
        descriptions = []

        for name, values in useful_items.items():
            value_descriptions = []

            for item in values:
                value = item.get('value', '')
                description = item.get('description', '')
                value_descriptions.append(f"Value: {value}, Description: {description}")

            descriptions.append(f"The param '{name}' previous returned values: " + "; ".join(value_descriptions))

        return "\n".join(descriptions)
    else:
        return None


def record_api_reflections(api_endpoint: str, issue_title: str, issue_detail: str) -> str:
    global api_reflections

    api_endpoint = api_endpoint.replace("{{", "{")
    api_endpoint = api_endpoint.replace("}}", "}")

    # Create the issue entry
    issue_entry = {
        "issue": issue_title,
        "details": issue_detail,
    }

    # Add or update the issues for the given API endpoint
    if api_endpoint not in api_reflections:
        # Initialize a new list with the current issue
        api_reflections[api_endpoint] = [issue_entry]
    else:
        # Check if the same issue already exists for the endpoint
        existing_issues = api_reflections[api_endpoint]
        if issue_entry not in existing_issues:
            # Add the issue if it's unique
            existing_issues.append(issue_entry)
            # Ensure only the latest 3 issues are kept
            if len(existing_issues) > 3:
                existing_issues.pop(0)

    return "finished record_api_reflections"


def get_api_reflections_for_llm(api_endpoint: str) -> str:
    if _config_ablation == ABLATION_NO_REFLECTION:
        print(f"{_config_ablation=}, No reflections.")
        return None

    global api_reflections
    api_endpoint = api_endpoint.replace("{{", "{")
    api_endpoint = api_endpoint.replace("}}", "}")

    if 'api_reflections' not in globals() or api_endpoint not in api_reflections:
        return None

    reflections = api_reflections.get(api_endpoint, [])
    if not reflections:
        return None

    descriptions = []
    for reflection in reflections:
        issue = reflection.get("issue", "No issue title provided")
        details = reflection.get("details", "No details provided")
        descriptions.append(f"Issue: {issue}. Details: {details}.")

    return "\n".join(descriptions)

# init all vars
'''
Test Scenario recording related.
Example structure:
{
    "summary": "",
    "api_sequence": ["POST"]
}
'''
generated_test_scenarios = []

'''
{
"user_id": [1,2,3],
"username": ["max", "mbx"]
}
'''
useful_items = {}

'''
{
    "GET /api/items": [{
        "issue": "missing_access_token",
        "details": "Authorization header is missing or improperly formatted in the request headers.",
    }]
}
'''
api_reflections = {}


scenario = TestScenario()

current_test_case = None  # type: TestCase

