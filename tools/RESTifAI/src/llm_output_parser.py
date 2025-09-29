from typing import Dict, Any, List
from spec_parser import Endpoint
from operation_flow import OperationFlow, OperationParameter, ParameterSource, flatten_body_data, RequestData
import json
from dataclasses import dataclass

@dataclass
class TestCaseDescription:
    description: str
    test_name: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the TestCaseDescription object to a dictionary"""
        return {
            "description": self.description,
            "test_name": self.test_name
        }
    
    def to_string(self) -> str:
        """Convert the TestCaseDescription object to a string representation"""
        return f"Test: {self.test_name} - {self.description}"

class LLMOutputParser:
    @staticmethod
    def _parse_params(previous_values: Dict[str, Any], operaton_dict: Dict[str, Any]) -> Dict[str, OperationParameter]:
        """
        Parse parameters from the operation dictionary using the new placeholder format.
        Supports multiple placeholders within a single value.
        
        :param previous_values: A dictionary containing previous values for dependent parameters.
        :param operaton_dict: New format: {"name": "{{CreateUser.response.body.userId}}" or "literal_value" or "text with {{placeholder1}} and {{placeholder2}}"}
        """
        import re
        
        param_dict = {}
        if not operaton_dict:
            return {}
            
        # Regex pattern to find all placeholders in format {{...}}
        placeholder_pattern = r'\{\{([^}]+)\}\}'
        
        for k, v in operaton_dict.items():
            # Handle values that may contain placeholders
            if isinstance(v, (str, int, float, bool)) or v is None:
                # For string values, check for placeholders
                if isinstance(v, str):
                    # Find all placeholders in the string
                    placeholder_matches = re.findall(placeholder_pattern, v)
                    
                    if placeholder_matches:
                        # Check if all placeholders exist in previous_values
                        missing_placeholders = []
                        for placeholder_key in placeholder_matches:
                            placeholder_key = placeholder_key.strip()
                            if placeholder_key not in previous_values:
                                missing_placeholders.append(placeholder_key)
                        
                        if missing_placeholders:
                            print(f"Warning: Placeholders {missing_placeholders} not found in previous values for parameter {k}. Available keys: {list(previous_values.keys())}")
                            raise ValueError(f"Placeholders {missing_placeholders} not found in previous values for parameter {k}. Available keys: {list(previous_values.keys())}")
                        
                        # If single placeholder that matches the entire string, treat as dependency
                        if len(placeholder_matches) == 1 and v == f"{{{{{placeholder_matches[0]}}}}}":
                            placeholder_key = placeholder_matches[0].strip()
                            param_dict[k] = OperationParameter(
                                value=previous_values[placeholder_key], 
                                source=ParameterSource.DEPENDENT, 
                                source_keys=[placeholder_key],
                                value_with_placeholder=v
                            )
                        else:
                            # Multiple placeholders or mixed content - replace all placeholders with actual values
                            replaced_value = v
                            source_keys = []
                            for placeholder_key in placeholder_matches:
                                placeholder_key = placeholder_key.strip()
                                placeholder_value = previous_values[placeholder_key]
                                replaced_value = replaced_value.replace(f"{{{{{placeholder_key}}}}}", str(placeholder_value))
                                source_keys.append(placeholder_key)
                            
                            param_dict[k] = OperationParameter(
                                value=replaced_value, 
                                source=ParameterSource.DEPENDENT, 
                                source_keys=source_keys,
                                value_with_placeholder=v
                            )
                    else:
                        # No placeholders - direct literal value
                        param_dict[k] = OperationParameter(value=v, source=ParameterSource.GENERATED)
                else:
                    # Non-string literal value (int, float, bool, None)
                    param_dict[k] = OperationParameter(value=v, source=ParameterSource.GENERATED)
            
            else:
                print(f"Warning: Invalid parameter format for {k}: {v}. Expected string, number, boolean, or null.")
                raise ValueError(f"Invalid parameter format for {k}: {v}. Expected string, number, boolean, or null.")
            
        return param_dict
    
    @staticmethod
    def _replace_placeholders(input_string: str, previous_values: Dict[str, Any]) -> Any:
        """
        Replace placeholders in the input string with values from previous_values.
        Placeholders are expected to be in the format {{key}}.
        
        :param input_string: The input string containing placeholders.
        :param previous_values: A dictionary containing previous values for dependent parameters.
        :return: The input string with placeholders replaced by actual values.
        """
        import re
        
        placeholder_pattern = r'\{\{([^}]+)\}\}'

        placeholder_matches = re.findall(placeholder_pattern, input_string)

        if placeholder_matches:
            missing_placeholders = []
            for placeholder_key in placeholder_matches:
                placeholder_key = placeholder_key.strip()
                if placeholder_key not in previous_values:
                    missing_placeholders.append(placeholder_key)
            
            if missing_placeholders:
                print(f"Warning: Placeholders {missing_placeholders} not found. Available keys: {list(previous_values.keys())}")
                raise ValueError(f"Placeholders {missing_placeholders} not found. Available keys: {list(previous_values.keys())}")
        
            if len(placeholder_matches) == 1 and input_string == f"{{{{{placeholder_matches[0]}}}}}":
                placeholder_key = placeholder_matches[0].strip()
                return previous_values[placeholder_key]
            else:
                replaced_value = input_string
                for placeholder_key in placeholder_matches:
                    placeholder_key = placeholder_key.strip()
                    placeholder_value = previous_values[placeholder_key]
                    replaced_value = replaced_value.replace(f"{{{{{placeholder_key}}}}}", str(placeholder_value))
                
                return replaced_value
        else:
            # No placeholders found, return the original string
            return input_string

    def _fill_body_placeholders(self, body, previous_values: Dict[str, Any]) -> Any:
        """
        Recursively fill placeholders in the template with values from the provided dictionary.
        """
        if isinstance(body, dict):
            return {k: self._fill_body_placeholders(v, previous_values) for k, v in body.items()}
        elif isinstance(body, list):
            return [self._fill_body_placeholders(item, previous_values) for item in body]
        elif isinstance(body, str):
            value = self._replace_placeholders(body, previous_values)
            return value
        else:
            return body

    def parse_generated_params(self, llm_output: Dict[str, Any], prev_operation_flow: OperationFlow) -> RequestData:
        """
        Parse input parameters from the generated input data.
        This function extracts path parameters, query parameters, headers, cookies, and body data.

        :param llm_output: The output from the LLM, expected to be a JSON object.
        :param prev_operation_flow: The previous operation flow containing previouse values.
        :return: A RequestData object containing the parsed parameters.
        :raises ValueError: If any of the parameters cannot be resolved or if there are issues with the input data.
        """
        previous_values = prev_operation_flow.previous_values_to_dict()
        
        request_data = RequestData()

        for source in ["path_params", "query_params", "headers", "cookies"]:
            try:
                request_data.__setattr__(source, self._parse_params(previous_values, llm_output.get(source, {})))
            except ValueError as e:
                raise ValueError(f"Error resolving {source}: {e}")

        body_data = llm_output.get("body", None)

        body_flatten = flatten_body_data(body_data, prefix="")

        try:
            parsed_body_flatten = self._parse_params(previous_values, body_flatten)
        except ValueError as e:
            raise ValueError(f"Error parsing body parameters: {e}")

        try:
            body_raw = self._fill_body_placeholders(body_data, previous_values)
        except ValueError as e:
            raise ValueError(f"Error filling placeholders in body template: {e}")

        request_data.body_flatten = parsed_body_flatten
        request_data.body = body_raw

        return request_data

    def parse_operation_sequence(self, llm_output: json, endpoints: List[Endpoint], operation_under_test: str):
        """
        Parse the operation sequence and usage guide from the LLM output.
        This function checks if the selected operations are valid and exist in the spec endpoints.

        :param llm_output: The output from the LLM, expected to be a JSON object.
        :param endpoints: The list of endpoints from the OpenAPI spec.
        :param operation_under_test: The operation ID that is currently being tested.
        :return: A tuple containing the selected operations and usage guide.
        :raises ValueError: If the LLM output is not a valid dict object or if the selected operations are not found in the spec endpoints.
        """
        operation_sequence = llm_output.get("operation_sequence", [])
        usage_guide = llm_output.get("usage_guide", "")

        if not operation_sequence:
            raise ValueError("No operation_sequence found in the LLM output.")

        for opid in operation_sequence:
            if not any((ep for ep in endpoints if ep.operation_id == opid)):
                print(f"Warning: operation Id {opid} not found in spec endpoints.")
                raise ValueError(f"Operation Id {opid} not found in spec endpoints.")

        last_operation = operation_sequence[-1] if operation_sequence else None

        if last_operation != operation_under_test:
            print(f"Warning: Last operation {last_operation} in operation sequence does not match the operation under test {operation_under_test}.")
            raise ValueError(f"Last operation {last_operation} in operation sequence does not match the operation under test {operation_under_test}.")

        return operation_sequence, usage_guide

    def parse_test_case_descriptions(self, llm_output) -> List[TestCaseDescription]:
        """
        Parse the test case descriptions from the LLM output.

        :param llm_output: The output from the LLM, expected to be a JSON object.
        :return: A list of InvalidTestCaseDescription objects.
        :raises ValueError: If the LLM output is not a valid dict object or if the test case descriptions are not in the expected format.
        """
        test_case_descriptions = []
        if llm_output == []:
            return test_case_descriptions

        if not isinstance(llm_output, list):
            raise ValueError("Invalid output format. Expected a list of dictionaries.")

        for description in llm_output:
            if not isinstance(description, dict):
                raise ValueError("Invalid output format. Expected a list of dictionaries.")
            
            if "description" not in description or "test_case_name" not in description:
                raise ValueError("Invalid output format. Expected 'description' and 'test_case_name' keys.")

            if not isinstance(description["description"], str) or not isinstance(description["test_case_name"], str):
                raise ValueError("Invalid output format. Expected 'description' and 'test_case_name' to be strings.")
            
            if description["description"] == "" or description["test_case_name"] == "":
                raise ValueError("Invalid output format. Expected 'description' and 'test_case_name' to be non-empty strings.")
            
            testcase_description = TestCaseDescription(
                description=description["description"],
                test_name=description["test_case_name"]
            )
            test_case_descriptions.append(testcase_description)

        return test_case_descriptions
    
    def parse_test_case_values(self, llm_output, operation_value_flow_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the test case values from the LLM output.

        :param llm_output: The output from the LLM, expected to be a JSON object.
        :return: A dictionary of test case values.
        :raises ValueError: If the LLM output is not a valid dict object or if the test case values are not in the expected format.
        """
        ACCEPTED_PREFIXES = ["request.path_params", "request.query_params", "request.headers", "request.cookies", "request.body", "response.status_code"]

        if not isinstance(llm_output, dict):
            raise ValueError("Invalid output format. Expected a json array.")
        llm_output
        for k, v in llm_output.items():
            if not isinstance(k, str):
                print(f"Warning: Key {k} is not a string. Expected a string key.")
                raise ValueError(f"Key {k} is not a string. Expected a string key.")
            k_split = k.split(".", 1)[1] if "." in k else k
            if not any(k_split.startswith(prefix) for prefix in ACCEPTED_PREFIXES):
                print(f"Warning: Key {k} does not start with a recognized prefix. Expected one of {ACCEPTED_PREFIXES}")
                raise ValueError(f"Key {k} does not start with a recognized prefix. Expected one of {ACCEPTED_PREFIXES}")
            if k in operation_value_flow_dict:
                if v == "__undefined":
                    operation_value_flow_dict.pop(k, None)
                else:
                    operation_value_flow_dict[k] = v
                continue

            flow_key_with_prefix_k = self.get_keys_with_prefix(k, operation_value_flow_dict)
            if flow_key_with_prefix_k:
                if v != "__undefined":
                    operation_value_flow_dict[k] = v
                for flow_key in flow_key_with_prefix_k:
                    operation_value_flow_dict.pop(flow_key, None)
                continue

            if v != "__undefined":
                operation_value_flow_dict.update({k: v})

        return operation_value_flow_dict

    def get_keys_with_prefix(self, prefix: str, dictionary: Dict[str, Any]) -> List[str]:
        """
        Get all keys in the dictionary that start with the specified prefix.
        
        :param prefix: The prefix to search for.
        :param dictionary: The dictionary to search in.
        :return: A list of keys that start with the specified prefix.
        """
        return [k for k in dictionary.keys() if k.startswith(prefix)]


if __name__ == "__main__":
    #test parse_test_case_values
    parser = LLMOutputParser()

    operation_value_flow_dict = {
        "addPet.request.headers.Content-Type": "application/json",
        "addPet.request.body.id": 10001,
        "addPet.request.body.category.id": 10,
        "addPet.request.body.category.name": "Dogs",
        "addPet.request.body.name": "Fido",
        "addPet.request.body.photoUrls[0]": "http://example.com/photos/fido1.jpg",
        "addPet.request.body.photoUrls[1]": "http://example.com/photos/fido2.jpg",
        "addPet.request.body.tags[0].id": 201,
        "addPet.request.body.tags[0].name": "friendly",
        "addPet.request.body.tags[1].id": 202,
        "addPet.request.body.tags[1].name": "playful",
        "addPet.request.body.status": "available",
        "addPet.response.body.id": 10001,
        "addPet.response.body.category.id": 10,
        "addPet.response.body.category.name": "Dogs",
        "addPet.response.body.name": "Fido",
        "addPet.response.body.photoUrls[0]": "http://example.com/photos/fido1.jpg",
        "addPet.response.body.photoUrls[1]": "http://example.com/photos/fido2.jpg",
        "addPet.response.body.tags[0].id": 201,
        "addPet.response.body.tags[0].name": "friendly",
        "addPet.response.body.tags[1].id": 202,
        "addPet.response.body.tags[1].name": "playful",
        "addPet.response.body.status": "available",
        "addPet.response.headers.Date": "Wed, 11 Jun 2025 08:13:15 GMT",
        "addPet.response.headers.Content-Type": "application/json",
        "addPet.response.headers.Transfer-Encoding": "chunked",
        "addPet.response.headers.Connection": "keep-alive",
        "addPet.response.headers.Access-Control-Allow-Origin": "*",
        "addPet.response.headers.Access-Control-Allow-Methods": "GET, POST, DELETE, PUT",
        "addPet.response.headers.Access-Control-Allow-Headers": "Content-Type, api_key, Authorization",
        "addPet.response.headers.Server": "Jetty(9.2.9.v20150224)",
        "addPet.response.status_code": 200
    }

    llm_output = {
        "addPet.request.headers": "application/adfadfadfadf",
        "addPet.request.body.id": "__undefined",
        "addPet.request.body.category": "{{CreateCategory.response.body}}",
        "addPet.request.body.name": "Fido2",
        "addPet.request.body.photoUrls": None,
        "addPet.request.body.tags[0]": "__undefined",
        "addPet.response.status_code": 405,
        "addPet.request.body.unknownProperty": ["unknownValue1", "unknownValue2"],
    }

    try:
        parsed_values = parser.parse_test_case_values(llm_output, operation_value_flow_dict)
        print("Parsed values:", json.dumps(parsed_values, indent=2))
    except ValueError as e:
        print("Error:", e)