from typing import List, Dict

class PromptTemplate:
    def __init__(self, template: str, placeholders: List[str] = None):
        if placeholders is None:
            placeholders = []

        self.template: str = template
        self.placeholders: List[str] = placeholders

    def _replace_placeholders(self, placeholder_values: Dict[str, str]) -> str:
        prompt = self.template
        for placeholder in self.placeholders:
            if placeholder in placeholder_values:
                prompt = prompt.replace(f"[[{placeholder}]]", str(placeholder_values[placeholder]))
            else:
                raise ValueError(f"Placeholder '{placeholder}' not found in provided values.")
        self.prompt = prompt
        return prompt

    def generate_prompt(self, placeholder_values: Dict[str, str]) -> str:
        return self._replace_placeholders(placeholder_values)


class OperationSelectorPrompt(PromptTemplate):
    def __init__(self):
        super().__init__(OPERATION_SELECTOR_SYSTEM_PROMPT, OPERATION_SELECTOR_SYSTEM_PROMPT_PLACEHOLDERS)

OPERATION_SELECTOR_SYSTEM_PROMPT_PLACEHOLDERS = ["operation_id", "endpoints_info"]
OPERATION_SELECTOR_SYSTEM_PROMPT = """
You are an API Test planning Expert. Your task is to determine the sequence of API operations needed to generate a valid 2xx code request for the [[operation_id]] operation.
Also you should provide guidance on how to use the operations correctly.

You are provided with the following information:

1. The operation Id for which a valid request needs to be generated. This operation Id is part of the API specification and represents a specific endpoint that needs to be called.
2. The full API specification in the form of endpoint metadata (`endpoints_info`), which includes all available operations and their required or optional parameters.

Based on this information, you need to:

- Determine the **correct sequence of operation Ids** needed to create a valid request for the [[operation_id]] operation. For each request needed, include the operation Id in the sequence.
- If not stated in the user request explicitly, try to create a scenario that allows to define as many parameter values of the endpoint as possible.
- Ensure that all required and optional parameters of the [[operation_id]] operation can be filled based on the sequence of operations.
- Assume the database is initially empty. If any operations depend on pre-existing resources, include earlier operations to create those resources.
- **Explain how to use each endpoint** in the sequence:
  - Mention **required and optional parameters**.
  - Indicate any **important considerations**, such as fields that should be included/excluded, expected formats, or known dependencies.
  - Clarify how data flows from one operation to the next if there are dependencies between requests.

---

### Provided Inputs:

**OPERATION ID A VALID REQUEST NEEDS TO BE GENERATED FOR:**  
[[operation_id]]

**ENDPOINTS INFO:**  
A list of all API operations, including operation Ids, their parameters, and relationships. Use this to determine what operations are available and what dependencies they have.  
[[endpoints_info]]

---

### Output Format:

Respond with a JSON object containing two keys:

1. `"operation_sequence"` – a **JSON array of strings** representing the list of operation Ids in the correct order.
2. `"usage_guide"` – a **short explanation** of how to use each endpoint in the sequence, including any noteworthy usage instructions, parameters to include or exclude, and how to handle data between steps.

"""
OPERATON_SELECTOR_EXAMPLE = """
### Example Output:
{
  "operation_sequence": ["createUser", "createOrder", "getOrder"],
  "usage_guide": "1. `createUser`: Requires `username` and `email`. Ensure the email is unique...\n2. `createOrder`: Requires `userId` from `createUser` response...\n3. `getOrder`: Use the `orderId` returned from `createOrder`..."
}

"""


class ValidValueGenerationPrompt(PromptTemplate):
    def __init__(self):
        super().__init__(VALID_VALUE_GEN_TEMPLATE, VALID_VALUE_GEN_TEMPLATE_PLACEHOLDERS)

VALID_VALUE_GEN_TEMPLATE_PLACEHOLDERS = ["operation_id", "selected_operations", "test_plan_description", "operation_id", "method", "path", "parameters", "request_body", "previouse_values"]
VALID_VALUE_GEN_TEMPLATE = """
You are a API Testing Expert. Your task is to generate realistic parameter values for a successful 2xx API request based on the provided endpoint details. 

You are provided with the following information:

1. A list of operation ids selected by a API Test Planing Expert to successfully create a valid request for the last endpoint in the list.
2. A short description of this Plan.
3. The current operation you should create valid parameters and its details, including the operation Id, method, path, parameters, and request body schema.
4. Previous Request and Response values representing the history of interaction and may be used to fill in dependent parameters for the current request.

Based on this information, you need to:
 - Generate realistic parameter values for the current operation.
 - Use the context to fill in any dependent parameters using "{{reference_key}}" syntax and use the keys from **PREVIOUS REQUEST AND RESPONSE VALUES:**.
 - If values are taken from previous responses, they are allways dependent and you have to use the "{{reference_key}}" syntax.
 - Ensure that the generated values are valid according to the provided schema.
 - Ensure to set the correct Content-Type header depending on the request body type.
 - Try to generate values for as many parameters as possible also if they are not required.

---

### Provided Inputs:

**SELECTED OPERATION LIST:**
[[selected_operations]]

**TEST PLAN DESCRIPTION:**
[[test_plan_description]]

**CURRENT OPERATION DETAILS:**
- Operation Id: [[operation_id]]
- Method: [[method]]
- Path: [[path]]
- Parameters (path, query, header, and cookie): [[parameters]]
- Request Body Schema: [[request_body]]

**PREVIOUS REQUEST AND RESPONSE VALUES:**
[[previouse_values]]

---

### Output Format:

Generate a JSON object with the following top-level keys:
path_params, query_params, headers, cookies, and body.

For each parameter, provide the value directly:
- Use literal values for generated data (e.g., "user123", 42, true)
- Use "{{reference_key}}" syntax for dependent values (e.g., "{{CreateUser.response.body.userId}}")
- References always need to be inclosed in quotes also if they are numbers, boolean etc..

Values containing { or } characters are supported - only {{double_braces}} are treated as reference keys.

If "PREVIOUS REQUEST AND RESPONSE VALUES" is empty, all values must be literal generated values.

"""

class UserInputTemplate(PromptTemplate):
    def __init__(self):
        super().__init__(USER_INPUT_TEMPLATE, USER_INPUT_TEMPLATE_PLACEHOLDERS)

USER_INPUT_TEMPLATE_PLACEHOLDERS = ["user_input"]
USER_INPUT_TEMPLATE = """
### Custom User Input:
The user provided a custom input that may help achieving your overall goal. Only use this information if its relevant for your task:

[[user_input]]

"""


VALID_VALUE_GEN_EXAMPLE = """
### Example Output:
{
  "path_params": {
    "userId": "{{CreateUser.response.body.userId}}"
  },
  "query_params": {
    "sort": "desc",
    "limit": 10,
    "$filter": "companyId eq {{CreateCompany.response.body.companyId}}",
    "$top": "__undefined"
  },
  "headers": {
    "Authorization": "Bearer {{AuthenticateUser.response.body.accessToken}}",
    "Content-Type": "application/json"
  },
  "cookies": {
    "sessionId": "{{LoginUser.response.body.sessionId}}"
  },
  "body": {
    "productId": "{{CreateProduct.response.body.productId}}",
    "companyName": "Test Company",
    "quantity": 2,
    "metadata": {
      "source": "api_test",
      "config": "{key: value}"
    }
  }
}

"""

class FixValueGenerationPrompt(PromptTemplate):
    def __init__(self):
        super().__init__(FIX_VALUE_GEN_TEMPLATE, FIX_VALUE_GEN_TEMPLATE_PLACEHOLDERS)

FIX_VALUE_GEN_TEMPLATE_PLACEHOLDERS = ["test_plan_description", "operation_id", "method", "path", "parameters", "request_body", "previouse_values", "failed_values", "error_response"]
FIX_VALUE_GEN_TEMPLATE = """
You are an API Testing Expert. Your task is to analyze a failed API request that resulted in a 4xx Client Error, and correct the parameter values to create a valid request.

You are provided with the following context:

1. A short description of the Test Plan.
2. The current operation details, including operation_id, method, path, parameters, and request body schema.
3. The values that were used in the failed request.
4. The server's 4xx response message and status code.
5. Previous Request and Response values representing the history of interaction and may be used to fill in parameters for the current request.

Your task is to:
- Analyze the provided **FAILED REQUEST VALUES:** and the **SERVER 4XX RESPONSE:** to determine what likely caused the client-side error (e.g., invalid types, missing required values, constraint violations, authorization issues, etc.).
- **Correct required parameters** to valid values based on the provided schema and context.
- **Remove optional parameters** that are not needed for a valid request.
- Use realistic examples where applicable, and respect the provided schema and any dependency context.
- Use the context to fill in any dependent parameters using "{{reference_key}}" syntax and use the keys from **PREVIOUS REQUEST AND RESPONSE VALUES:**.
- If values are taken from previous responses, they are allways dependent and you have to use the "{{reference_key}}" syntax.

---

### Provided Inputs:

**TEST PLAN DESCRIPTION:**  
[[test_plan_description]]

**CURRENT OPERATION DETAILS:**  
- Operation Id: [[operation_id]]
- Method: [[method]]
- Path: [[path]]
- Parameters (path, query, header, and cookie): [[parameters]]
- Request Body Schema: [[request_body]]

**PREVIOUS REQUEST AND RESPONSE VALUES:**  
[[previouse_values]]

**FAILED REQUEST VALUES:**  
[[failed_values]]

**SERVER 4XX RESPONSE:**  
[[error_response]]

---

### Output Format:

Generate a JSON object with the following top-level keys:
path_params, query_params, headers, cookies, and body.

For each parameter, provide the value directly:
- Use literal values for generated data (e.g., "user123", 42, true)
- Use "{{reference_key}}" syntax for dependent values (e.g., "{{CreateUser.response.body.userId}}")
- References always need to be inclosed in quotes also if they are numbers, boolean etc..

Values containing { or } characters are supported - only {{double_braces}} are treated as reference keys.

Return only the JSON object with the corrected values. Do not include any explanations or extra text.

"""


class GenerateStructuralNegativeTestDescriptionsPrompt(PromptTemplate):
    def __init__(self):
        super().__init__(GENERATE_STRUCTURAL_NEGATIVE_TEST_DESCRIPTIONS_TEMPLATE, GENERATE_STRUCTURAL_NEGATIVE_TEST_DESCRIPTIONS_TEMPLATE_PLACEHOLDERS)

GENERATE_STRUCTURAL_NEGATIVE_TEST_DESCRIPTIONS_TEMPLATE_PLACEHOLDERS = ["operations", "baseline_data", "endpoints_info", "last_endpoint_name"]
GENERATE_STRUCTURAL_NEGATIVE_TEST_DESCRIPTIONS_TEMPLATE = """
You are an API Testing Expert. Create a valid JSON array of objects (each with “description” and “test_case_name”) for strictly invalid requests targeting the [[last_endpoint_name]] operation. Only violate the OpenAPI schema constraints of request properies explicitly defined in the OpenAPI specification. Dont test for not defined constraints or values. Each scenario must produce a guaranteed 4xx error and never be valid. Do not include business or domain logic. Do not generate type validation tests for path parameters when their schema type is string, as all path parameters are strings in the actual HTTP request URL. Each test must be unique, unambiguously invalid, and not interpretable as valid under the spec. Output only the JSON array—no extra text.

---

**Provided Inputs:**

- **SELECTED OPERATION LIST:**  
  [[operations]]

- **BASELINE DATA:**  
  [[baseline_data]]

- **ENDPOINTS INFO:**  
  [[endpoints_info]]

- **LAST ENDPOINT NAME:**  
  [[last_endpoint_name]]

**Output Format:**
Return a JSON array of objects, each with:
• description: Includes the parameters that needs to be changed for the relevant operation and a value example that violates the specification.
• test_case_name: The name of the test case in camelCase.

**Example:**
[
  {
    "description": "Change the `name` parameter of the addUser request to a string with more than the maxLenght of 20 characters, e.g., 'ThisNameIsWayTooLongForTheSystem'",
    "test_case_name": "nameTooLong"
  }
]

"""

class GenerateFunctionalNegativeTestDescriptionsPrompt(PromptTemplate):
    def __init__(self):
        super().__init__(GENERATE_FUNCTIONAL_NEGATIVE_TEST_DESCRIPTIONS_TEMPLATE, GENERATE_FUNCTIONAL_NEGATIVE_TEST_DESCRIPTIONS_TEMPLATE_PLACEHOLDERS)

GENERATE_FUNCTIONAL_NEGATIVE_TEST_DESCRIPTIONS_TEMPLATE_PLACEHOLDERS = ["operations", "baseline_data", "endpoints_info", "existing_test_cases", "last_endpoint_name"]
GENERATE_FUNCTIONAL_NEGATIVE_TEST_DESCRIPTIONS_TEMPLATE = """
You are an API Testing Expert. Create a valid JSON array of objects (each with “description” and “test_case_name”) for strictly invalid requests targeting the [[last_endpoint_name]] operation based on **domain/business logic** errors only. If not specified in the specification, use common sense and industry best practices to determine what constitutes a logical error. Each scenario must produce a guaranteed 4xx error for the [[last_endpoint_name]] endpoint that violates logical or business rules. Do not include schema violations or structural constraints. Each test must be unique, unambiguously invalid, and not interpretable as valid.
The exact same sequence of operations from the baseline must be used, no added or removed steps. The database is empty for every test, and previous requests remain valid; only the final request can change. Each scenario must produce a 4xx error that violates logical or business rules and must not duplicate existing test cases or structural constraints. Output only the JSON array—no extra text.

---

**Provided Inputs:**

- **SELECTED OPERATION LIST:**  
  [[operations]]

- **BASELINE DATA:**  
  [[baseline_data]]

- **ENDPOINTS INFO:**  
  [[endpoints_info]]

- **EXISTING TEST CASES:**  
  [[existing_test_cases]]

- **LAST ENDPOINT NAME:**  
  [[last_endpoint_name]]

**Output Format:**
Return a JSON array of objects, each with:
• description: Includes the parameters that needs to be changed for the relevant operation and a value example that violates the specification.
• test_case_name: The name of the test case in camelCase.

**Example:**
[
  {
    "description": "Change the `userId` parameter of the deleteUser request to a non-existing user ID, e.g., '00000000-0000-0000-0000-0000000000', to test deletion of a non-existing user.",
    "test_case_name": "deleteNonExistingUser"
  }
]

"""


class GenerateTestDataPrompt(PromptTemplate):
    def __init__(self):
        super().__init__(GENERATE_TEST_DATA, GENERATE_TEST_DATA_PLACEHOLDERS)

GENERATE_TEST_DATA_PLACEHOLDERS = ["test_case_description", "operation_value_flow", "endpoints_info"]
GENERATE_TEST_DATA = """
You are an API Testing Expert. Your task is to generate strictly invalid parameter values that fulfill a test case description based on a test case baseline while ensuring the values violate schema rules, formatting constraints, or other defined restrictions in a way that the system under test (SUT) cannot process them correctly. The goal is to test the system's ability to handle invalid inputs and ensure robust error handling.

You are provided with the following information:

1. A **Test Case Description** that defines what should be tested in the test case.
2. A **Test Baseline** in form of a list of operation Ids with all their request and response values representing a valid test scenario, showcasing the behavior of the system. Values can be either generated or dependent on other operation values.
3. A **Endpoint Information** with relevant Endpoint descriptions, including all restrictions and schema information.

Based on this information, you need to:

- Generate invalid parameter values for the test case description that strictly violate the intended behavior of the system under test.
- Ensure that invalid values would either result in parsing errors or system misbehavior if the SUT were to process them.
- Only generate values that are required to fulfill the test case description. These values will be substituted in the test baseline values.
- Also change the response status codes to match the test case's expected behavior. Do not change the response body, only the status code.
- Do not return any key-value pairs for parameters you do not have exact information about.
- If any information is missing in the test case description, rely on the detailed endpoint information.

Examples of invalid values include:

- Date strings in incorrect formats (e.g., "32-13-2023", "2023/31/13", or "INVALID_DATE").
- Strings that exceed length constraints or contain prohibited characters.
- Numbers that exceed defined ranges or contain invalid characters.

For null value handling, use these special formats:
- `null` → Parameter will be **sent with null value** in the request
- `"__undefined"` → Parameter will be **omitted** from the request entirely

---

### Provided Inputs:

**TEST CASE DESCRIPTION:**
[[test_case_description]]

**TEST BASELINE:**
[[operation_value_flow]]

**ENDPOINTS INFO:**
[[endpoints_info]]

### Output Format:
Respond with a JSON object containing the following:
- The keys should exactly match the keys in the test oracle.
- For body values use the flatten keys with dot notation (e.g., "<operationId>.request.body.user.userId").
- For query parameters, use the format "<operationId>.request.query_params.<paramName>".
- For path parameters, use the format "<operationId>.request.path_params.<paramName>".
- For header parameters, use the format "<operationId>.request.headers.<paramName>".
- For cookie parameters, use the format "<operationId>.request.cookies.<paramName>".
- The values should be the generated values fulfilling the test case.
- Use `null` to send explicit null values
- Use `"__undefined"` to omit parameters entirely

"""

GENERATE_TEST_DATA_EXAMPLE = """
### Example Output:
{
  "DeleteUser.request.path_params.userId": "00000000-0000-0000-0000-0000000000",
  "DeleteUser.response.status_code": 404
}

{
  "CreateUser.request.body.username": "__undefined",
  "CreateUser.response.status_code": 400
}

{
  "CreateOrder.request.body.productId": null,
  "CreateOrder.response.status_code": 400
}
"""

class TestFailureClassificationPrompt(PromptTemplate):
    def __init__(self):
        super().__init__(TEST_FAILURE_CLASSIFICATION_TEMPLATE, TEST_FAILURE_CLASSIFICATION_PLACEHOLDERS)

TEST_FAILURE_CLASSIFICATION_PLACEHOLDERS = ["test_case_data"]
TEST_FAILURE_CLASSIFICATION_TEMPLATE = """
You are an expert API testing judge. Your task is to analyze a failed test case and classify it as either a **True Positive** (legitimate failure of the System Under Test) or **False Positive** (incorrectly designed test case).

## Classification Definitions:

**True Positive (TP)**: The test case is correctly designed and the failure indicates a real bug or issue in the System Under Test (SUT). The API should have handled the request differently according to its specification.

**False Positive (FP)**: The test case is incorrectly designed or has invalid expectations. The API behavior is actually correct, but the test case wrongly expects different behavior.

## Analysis Framework:

1. **Test Intent Analysis**: Determine if this is a positive test (expecting success) or negative test (expecting specific error behavior)
   - Look at the test description to understand the intended scenario
   - Check if the test is designed to validate error handling or normal operation
2. **Request Validation**: Evaluate if the test request is appropriate for its intended purpose
3. **Response Analysis**: Evaluate if the API response is appropriate for the given request and test intent
   - Compare actual response with what the specification says should happen
   - Consider both success scenarios and error handling scenarios
4. **Test Assertion Logic**: Assess whether the test case's expectations align with its stated purpose
   - Do the assertions match the test description?
   - Are error expectations reasonable for negative tests?   - Are success expectations reasonable for positive tests?
5. **Specification Compliance**: Verify if the API behavior align with the OpenAPI specification

## Handling Specification Gaps:

When the expected behavior is **not explicitly stated** in the API specification, evaluate based on **industry best practices**.
If the specification is ambiguous or incomplete, consider what a **well-designed API** should do in the given scenario, and classify based on whether the actual behavior aligns with these principles.

## Provided Test Case Data:

```json
[[test_case_data]]
```

## Your Analysis Task:

1. **Examine the test case description** to understand the intended test scenario
2. **Review the API endpoints** and their specifications to understand the expected behavior
3. **Analyze the test execution results** including:
   - Request data (method, URL, headers, body)
   - Response data (headers, body, status codes)
   - Assertions that failed and their error messages
4. **Compare actual vs expected behavior** based on the API specification
5. **Consider edge cases and validation rules** defined in the API schema

## Decision Criteria:

**Classify as True Positive (TP) if:**
- **For Valid Request Tests**: The request is valid according to the API specification, but the API response violates the documented behavior
- **For Invalid Request Tests (Negative Tests)**: The request is intentionally invalid to test error handling, but the API fails to respond with the expected error response according to the specification
- The test assertions correctly match the test intent (expecting success for valid requests, expecting specific errors for invalid requests)
- The failure reveals a genuine bug in the SUT's behavior or error handling
- **When specification is unclear**: The API behavior violates industry best practices and common API design principles

**Classify as False Positive (FP) if:**
- **For Valid Request Tests**: The test request violates the API specification, but the test expects a successful response
- **For Invalid Request Tests**: The test sends invalid data but expects a successful response instead of the appropriate error response
- The API response is correct according to the specification, but the test assertions are wrong
- The test case misunderstands the intended API behavior (e.g., expecting success when failure is appropriate, or vice versa)
- **When specification is unclear**: The API behavior follows reasonable best practices, but the test expects different behavior without clear justification

## Output Format:

Provide your analysis in the following JSON format:

```json
{
  "reasoning": "Detailed explanation of your classification decision",
  "key_factors": [
    "List of key factors that influenced your decision"
  ],
  "api_behavior_assessment": "Assessment of whether the API behaved correctly",
  "test_design_assessment": "Assessment of whether the test case is well-designed",
  "classification": "TP" | "FP",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "recommendation": "Recommendation for next steps (fix API, fix test, investigate further, etc.)"
}
```

## Important Notes:

- Base your analysis strictly on the provided test data and API specification
- Consider both the technical correctness and the business logic aspects
- If unclear, lean towards "MEDIUM" or "LOW" confidence and recommend further investigation
- Focus on objective analysis rather than assumptions about intended behavior
- Remember that negative test cases are designed to test error handling, so some failures are expected

Analyze the provided test case data and provide your classification.
"""

class TestFailureClassificationPrompt2(PromptTemplate):
    def __init__(self):
        super().__init__(TEST_FAILURE_CLASSIFICATION_TEMPLATE_2, TEST_FAILURE_CLASSIFICATION_PLACEHOLDERS)

TEST_FAILURE_CLASSIFICATION_TEMPLATE_2 = """
You are an expert in API testing. Your task is to review a failed test case and classify it as either:

- **True Positive (TP)**: The test is correct, and the failure reveals a real issue in the API (behavior violates the OpenAPI spec or best practices).
- **False Positive (FP)**: The test is flawed — it misinterprets the API spec, expects incorrect behavior, or fails due to invalid assumptions.

If the spec is unclear, use standard API design principles to judge correctness.

## Test Case Input:

```json
[[test_case_data]]
```

## Output Format:
```json
{
  "reasoning": "Why you classified it as TP or FP",
  "key_factors": ["What influenced your decision"],
  "api_behavior_assessment": "Did the API behave correctly?",
  "test_design_assessment": "Was the test properly designed?",
  "classification": "TP" | "FP",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "recommendation": "What should be done next"
}
```

Base your judgment strictly on the test case and OpenAPI spec. Focus on objective reasoning and use medium/low confidence when uncertain.
"""