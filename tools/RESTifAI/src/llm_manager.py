import os
import json

from openai import APITimeoutError
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_community.callbacks.manager import get_openai_callback
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
from typing import List, Dict, Any

from config import MODEL_TEMPERATURE, MODEL_TIMEOUT
from spec_parser import OpenAPISpecParser, Endpoint
from operation_flow import OperationFlow
from llm_output_parser import LLMOutputParser, TestCaseDescription
from custom_request_sender import RequestData, ResponseData

from prompt_templates import ValidValueGenerationPrompt, UserInputTemplate, OperationSelectorPrompt, FixValueGenerationPrompt, GenerateStructuralNegativeTestDescriptionsPrompt, GenerateFunctionalNegativeTestDescriptionsPrompt, GenerateTestDataPrompt, OPERATON_SELECTOR_EXAMPLE, VALID_VALUE_GEN_EXAMPLE, GENERATE_TEST_DATA_EXAMPLE

load_dotenv()

class LLMTracker:
    """
    Class to track LLM usage and costs.
    This is a placeholder for future implementation.
    """
    def __init__(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_cost = 0.0

    def reset(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_cost = 0.0

    def add_usage(self, prompt_tokens: int, completion_tokens: int, cost: float):
        """
        Add usage to the tracker and update total cost.
        """
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens = self.prompt_tokens + self.completion_tokens
        self.total_cost += cost

    def get_total_tokens(self) -> int:
        """
        Get the total number of tokens used.
        """
        return self.total_tokens
    
    def get_total_cost(self) -> float:
        """
        Get the total cost of LLM usage.
        """
        return self.total_cost

class LLMManager:
    def __init__(self):
        self.model = None
        try:
            api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
            if not api_key:
                raise ValueError("AZURE_OPENAI_API_KEY environment variable is not set.")
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
            if not endpoint:
                raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is not set.")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "")
            if not api_version:
                raise ValueError("AZURE_OPENAI_API_VERSION environment variable is not set.")
            model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
            if not model_name:
                raise ValueError("AZURE_OPENAI_DEPLOYMENT environment variable is not set.")
            self.model = AzureChatOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version=api_version,
                azure_deployment=model_name,
                temperature=MODEL_TEMPERATURE,
                timeout=MODEL_TIMEOUT,
                max_tokens=None,
                max_retries=2,
            )

        except Exception as e:
            print(f"Failed to fetch Azure OpenAI variables, now tries OpenAI variables")
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set.")
            model_name = os.getenv("OPENAI_MODEL_NAME", "")
            if not model_name:
                raise ValueError("OPENAI_MODEL_NAME environment variable is not set.")
            self.model = ChatOpenAI(
                model_name=model_name,
                temperature=MODEL_TEMPERATURE,
                timeout=MODEL_TIMEOUT,
                max_tokens=None,
                max_retries=2,
                openai_api_key=api_key,
            )

        self.str_output_parser = StrOutputParser()
        
        self.llm_output_parser = LLMOutputParser()

        self.tracker = LLMTracker()

    def get_total_tokens(self) -> int:
        """
        Get the total number of tokens used by the LLM.
        """
        return self.tracker.get_total_tokens()
    
    def get_total_cost(self) -> float:
        """
        Get the total cost of LLM usage.
        """
        return self.tracker.get_total_cost()

    def is_running(self) -> bool:
        """
        Check if the LLM is running by invoking a simple prompt.
        """
        try:
            self.model.invoke("Is the LLM running?")
            return True
        except Exception as e:
            print(f"LLM is not running: {e}")
            return False

    @staticmethod
    def _get_json_block(text: str) -> dict:
        """
        Extracts a JSON block from the given text.
        """
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            json_str = text[start:end]
            data = json.loads(json_str)
        except (ValueError, json.JSONDecodeError):
            print("Error extracting JSON block from text.")
            raise json.JSONDecodeError("Invalid JSON format, cant apply json.loads() to output", text, 0)
        
        if not isinstance(data, dict):
            raise ValueError("Extracted JSON is not a dictionary.")
        return data
    
    @staticmethod
    def _get_json_array_block(text: str) -> dict:
        """
        Extracts a JSON array block from the given text.
        """
        try:
            start = text.index("[")
            end = text.rindex("]") + 1
            json_str = text[start:end]
            data = json.loads(json_str)
        except (ValueError, json.JSONDecodeError):
            print("Error extracting JSON array block from text.")
            raise json.JSONDecodeError("Invalid JSON format, cant apply json.loads() to output", text, 0)
        
        if not isinstance(data, list):
            raise ValueError("Extracted JSON is not a list.")
        return data
    
    def invoke_chain_with_token_tracking(self, chain, prompt) -> str:
        with get_openai_callback() as cb:
            response = chain.invoke(prompt)
            self.tracker.add_usage(cb.prompt_tokens, cb.completion_tokens, cb.total_cost)
        return response


    def generate_valid_values_for_endpoint(self, endpoint: Endpoint, operation_flow_history: OperationFlow, user_input: str = None) -> RequestData:
        parameters_str = self._format_parameters(endpoint.parameters if hasattr(endpoint, "parameters") else [])
        request_body_str = self._format_request_body(endpoint.request_body) if getattr(endpoint, "request_body", None) else "None"
        previous_values = operation_flow_history.previous_values_to_string()

        prompt_input = {
            "selected_operations": operation_flow_history.selected_operations,
            "test_plan_description": operation_flow_history.usage_guide,
            "operation_id": endpoint.operation_id,
            "method": endpoint.method.upper(),
            "path": endpoint.path,
            "parameters": parameters_str,
            "request_body": request_body_str,
            "previouse_values": previous_values,
        }

        error_message = ""
        max_retries = 3
        attempt = 0
        while attempt < max_retries:
            attempt += 1

            prompt = ValidValueGenerationPrompt().generate_prompt(prompt_input)
            if user_input:
                prompt += UserInputTemplate().generate_prompt({"user_input": user_input})
            prompt += VALID_VALUE_GEN_EXAMPLE
            prompt += error_message

            chain = self.model | self.str_output_parser
            try:
                llm_output = self.invoke_chain_with_token_tracking(chain, prompt)
            except APITimeoutError as e:
                print(f"LLM invocation timed out: {e}")
                break

            try:
                llm_output_json = self._get_json_block(llm_output)
            except json.JSONDecodeError as e:
                error_message = "\n### SYSTEM OUTPUT:" + str(llm_output) + "\n\n" + f"{e} Try to generate again.\n"
                continue
            
            # Ensure keys exist and body is properly handled
            llm_output_json.setdefault("path_params", {})
            llm_output_json.setdefault("query_params", {})
            llm_output_json.setdefault("headers", {})
            llm_output_json.setdefault("cookies", {})
            llm_output_json.setdefault("body", None)

            try:
                request_data = self.llm_output_parser.parse_generated_params(llm_output_json, operation_flow_history)
            except ValueError as e:
                print(f"Error parsing input parameters: {e}")
                error_message = "\n### SYSTEM OUTPUT:" + json.dumps(llm_output, indent=2) + "\n\n" + f"Error parsing input parameters: {e}. Try to generate again.\n"
                continue
            return request_data, llm_output_json
        
        print(f"Failed to generate input for endpoint {endpoint.operation_id} after {max_retries} attempts.")
        return None, None

    def _format_parameters(self, parameters: list) -> str:
        if not parameters:
            return "None"
        lines = []
        for param in parameters:
            name = param.get("name", "")
            location = param.get("in", "")
            required = param.get("required", False)
            description = param.get("description", "")
            lines.append(f"- {name} (in: {location}, required: {required}): {description}")
        return "\n".join(lines)

    def _format_request_body(self, request_body: dict) -> str:
        if not request_body:
            return "None"
        # Simple string representation of the schema dict
        return str(request_body)

    def fix_values_for_endpoint(self, endpoint: Endpoint, operation_flow_history: OperationFlow, response_data: ResponseData, raw_llm_output: dict, status_code: int, user_input: str = None) -> RequestData:
        """
        Fixes the values for the endpoint based on the response data and the status code.
        Returns a RequestData object with updated values.
        """
        parameters_str = self._format_parameters(endpoint.parameters if hasattr(endpoint, "parameters") else [])
        request_body_str = self._format_request_body(endpoint.request_body) if getattr(endpoint, "request_body", None) else "None"
        previous_values = operation_flow_history.previous_values_to_string()

        prompt_input = {
            "test_plan_description": operation_flow_history.usage_guide,
            "operation_id": endpoint.operation_id,
            "method": endpoint.method.upper(),
            "path": endpoint.path,
            "parameters": parameters_str,
            "request_body": request_body_str,
            "previouse_values": previous_values,
            "failed_values": json.dumps(raw_llm_output, indent=2),
            "error_response": response_data.body,
            "status_code": status_code,
        }

        prompt = FixValueGenerationPrompt().generate_prompt(prompt_input)
        if user_input:
            prompt += UserInputTemplate().generate_prompt({"user_input": user_input})
        prompt += VALID_VALUE_GEN_EXAMPLE

        max_retries = 3
        attempt = 0
        while attempt < max_retries:
            attempt += 1

            chain = self.model | self.str_output_parser
            try:
                llm_output = self.invoke_chain_with_token_tracking(chain, prompt)
            except APITimeoutError as e:
                print(f"LLM invocation timed out: {e}")
                break

            try:
                llm_output_json = self._get_json_block(llm_output)
            except json.JSONDecodeError as e:
                print(f"Error invoking LLM: {e}")
                prompt + "\n" + str(llm_output) + "\n\n" + f"{e} Try to generate again.\n"
                continue
            
            # Ensure keys exist and body is properly handled
            llm_output_json.setdefault("path_params", {})
            llm_output_json.setdefault("query_params", {})
            llm_output_json.setdefault("headers", {})
            llm_output_json.setdefault("cookies", {})
            llm_output_json.setdefault("body", None)

            try:
                request_data = self.llm_output_parser.parse_generated_params(llm_output_json, operation_flow_history)
            except ValueError as e:
                print(f"Error parsing input parameters: {e}")
                prompt += "\n" + json.dumps(llm_output, indent=2) + "\n\n" + f"Error parsing input parameters: {e}. Try to generate again.\n"
                continue
            return request_data, llm_output_json
        
        print(f"Failed to generate input for endpoint {endpoint.operation_id} after {max_retries} attempts.")
        return None

    def select_operations(self, endpoints: List[Endpoint], operation_id: str, user_input: str = None) -> dict:
        """
        Combined LLM call to select endpoints and specify required parameters from previous responses.
        Returns a dict with:
          - 'selected_operations': list of operation Ids needed
        """
        endpoints_reduced_info = OpenAPISpecParser.filter_2xx_responses(endpoints)
        endpoints_info = OpenAPISpecParser.endpoints_to_string(endpoints_reduced_info)

        prompt_input = {
            "endpoints_info": endpoints_info,
            "operation_id": operation_id,
        }

        error_message = ""
        max_retries = 3
        attempt = 0
        while attempt < max_retries:
            attempt += 1

            prompt = OperationSelectorPrompt().generate_prompt(prompt_input)
            if user_input:
                prompt += UserInputTemplate().generate_prompt({"user_input": user_input})
            prompt += OPERATON_SELECTOR_EXAMPLE
            prompt += error_message

            chain = self.model | self.str_output_parser 
            try:
                llm_output = self.invoke_chain_with_token_tracking(chain, prompt)
            except APITimeoutError as e:
                print(f"LLM invocation timed out: {e}")
                break

            try:
                llm_output_json = self._get_json_block(llm_output)
            except json.JSONDecodeError as e:
                print(f"Error invoking LLM: {e}")
                error_message = f"\n{llm_output}\n\nOutput is not valid JSON: {e}. Try to generate again.\n"
                continue

            try:
                operation_sequence, usage_guide = self.llm_output_parser.parse_operation_sequence(llm_output_json, endpoints, operation_id)
            except ValueError as e:
                print(f"Error parsing operation sequence: {e}")
                error_message = "\n" + json.dumps(llm_output, indent=2) + "\n\n" + f"Error parsing operation sequence: {e}. Try to generate again.\n"
                continue

            print(f"Selected operations: {operation_sequence}")

            return operation_sequence, usage_guide
        return [operation_id], "No usage guide available"

    def generate_structural_negative_test_case_descriptions(self, operation_flow: OperationFlow, endpoints: List[Endpoint]) -> List[TestCaseDescription]:
        """
        Generate negative test case descriptions for the given operation flow.
        """
        baseline_data = operation_flow.values_with_refs_to_string()
        endpoints_info = OpenAPISpecParser.endpoints_to_string(endpoints)
        
        # Get the last endpoint name from the selected operations
        last_endpoint_name = operation_flow.selected_operations[-1]

        prompt_input = {
            "operations": operation_flow.selected_operations,
            "baseline_data": baseline_data,
            "endpoints_info": endpoints_info,
            "last_endpoint_name": last_endpoint_name,
        }

        error_message = ""
        max_retries = 3
        attempt = 0
        while attempt < max_retries:
            attempt += 1

            prompt = GenerateStructuralNegativeTestDescriptionsPrompt().generate_prompt(prompt_input)
            prompt += error_message

            chain = self.model | self.str_output_parser
            try:
                llm_output = self.invoke_chain_with_token_tracking(chain, prompt)
            except APITimeoutError as e:
                print(f"LLM invocation timed out: {e}")
                break

            try:
                llm_output_json = self._get_json_array_block(llm_output)
            except json.JSONDecodeError as e:
                print(f"Error invoking LLM: {e}")
                error_message = "\n" + str(llm_output) + "\n\n" + f"{e} Try to generate again.\n"
                continue

            try:
                test_case_descriptions = self.llm_output_parser.parse_test_case_descriptions(llm_output_json)
            except ValueError as e:
                print(f"Error parsing test case descriptions: {e}")
                error_message = "\n" + json.dumps(llm_output, indent=2) + "\n\n" + f"Error parsing test case descriptions: {e}. Try to generate again.\n"
                continue
        
            return test_case_descriptions
        return []
    
    def generate_functional_negative_test_case_descriptions(self, operation_flow: OperationFlow, endpoints: List[Endpoint], existing_test_cases: List[str] = None) -> List[TestCaseDescription]:
        """
        Generate functional negative test case descriptions for the given operation flow.
        These test cases focus on business logic violations rather than structural/schema violations.
        
        Args:
            operation_flow: The operation flow to generate test cases for
            endpoints: The relevant endpoints for the operation flow
            existing_test_cases: List of existing test cases to avoid duplicating
            
        Returns:
            List of test case descriptions
        """
        baseline_data = operation_flow.values_with_refs_to_string()
        endpoints_info = OpenAPISpecParser.endpoints_to_string(endpoints)
        
        # Get the last endpoint name from the selected operations
        last_endpoint_name = operation_flow.selected_operations[-1]

        existing_test_cases_str = json.dumps(existing_test_cases) if existing_test_cases else "[]"
        
        prompt_input = {
            "operations": operation_flow.selected_operations,
            "baseline_data": baseline_data,
            "endpoints_info": endpoints_info,
            "existing_test_cases": existing_test_cases_str,
            "last_endpoint_name": last_endpoint_name,
        }

        error_message = ""
        max_retries = 3
        attempt = 0
        while attempt < max_retries:
            attempt += 1

            prompt = GenerateFunctionalNegativeTestDescriptionsPrompt().generate_prompt(prompt_input)
            prompt += error_message

            chain = self.model | self.str_output_parser
            try:
                llm_output = self.invoke_chain_with_token_tracking(chain, prompt)
            except APITimeoutError as e:
                print(f"LLM invocation timed out: {e}")
                break

            try:
                llm_output_json = self._get_json_array_block(llm_output)
            except json.JSONDecodeError as e:
                print(f"Error invoking LLM: {e}")
                error_message = "\n" + str(llm_output) + "\n\n" + f"{e} Try to generate again.\n"
                continue

            try:
                test_case_descriptions = self.llm_output_parser.parse_test_case_descriptions(llm_output_json)
            except ValueError as e:
                print(f"Error parsing test case descriptions: {e}")
                error_message = "\n" + json.dumps(llm_output, indent=2) + "\n\n" + f"Error parsing test case descriptions: {e}. Try to generate again.\n"
                continue
        
            return test_case_descriptions
        return []
    
    def generate_invalid_values_from_test_case_description(self, test_case_description: TestCaseDescription, operation_value_flow: str,  endpoints: List[Endpoint], operation_value_flow_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate values from the test case description.
        """
        endpoints_info = OpenAPISpecParser.endpoints_to_string(endpoints)

        prompt_input = {
            "test_case_description": test_case_description,
            "operation_value_flow": operation_value_flow,
            "endpoints_info": endpoints_info,
        }

        error_message = ""
        max_retries = 3
        attempt = 0
        while attempt < max_retries:
            attempt += 1

            prompt = GenerateTestDataPrompt().generate_prompt(prompt_input)
            prompt += GENERATE_TEST_DATA_EXAMPLE
            prompt += error_message

            chain = self.model | self.str_output_parser
            try:
                llm_output = self.invoke_chain_with_token_tracking(chain, prompt)
            except APITimeoutError as e:
                print(f"LLM invocation timed out: {e}")
                break

            try:
                llm_output_json = self._get_json_block(llm_output)
            except json.JSONDecodeError as e:
                print(f"Error invoking LLM: {e}")
                error_message = "\n" + str(llm_output) + "\n\n" + f"{e} Try to generate again.\n"
                continue

            try:
                test_case_values = self.llm_output_parser.parse_test_case_values(llm_output_json, operation_value_flow_dict)
            except ValueError as e:
                print(f"Error parsing input parameters: {e}")
                error_message = "\n" + json.dumps(llm_output, indent=2) + "\n\n" + f"Error parsing input parameters: {e}. Try to generate again.\n"
                continue
        
            return test_case_values
        return None