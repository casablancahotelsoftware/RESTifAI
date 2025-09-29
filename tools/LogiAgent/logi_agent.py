import json
import random
import time
import uuid
import sys
import os
from dataclasses import dataclass
from typing import Optional

import autogen
from autogen import ConversableAgent

from tools import do_request, record_result
import tools
import test_scenario
from dotenv import load_dotenv
from evalution import categorize_endpoints_by_status_with_graph
from rest_graph import RESTGraph
import argparse


load_dotenv()

sys.setrecursionlimit(5000)

@dataclass
class AppConfig:
    """Configuration class to hold all application settings"""
    system_name: str
    base_url: str
    log_path: str
    openapi_json_path: str
    edge_json_path: str
    max_time: int = 120
    rest_graph: Optional[RESTGraph] = None
    
    def __post_init__(self):
        """Initialize REST graph after configuration is set"""
        if not self.rest_graph and os.path.exists(self.openapi_json_path) and os.path.exists(self.edge_json_path):
            self.rest_graph = RESTGraph(
                None,
                swagger_path=self.openapi_json_path,
                base_url=self.base_url,
                edges_json_path=self.edge_json_path
            )
        
        # Ensure log directory exists
        os.makedirs(self.log_path, exist_ok=True)

api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
model = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
base_url = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "")

base_url = base_url.rstrip("/") + "/"

if base_url.endswith(".azure.com/"):
    base_url = base_url + "openai/deployments/" + model + "/chat/completions?api-version=" + api_version

if api_key and model and base_url and api_version:
    print(f"Azure OpenAI config found.")
    llm_config = {
        "config_list": [
            {
                "cache_seed": int(time.time()*1000),
                "model": model,
                "api_key": api_key,
                "base_url": base_url,
                "api_version": api_version,
                "api_type": "azure",
                "timeout": 120,
                "max_retries": 6,
                "price": [0.0004, 0.0016]
            }
        ]
    }
elif os.environ.get("OPENAI_API_KEY") is not None and os.environ.get("OPENAI_MODEL_NAME") is not None:
    llm_config = {"config_list": [
        {
            "cache_seed": int(time.time()*1000),
            "model": os.environ.get("OPENAI_MODEL_NAME"),
            "api_key": os.environ.get("OPENAI_API_KEY"),
            "timeout": 120,
            "max_retries": 3,
        },
        ]
    }

else: 
    raise ValueError("No valid LLM configuration found in environment variables.")

test_scenario_response_message = ""

def main(config: AppConfig):
    # Set the REST graph for test_scenario module
    test_scenario.set_rest_graph(config.rest_graph)
    
    api_retry_in_round_max_time = 3
    api_retry_last_pop_test_case = None  # type: test_scenario.TestCase
    previous_agent_names = []

    # Prompts

    test_scenario_prompt = f"""
You are a test scenario generate agent.
You generate one detailed and appropriate test scenarios for the provided REST system APIs listed below, to help identify potential bugs.

# Requirements for Test Scenario
- Each generated test scenario should be appropriately detailed, completed, complex, realistic, and coherent. Should mix different operations across multiple API endpoints, 
- Focus on interactions that could reveal defects such as mismatches (e.g., create, update, retrieve, delete) in data consistency, unexpected error responses, or unexpected dependency between endpoints.
- Design test scenarios with logically connected steps to reveal data inconsistencies, state management flaws, or unexpected behaviors, focusing on extended interaction paths with multiple CRUD operations or endpoint dependencies.

# Output Format

The output should be formatted as a step-by-step sequence, where each point explains a part of the scenario, including:
- The API endpoints that will be used.
- Description of this API call
- Expected responses.
Each step should be numbered and describe in detail to fully understand the scenario while remaining concise and refined.

# Example
```
**Input:** Provided system APIs: [1. POST /products, 2. GET /products, 3. POST /cart, 4. POST /checkout] 
**Output:**
1. **Title:** Add a Product to the System
    - **API Endpoint:** POST /products
    - **Description:** Adds a new product to the system with details such as name, price, and stock quantity.
    - **Expected Response:** A success response confirming that the product has been added successfully with the provided details.

2. **Title:** Retrieve Product List
    - **API Endpoint:** GET /products
    - **Description:** Fetches the list of all available products to verify that the newly added product appears in the inventory.
    - **Expected Response:** A list of products, including the recently added product with accurate details.
3. ... 

Summary: 
This workflow tests the entire purchasing process, ensuring that product management, cart functionality, and checkout operations work seamlessly together and that inventory updates correctly.
```

The following REST APIs are in the under test system, Please do not use other APIs other than these.
{config.rest_graph.graph_walk_llm_wrapper(node_cnt=min(10, len(config.rest_graph.api_nodes)))}


Previously generated test scenarios:
{test_scenario.get_previous_all_test_scenarios_for_llm()}
Ensure that the new test scenario is distinct and does not overlap with the previously generated test scenarios.

Start generate new test scenario for this REST API system.
"""

    test_scenario_recorder_prompt = """
First, call `record_test_scenario` once to record a test scenario generated by this REST API system, including a `summary` and `api_sequence`.  
Then, sequentially call `add_test_case` to record all REST test cases derived from the test scenario.

If `record_test_scenario` is called and all test data has been recorded, respond with "STATE-FLOW-MESSAGE:TEST SCENARIO RECORD COMPLETED" and do nothing else.

# Function Details

### **`record_test_scenario`**
- **`summary`**: A description of the test scenario. If the test scenario document already includes a summary, use it as is without modification.
- **`api_sequence`**: A list of items representing the sequence of API calls.  
  Each item must follow the **API Endpoint Rules** (see below).  
  Example: `["POST /pet", "GET /user/{{username}}", "DELETE /order/{{id}}"]`  

### **`add_test_case`**
- **`test_case_title`**: A title describing the specific test case.  
- **`api_endpoint`**: The API endpoint (see **API Endpoint Rules** below).  
- **`description`**: A description of the test case purpose and behavior.  
- **`expected_resp`**: The expected response for this test case.

### **API Endpoint Rules**
- **Format**: Use `<HTTP_METHOD> <API_ENDPOINT>`.  
  Examples:  
  - `POST /pet`  
  - `GET /user/{{username}}`  
  - `DELETE /order/{{id}}`  

- **Placeholders**: Use placeholders (e.g., `{{username}}`, `{{id}}`) for variables in the endpoints instead of hardcoded values.  
  Examples:  
  - Correct: `GET /user/{{username}}`  
  - Incorrect: `GET /user/johnDoe`  

- **Naming**: Always follow the placeholder names as defined in the Swagger documentation.  
  - Do **not** modify placeholder names. For example:  
    - Correct: `DELETE /order/{{id}}` (matches Swagger's definition).  
    - Incorrect: `DELETE /order/{{order_id}}` (modified the placeholder name).  

### Shared Rules
- Follow the API endpoint rules consistently across both `record_test_scenario` and `add_test_case`.
"""

    api_invoke_prompt = f"""
You are API invocation agent.
You generate API request parameters and execute API call.

# Steps
1. **Get next REST API test case**: Using the `get_next_test_case` tool to get next one test api, this api's corresponding swagger api info, and other useful info. 
2. **Generate Parameters AND Send API Requests**: For previous got API, Generate the appropriate parameters according to the information retrieved. Try to generate Then Execute this API request using the `do_request` tool. 

# Notes
- Get one by `get_next_test_case` then call `do_request` for it. Do not call get_next_test_case repeatedly.
- If an API request fails and get_next_test_case returns the same API as the previous one, use do_request to execute the request instead of calling get_next_test_case again.
- Generate parameter values based on Swagger constraints. Ensure values are **valid, diverse, and unpredictable**:
  - **Strings**: Use unique randomness (e.g., `"user_M4dXw7Qz9tR", "file_X9LmQ2Yt4Kr7", "r7LmQ9XpK2YtZ@example.net", "pwd_L9Rt2X7YtQp", "serial_7Rt9LXQ2YtM"`), avoiding generic patterns like `"test123"`. 
  - **Numbers**: Randomize within allowed ranges, including boundaries.
  - **Enums**: Randomly pick valid options, ensuring variety.
  - **Formats**: Follow required patterns (e.g., UUIDs, emails) with randomness (e.g., `"123e4567-e89b-12d3-a456-426614174000"`).
  - Hint: For variables that given example values in docs, try using example values at first, but avoiding reuse static or predictable values across all test cases/scenarios.
- When and only when `get_next_test_case` return "No more test case", say "STATE-FLOW-MESSAGE:NO MORE REQUESTS" and do nothing else. That means all request have been executed.

# Function Details
**`get_next_test_case` Function**: Do Not have parameters.

**`do_request` Parameters**:
- **`base_url`** (str): Base URL of the server. base_url = {config.rest_graph.get_base_url()}
- **`method`** (str): HTTP method to be used (e.g., GET, POST).
- **`api`** (str): API endpoint path.
- **`headers`** (dict): Request headers. 
  - **Note**: If the context includes Auth information such as an `access_token`, ensure the `headers` dictionary contains an `Authorization` key in the format: `"Authorization": "{{access_token_type}} {{access_token}}"`. For example: `{{"Authorization": "Bearer eyJhb..."}}`.
- **`params`** (dict): URL parameters.
- **`payload`** (dict): Request body payload, typically JSON Object: {{"key": "value"}}, do not use list until you are told so.
- **`payload_type`** (str) Payload type of request body, get_next_test_case's return info may have this info. Default is "application/json"
"""

    api_record_prompt = """
You are an API invocation Record agent.  
You should record:
1. Useful items of this API invocation by `record_useful_items` function tool if invocation is success
2. Reflection of this API invocation by `record_api_reflections` function tool if invocation is failed

If there are no items or reflections deserve to be recorded, return:  
`"STATE-FLOW-MESSAGE:NO ITEMS SHOULD RECORD"` and take no further action in such cases.

# Useful items of this API invocation (success invocation)

If the previous response is correct (aligns with the oracle), use the `record_useful_items` function tool to capture all **relevant object attributes** from the previous REST API's request and response.  
You should only record attributes directly related to identifiable objects, such as `id`, `name`, `password`, or other key properties essential for subsequent requests or validations.

### What to Record:
- **Object Attributes**: Attributes that describe identifiable objects within the system under test, typically needed for subsequent operations or validations. These include:
  - Unique identifiers (e.g., `id`, `productID`, `badge_id`)  
  - Descriptive attributes (e.g., `name`, `badge_name`)  
  - Related links or references (e.g., `link_url`, `image_url`)  
  - Relevant object states (e.g., `state: "active"`, `status: "locked"`) if they are meaningful within the system.  

### What NOT to Record:
- **Exclude the following types of information**:  
  1. **Error or Exception Details**:
     - Example: `error_message`, `reason`, `error_detail`.  
  2. **Request/Response Metadata**:
     - Example: `timestamp`, `etag`, `response_code`.  
  3. **Process or Request State**:
     - Example: `request_status`, `retry_count`.  
  4. **Boolean Values**:
     - Unless they are explicitly part of an object's attributes (e.g., `is_active`), do not record standalone booleans.  
  5. **Other Irrelevant Data**:
     - Avoid data that does not describe objects in the system under test.

### Recording Instructions
- Prepare a dictionary with each useful item's name, corresponding value, and description. 
  Each dictionary key should represent the name of an essential attribute (e.g., "productID", "username").
  The value for each key should be another dictionary containing the following fields:
  - `"value"`: The corresponding value of the attribute (e.g., "101", "Max").
  - `"description"`: A brief description of the attribute (e.g., "Product ID of a specific item", "User with admin privileges").
- Pass the dictionary of items directly to the `record_useful_items` function to record them all at once.


# Reflection of this API invocation (success invocation)
If the previous response of this API is failed, think about if previous api invocation params have problem.

### What to Reflect:
1. **Parameter Issues**: Identify any incorrect or missing parameters in the request. Examples include:
   - Invalid or missing `access_token` in headers.
   - Incorrect or missing required fields in the payload (e.g., `email`, `password`).
   - Mistyped endpoint or query parameters.

2. **Authorization/Authentication Errors**:
   - Was the `Authorization` header properly set (e.g., valid `access_token`)?
   - Were user roles/permissions sufficient for this request?

3. **API Contract Violations**:
   - Does the payload or request structure deviate from API specifications?
   - Is the API expecting additional headers or parameters not provided?

4. **Environmental Issues**:
   - Could server configuration (e.g., CORS, rate limiting) or connectivity problems have caused the failure?

### Reflection Recording Instructions:
- Create a dictionary with detailed reflection points, using concise and descriptive keys.
- Each key should highlight an area of concern (e.g., "missing_access_token", "invalid_payload").
- Pass the dictionary to the `record_api_reflections` function to document the reflection.


# Function Details of `record_useful_items` and `record_api_reflections`
**`record_useful_items` Function Parameter**:
- **`items`**: A dictionary where each key is the name of a useful item to be recorded, and each value is a dictionary containing two fields:
  - `"value"`: The corresponding value of the attribute (e.g., `"101"`, `"Max"`).
  - `"description"`: The description of the attribute (e.g., `"Product ID of a specific item"`, `"User with admin privileges"`).
  Example: 
  ```python
  {
      "productID": {"value": "101", "description": "Product ID of a specific item"},
      "username": {"value": "Max", "description": "User with admin privileges"}
  }
  ```

**`record_api_reflections` Function Parameters**:
- **`api_endpoint`** (str): The API endpoint where the issue occurred. see **API Endpoint Rule** below.
- **`issue_title`** (str): A concise title describing the issue (e.g., `"missing_access_token"` or `"invalid_query_params"`).
- **`issue_detail`** (str): A detailed explanation of the issue (e.g., `"Authorization header is missing or improperly formatted in the request headers."`).

### **API Endpoint Rules**
- **Format**: Use `<HTTP_METHOD> <API_ENDPOINT>`.  
  Examples:  
  - `POST /pet`  
  - `GET /user/{{username}}`  
  - `DELETE /order/{{id}}`  

- **Placeholders**: Use placeholders (e.g., `{{username}}`, `{{id}}`) for variables in the endpoints instead of hardcoded values.  
  Examples:  
  - Correct: `GET /user/{{username}}`  
  - Incorrect: `GET /user/johnDoe`  

- **Naming**: Always follow the placeholder names as defined in the Swagger documentation.  
  - Do **not** modify placeholder names. For example:  
    - Correct: `DELETE /order/{{id}}` (matches Swagger's definition).  
    - Incorrect: `DELETE /order/{{order_id}}` (modified the placeholder name).  
"""

    validation_prompt = """
You are an API Validation Agent. You should do your validation for response data in two steps.
Remember you must *Explicitly* reasoning and analyze by output your thoughts and then you can call `record_result` function tool.

# Steps
1. Call `get_next_response_for_validation` once to retrieve API documentation or response info.
2. Compare the expected and actual responses, *explicitly* evaluating them from multiple perspectives, and record by calling `record_result` function.
   - Consider both the response code and key elements in the response body.
   - Provide a detailed evaluation from at least three different perspectives, ensuring that one perspective may contradict the others to offer a balanced assessment.
   - *Explicitly* output your reasoning for each perspective, Output Format: 
     * Thought1: <thoughts>
     * Thought2: <thoughts>
     * Thought3: <thoughts> ...
     You have to output your thoughts following this Output Format before you call record_result function tool.
   - Suggesting the `record_result` function tool to log the evaluation result:Record the evaluation using `record_result`:
     * Include params `align_with_expected`, `judge_reason`, `oracle` , `request_info`, and `response` when calling the `record_result` function
     * For *minor mismatches**, mark `align_with_expected` as `True`, but highlight the discrepancies in `judge_reason`. For significant deviations, mark it as `False` and elaborate.

# Function Details
**`get_next_response_for_validation` Function**: Do Not have parameters.

**`record_result` Function** Parameters:
- **oracle**: The expected response, provided as a string.
- **judge_reason**: 
  - Provide clear reasoning for your judgment, highlighting any deviations and their significance.
  - For `align_with_expected = True`, explicitly state why the response is considered aligned despite the minor deviations. For example:
    - *"The response includes an additional field not specified in the expected result, but it does not affect the primary functionality."*
  - For `align_with_expected = False`, clearly explain how the discrepancies impact functionality or violate the expected behavior. For example:
    - *"The response omits the required 'id' field, which is critical for subsequent operations."*
    - *"The response code is 500, indicating a server error, which does not align with the expected behavior."*
- **align_with_expected**: 
  - Set to `True` if the actual response mainly aligns with the expected result, even if there are minor deviations such as:
    - Minor differences in non-critical fields or message strings, as long as core functionality and intent are preserved.
    - If you believe the mismatch in response is due to your incorrect request parameters or your wrong expectations, set align_with_expected to True.
  - Set to `False` if discrepancies significantly affect functionality, intended behavior, or key data elements.
- **request_info**: Information about the API request, including method, URL, parameters, and other relevant details.
- **response**: The actual response, including both the response code and body.

# Notes

- Perform one validation for one request and response.
- Provide detailed reasoning when evaluating the alignment of responses.
- If request in test scenario, but not actually do request, record it with: align_with_expected=False, request_info=NoRequest, response=NoResponse
"""

    print(f"{test_scenario_prompt}")

    test_scenario_agent = ConversableAgent(name="test_scenario_agent",
                                             system_message=test_scenario_prompt,
                                             llm_config=llm_config,
                                             human_input_mode="NEVER")

    test_scenario_recorder_agent = ConversableAgent(name="test_scenario_recorder_agent",
                                                    system_message=test_scenario_recorder_prompt,
                                                    llm_config=llm_config,
                                                    human_input_mode="NEVER")
    test_scenario_recorder_agent.register_for_llm(name="add_test_case", description="record rest api test case")(test_scenario.add_test_case)
    test_scenario_recorder_agent.register_for_execution(name="add_test_case")(test_scenario.add_test_case)

    test_scenario_recorder_agent.register_for_llm(name="record_test_scenario", description="record rest api test scenario")(test_scenario.record_test_scenario)
    test_scenario_recorder_agent.register_for_execution(name="record_test_scenario")(test_scenario.record_test_scenario)

    api_invoke_agent = ConversableAgent(name="api_invoke_agent",
                                        system_message=api_invoke_prompt,
                                        llm_config=llm_config,
                                        human_input_mode="NEVER",
                                        )
    api_invoke_agent.register_for_llm(name="get_next_test_case", description="get next api test info")(test_scenario.get_next_test_case)
    api_invoke_agent.register_for_execution(name="get_next_test_case")(test_scenario.get_next_test_case)

    api_invoke_agent.register_for_llm(name="do_request",description="Do REST API request")(do_request)
    api_invoke_agent.register_for_execution(name="do_request")(do_request)

    # record feed back
    api_recorder_agent = ConversableAgent(name="api_recorder_agent",
                                                    system_message=api_record_prompt,
                                                    llm_config=llm_config,
                                                    human_input_mode="NEVER")
    api_recorder_agent.register_for_llm(name="record_useful_items", description="record useful item among previous response data")(test_scenario.record_useful_items)
    api_recorder_agent.register_for_execution(name="record_useful_items")(test_scenario.record_useful_items)

    api_recorder_agent.register_for_llm(name="record_api_reflections", description="record reflection for api call failure")(test_scenario.record_api_reflections)
    api_recorder_agent.register_for_execution(name="record_api_reflections")(test_scenario.record_api_reflections)

    validation_agent = ConversableAgent(name="validation_agent",
                                        system_message=validation_prompt,
                                        llm_config=llm_config,
                                        human_input_mode="NEVER")

    validation_agent.register_for_llm(name="get_next_response_for_validation",
                                      description="get next api request and response for validation")(test_scenario.get_next_response_for_validation)
    validation_agent.register_for_execution(name="get_next_response_for_validation")(test_scenario.get_next_response_for_validation)

    validation_agent.register_for_llm(name="record_result",
                                      description="record result")(record_result)
    validation_agent.register_for_execution(name="record_result")(record_result)

    # ==================== Execution ========================
    def state_transition(last_speaker, groupchat):
        # Rate limit for online systems
        # time.sleep(random.randint(100, 1000) / 1000)
        nonlocal api_retry_in_round_max_time, api_retry_last_pop_test_case, previous_agent_names

        try:
    
            messages = groupchat.messages
            last_msg = messages[-1]
            last_msg_content = last_msg['content']
        
            previous_agent_names.append(last_speaker.name)
            if len(previous_agent_names) > 10:
                previous_agent_names = previous_agent_names[-10:]
                if len(set(previous_agent_names)) <= 1:
                    print(f"Agent called repeatedly more than 10 times, return None to start next request, agent_names: {previous_agent_names[-1]}")
                    return None
        
            # print(f"{last_msg_content}")
        
            if last_speaker is test_scenario_agent:
                if len(test_scenario.scenario.scenario_text) == 0:
                    # Save test scenario information
                    test_scenario.scenario.scenario_text = last_msg_content
                return test_scenario_recorder_agent
            elif last_speaker is test_scenario_recorder_agent:
                if "STATE-FLOW-MESSAGE:TEST SCENARIO RECORD COMPLETED" in last_msg_content:
                    return api_invoke_agent
                else:
                    return test_scenario_recorder_agent
            elif last_speaker is api_invoke_agent:
                # Use agent's runtime content (messages[-1]) to determine if the request was successful
                if "status_code" in last_msg_content and "response_data" in last_msg_content and len(last_msg['tool_responses']) > 0:
                    # Request sent and returned, remove one test_case from test_scenario.scenario
                    api_retry_last_pop_test_case = test_scenario.scenario.todo_tests.pop(0)
                    print(f"REMOVE CASE: there are {len(test_scenario.scenario.todo_tests)} test cases now.")
                    return validation_agent
                if "STATE-FLOW-MESSAGE:NO MORE REQUESTS" in last_msg_content:
                    print("End of this test scenario.")
                    return None
                else:
                    return api_invoke_agent
            elif last_speaker is validation_agent:
                # After successful record, call next API
                if "finished record_result" in last_msg_content and len(last_msg['tool_responses']) > 0:
                    test_scenario.scenario.todo_resps.pop(0)
                    print(
                        f"REMOVE RESPONSE: there are {len(test_scenario.scenario.todo_resps)} responses left (0 is right).")
        
                    # Request failed, decide whether to retry based on remaining api_retry_in_round_max_time
                    if 'align_with_expected=False' in last_msg_content:
                        print(f"Find align_with_expected=False. {api_retry_in_round_max_time=} {api_retry_last_pop_test_case.api_endpoint=}")
                        if api_retry_in_round_max_time > 0 and type(api_retry_last_pop_test_case) is test_scenario.TestCase:
                            api_retry_in_round_max_time -= 1
                            test_scenario.add_test_case_object(api_retry_last_pop_test_case)
                            api_retry_last_pop_test_case = None
                            return api_invoke_agent
                        else:
                            print(f"{api_retry_in_round_max_time=} Exceeded maximum failure attempts. return api_recorder_agent")
        
                    return api_recorder_agent
                else:
                    return validation_agent
            elif last_speaker is api_recorder_agent:
                # record_useful_items is returned when call is successful, continue with next API
                if "finished record_useful_items" in last_msg_content and len(last_msg['tool_responses']) > 0:
                    return api_invoke_agent
                # Nothing worth recording, continue to next round
                elif "STATE-FLOW-MESSAGE:NO ITEMS SHOULD RECORD" in last_msg_content:
                    return api_invoke_agent
                # Stuck in continuous api_recorder_agent unable to record state, proceed to next request
                elif "Error: Function" in last_msg_content and "not found" in last_msg_content:
                    if len(previous_agent_names) > 5 and all(name == "api_recorder_agent" for name in previous_agent_names[-5:]):
                        print("api_recorder_agent called continuously more than 5 times, switching to api_invoke_agent")
                        return api_invoke_agent
                    else:
                        return api_recorder_agent
                # record_api_reflections is returned when call fails, end this round of testing
                elif "finished record_api_reflections" in last_msg_content and len(last_msg['tool_responses']) > 0:
                    return None
                else:
                    return api_recorder_agent
            else:
                return None

        except Exception as e:
            print(f"Error occurred: {e}")
            return None

    groupchat = autogen.GroupChat(
        agents=[test_scenario_agent, test_scenario_recorder_agent, api_invoke_agent, api_recorder_agent, validation_agent],
        messages=[],
        max_round=200,
        speaker_selection_method=state_transition,
    )
    group_chat_manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config,
                                                  system_message="""Agents and its tools:
* test_scenario_recorder_agent:
    + add_test_case: record rest api test case
    + record_test_scenario: record rest api test scenario

* api_invoke_agent:
    + get_next_test_case: get next api test info
    + do_request: Do REST API request

* api_recorder_agent:
    + record_useful_items: record useful item among previous response data
    + record_api_reflections: record reflection for api call failure

* validation_agent:
    + get_next_response_for_validation: get next api request and response for validation
    + record_result: record result
""")

    group_chat_manager.initiate_chat(
        test_scenario_agent,
        message="Start LLM based REST API Test loop",
        # summary_method="reflection_with_llm",
    )

    global test_scenario_response_message
    test_scenario_response_message = test_scenario.scenario.scenario_text


    test_scenario_summary_prompt = f"""
Summarize a REST API Test Scenario based on its description and execution data. Highlight key outcomes, identify errors or mismatches, and provide actionable suggestions for improvement.

# Inputs
## Test Scenario Description by another agent
{test_scenario_response_message}

## Execution Data: Specifics on correct ("Align with expectation") and incorrect ("Not align with expectation") outcomes.

### Right results:
{tools.right_results}

### Wrong results:
{tools.wrong_results}

# Steps
1. **Overall Success/Failure**: Provide a brief statement on the overall success or failure of the scenario.
2. **Error Identification**: Summarize incorrect outcomes and analyze their causes.
3. **Recommendations**: Suggest actionable improvements or next steps, such as adding tests or addressing missing validations.

# Output Format
- A clear and concise paragraph (50 words) summarizing key outcomes, including test failure, errors, and recommendations.

# Examples
## Example 1
The REST API test scenario executed successfully without errors, validating user lifecycle operations, item creation, password updates, and data consistency. Key points: ensure thorough validation for edge cases in password recovery and health checks in production environments.

## Example 2
Test Scenario failed at POST /admin/users due to insufficient permissions. Ensure access-token validation is correctly configured. Recommend adding role and permission checks in future Test Scenario generation to prevent such issues.

# Notes
- Recommendations should be concise, realistic, and actionable.
- Once the summary is created, proceed to call the `record_test_scenario_result_summary` tool to record the result summary.
"""
    test_scenario_summary_agent = ConversableAgent(name="test_scenario_recorder_agent",
                                                    system_message=test_scenario_summary_prompt,
                                                    llm_config=llm_config,
                                                    human_input_mode="NEVER")
    test_scenario_summary_agent.register_for_llm(name="record_test_scenario_result_summary", description="record test scenario result summary")(test_scenario.record_test_scenario_result_summary)
    test_scenario_summary_agent.register_for_execution(name="record_test_scenario_result_summary")(test_scenario.record_test_scenario_result_summary)

    dummy_proxy = ConversableAgent(name="mentor_agent",
                                   system_message="You are the mentor agent of test_scenario_summary_agent",
                                   llm_config=llm_config,
                                   human_input_mode="NEVER")
    dummy_proxy.register_for_llm(name="record_test_scenario_result_summary",description="record test scenario result summary")(test_scenario.record_test_scenario_result_summary)
    dummy_proxy.register_for_execution(name="record_test_scenario_result_summary")(test_scenario.record_test_scenario_result_summary)

    dummy_proxy.initiate_chat(test_scenario_summary_agent,
                              message="Summary this Test Scenario's execution result",
                              max_turns=2)

    total_tokens = 0
    total_cost = 0.0


    for agent in [test_scenario_agent, test_scenario_recorder_agent, api_invoke_agent, api_recorder_agent, validation_agent, test_scenario_summary_agent, dummy_proxy]:
        if agent.client.actual_usage_summary is None:
            continue
        
        for key, value in agent.client.actual_usage_summary.items():
            if key != 'total_cost' and isinstance(value, dict) and 'total_tokens' in value:
                total_tokens += value['total_tokens']
        
        total_cost += agent.client.actual_usage_summary['total_cost']

    return {
        "total_tokens": total_tokens,
        "total_cost": total_cost
    }

def calculate_request_count():
    all_request_cnt = 0
    analyzed_files = []

    json_log_path = config.log_path

    for file in os.listdir(json_log_path):
        if file.endswith(".json"):
            analyzed_files.append(file)
            with open(os.path.join(json_log_path, file), "r") as f:
                data = json.load(f)
                all_request_sequence = data["all_request_sequence"]

                all_request_cnt += len(all_request_sequence)

    return all_request_cnt

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='LogiAgent REST API Testing Tool')

    parser.add_argument('--max-time', type=int, default=120, help='Maximum execution time in seconds (default: 120)')
    parser.add_argument('--system-name', dest='system_name', type=str, required=True, help='System (service) name to test')
    parser.add_argument('--base-url', dest='base_url', type=str, required=True, help='Base URL for the REST API')
    parser.add_argument('--openapi-json', dest='openapi_json_path', type=str, help='Path to OpenAPI JSON specification')
    parser.add_argument('--edge-json', dest='edge_json_path', type=str, help='Path to edges JSON file')
    parser.add_argument('--log-path', dest='log_path', type=str, help='Path to store log files')

    args = parser.parse_args()
    
    # Set default paths if not provided
    if not args.openapi_json_path:
        args.openapi_json_path = f'apis/{args.system_name}/specifications/openapi.json'
    if not args.edge_json_path:
        args.edge_json_path = f'apis/{args.system_name}/edges/edges.json'
    if not args.log_path:
        args.log_path = f'./logs'

    return args

def create_config_from_args(args) -> AppConfig:
    """Create AppConfig from parsed arguments"""
    return AppConfig(
        system_name=args.system_name,
        base_url=args.base_url,
        openapi_json_path=args.openapi_json_path,
        edge_json_path=args.edge_json_path,
        log_path=args.log_path,
        max_time=args.max_time
    )

if __name__ == '__main__':
    args = parse_arguments()
    config = create_config_from_args(args)

    # Validate that required files exist
    if not os.path.exists(config.openapi_json_path):
        print(f"Error: OpenAPI JSON file not found at {config.openapi_json_path}")
        sys.exit(1)
    
    if not os.path.exists(config.edge_json_path):
        print(f"Error: Edge JSON file not found at {config.edge_json_path}")
        sys.exit(1)

    if not config.rest_graph:
        print("Error: Failed to initialize REST graph")
        sys.exit(1)

    print(f"Config Applied: System={config.system_name}, Base URL={config.base_url}")
    print(f"OpenAPI: {config.openapi_json_path}")
    print(f"Edges: {config.edge_json_path}")
    print(f"Logs: {config.log_path}")

    global_metrics = {
        "successful_operations": 0,
        "server_errors": 0,
        "total_tokens": 0,
        "total_cost": 0.0,
        "total_tests": 0,
        "failed_tests": 0
    }

    unique_successfull = set()
    start_time = time.time()

    # Use max_time from configuration
    max_time = config.max_time

    i=0
    while time.time() - start_time < max_time:
        
        usage_dict = {
            "total_tokens": 0,
            "total_cost": 0.0
        }


        # reset all global vars
        test_scenario_response_message = ""
        test_scenario.scenario = test_scenario.TestScenario()
        tools.all_request_sequence.clear()
        tools.right_results.clear()
        tools.wrong_results.clear()
        seed = int(time.time()*1000)
        llm_config["config_list"][0]["cache_seed"] = seed

        print(f"main: {i}, {seed=}, timestamp={int(time.time())}, remaining_time={max_time - (time.time() - start_time)}")

        tmp_dict = main(config)
        usage_dict["total_cost"] += tmp_dict.get("total_cost", 0.0)
        usage_dict["total_tokens"] += tmp_dict.get("total_tokens", 0)

        # Get current iteration's endpoint categorization
        current_endpoints = categorize_endpoints_by_status_with_graph(tools.all_request_sequence, rest_graph=config.rest_graph)

        unique_successfull.update(current_endpoints.get("200", set()))
        
        for key, value in current_endpoints.items():
            if isinstance(value, set):
                current_endpoints[key] = list(value)

        with open(f"{config.log_path}/main_result_{int(time.time()*1000)}_PID_{os.getpid()}.json", "w") as f:
            f.write(
                json.dumps(
                    {
                        "all_cnt": len(tools.all_request_sequence),
                        "all_request_sequence": tools.all_request_sequence,
                        "right_results": tools.right_results,
                        "wrong_results": tools.wrong_results,
                        "test_scenario_response_message": test_scenario_response_message,
                        "usage": usage_dict,
                        "unique_endpoints": current_endpoints,
                        "total_true_result": len(tools.right_results),
                        "total_false_result": len(tools.wrong_results)
                    }
                )
            )


        server_errs = current_endpoints.get("500", 0)
        failed_tests = len(tools.wrong_results)
        total_test = len(tools.right_results) + len(tools.wrong_results)

        global_metrics["server_errors"] += server_errs
        global_metrics["total_tokens"] += usage_dict["total_tokens"]
        global_metrics["total_cost"] += usage_dict["total_cost"]
        global_metrics["total_tests"] += total_test
        global_metrics["failed_tests"] += failed_tests

        i+=1
    
    global_metrics["successful_operations"] = len(unique_successfull)

    print(global_metrics)

    with open(f"{config.log_path}/results.json", "w") as f:
        json.dump(global_metrics, f, indent=2)