from operation_flow import OperationFlow, RequestData, ResponseData, OperationParameter, ParameterSource, unflatten_body_data
from llm_output_parser import TestCaseDescription
from test_report_manager import TestReportManager
from src.script_executor import ScriptExecutor
from config import Paths

import subprocess
import json
import shutil
from typing import Dict, Any, List, Tuple
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import re

def prepare_js_value(value):
    """
    Prepares a value for use in JavaScript by converting Python data types
    to their appropriate JavaScript representations.
    """
    # Handle special sentinel values for null handling
    if value == "__undefined":
        return "undefined"
    
    if isinstance(value, bool):
        # Convert Python boolean to JavaScript boolean
        return "true" if value else "false"
    elif value is None:
        # Convert Python None to JavaScript null
        return "null"
    elif isinstance(value, (int, float)):
        # Numbers are fine as-is
        return value
    elif isinstance(value, Decimal):
        # Convert Decimal to float
        return float(value)
    elif isinstance(value, datetime):
        # Convert datetime to ISO 8601 string
        return json.dumps(value.isoformat())
    elif isinstance(value, str):
        # Escape the string for JavaScript and wrap in single quotes
        escaped_value = value.replace("'", "\\'")
        return f"'{escaped_value}'"
    elif isinstance(value, (list, dict)):
        # Use json.dumps for lists and dictionaries
        return json.dumps(value)
    else:
        # Raise an error for unsupported types
        raise TypeError(f"Unsupported data type: {type(value)}")
    

class PostmanCollectionBuilder:
    GET_RESPONSE_BODY_VALUE_JS_FUNCTION = [
        "",
        "   /**",
        "    * Gets a value from a nested object using a flattened key path",
        "    * @param {Object} obj - The object to extract from",
        "    * @param {string} path - Flattened key path (e.g., 'users[1].role.id')",
        "    * @return {*} The extracted value or undefined if not found",
        "    */",
        "   function getValueByPath(obj, path) {",
        "       // Handle array notation by splitting correctly",
        "       const parts = [];",
        "       let currentPart = '';",
        "       let inBracket = false;",
        "",
        "       // Parse the path maintaining array indexes",
        "       for (let i = 0; i < path.length; i++) {",
        "           const char = path[i];",
        "           if (char === '.' && !inBracket) {",
        "               if (currentPart) parts.push(currentPart);",
        "               currentPart = '';",
        "           } else if (char === '[') {",
        "               inBracket = true;",
        "               parts.push(currentPart);",
        "               currentPart = '[';",
        "           } else if (char === ']') {",
        "               inBracket = false;",
        "               currentPart += ']';",
        "               parts.push(currentPart);",
        "               currentPart = '';",
        "           } else {",
        "               currentPart += char;",
        "           }",
        "       }",
        "       if (currentPart) parts.push(currentPart);",
        "",
        "       // Navigate through the object",
        "       let current = obj;",
        "       for (const part of parts) {",
        "           if (!current) return undefined;",
        "",
        "           if (part.startsWith('[') && part.endsWith(']')) {",
        "               // Handle array index",
        "               const index = parseInt(part.substring(1, part.length - 1));",
        "               if (!Array.isArray(current) || current.length <= index) {",
        "                   return undefined;",
        "               }",
        "               current = current[index];",
        "           } else {",
        "               // Handle object property",
        "               current = current[part];",
        "           }",
        "       }",
        "       return current;",
        "   }",
        "",
    ]

    def __init__(self, base_url: str, test_case_description: TestCaseDescription, output_dir: Path = None):
        self.output_dir = output_dir or Paths.get_tests()
        self.base_url = base_url.rstrip('/')
        self.collection = {
            "info": {
                "name": f"{test_case_description.test_name}",
                "description": f"{test_case_description.description}",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "item": [],
            "event": [
                {
                    "listen": "prerequest", 
                    "script": {
                        "type": "text/javascript",
                        "exec": self._build_prerequest_script()
                    }
                }
            ]
        }

    def _build_prerequest_script(self):
        """Build the prerequest script"""
        script_lines = [
            f"pm.environment.set('baseUrl', '{self.base_url}');"
        ]
        
        return script_lines

    def _encode_query_parameters(self, test_case_values: Dict[str, Any]) -> Dict[str, Any]:
        """
        URL-encode query parameter values that contain special characters.
        
        Args:
            test_case_values: Dictionary of test case values
            
        Returns:
            Updated dictionary with properly encoded query parameter values
        """
        import urllib.parse
        
        updated_values = test_case_values.copy()
        
        for key, value in test_case_values.items():
            # Check if this is a query parameter
            if ".request.query_params." in key:
                # Get the actual value to encode
                actual_value = None
                
                if isinstance(value, OperationParameter):
                    if value.source == ParameterSource.GENERATED:
                        actual_value = value.value
                    # Don't encode dependent parameters as they use variable placeholders
                    elif value.source == ParameterSource.DEPENDENT:
                        continue
                else:
                    actual_value = value
                
                # URL encode if the value contains special characters that need encoding
                if isinstance(actual_value, str):
                    # Check if value contains JSON-like content or other special characters
                    if (actual_value.startswith('{') and actual_value.endswith('}')) or \
                       any(char in actual_value for char in ['&', '=', '?', '#', ' ', '"']):
                        
                        encoded_value = urllib.parse.quote(actual_value, safe='')
                        
                        # Update the value in the dictionary
                        if isinstance(value, OperationParameter):
                            # Create a new OperationParameter with encoded value
                            updated_param = OperationParameter(
                                value=encoded_value,
                                source=value.source,
                                source_keys=value.source_keys,
                                value_with_placeholder=value.value_with_placeholder
                            )
                            updated_values[key] = updated_param
                        else:
                            updated_values[key] = encoded_value
        
        return updated_values
    
    def _generate_body_obj(self, request_data: RequestData, test_case_values, operation_id: str, headers) -> Dict[str, Any]:
        body = {}
        unflattened_body = None
        if request_data.body_flatten:
            for k, v in request_data.body_flatten.items():
                param = k.removeprefix("request.body.")
                collection_key = f"{operation_id}.{k}"
                if isinstance(v, OperationParameter) and v.source == ParameterSource.DEPENDENT:
                    body[param] = f"{{{{{collection_key}}}}}"
                elif isinstance(v, OperationParameter) and v.source == ParameterSource.GENERATED:
                    body[param] = v.value
                else:
                    body[param] = v
            unflattened_body = unflatten_body_data(body)
        #if request body is not a dict
        elif f"{operation_id}.request.body" in test_case_values:
            body_value = test_case_values.get(f"{operation_id}.request.body", None)
            if isinstance(body_value, OperationParameter) and body_value.source == ParameterSource.DEPENDENT:
                collection_key = f"{operation_id}.request.body"
                unflattened_body = f"{{{{{collection_key}}}}}"
            elif isinstance(body_value, OperationParameter) and body_value.source == ParameterSource.GENERATED:
                unflattened_body = body_value.value
            else:
                unflattened_body = body_value

        formatted_body = None
        if unflattened_body:
            to_url_encode_types = ["application/x-www-form-urlencoded", "multipart/form-data"]
            if any(v for v in headers if v["key"] == "Content-Type" and v["value"].lower() in to_url_encode_types):
                formatted_body = {
                    "mode": "urlencoded",
                    "urlencoded": [
                        {
                            "key": k,
                            "value": str(v),
                            "type": "text"
                        } for k, v in unflattened_body.items()
                    ]
                }
            else:
                formatted_body = {
                    "mode": "raw",
                    "raw": json.dumps(unflattened_body, indent=2),
                    "options": {
                        "raw": {
                            "language": "json"
                        }
                    }
                }
        
        return formatted_body

    def _generate_url_obj(self, path: str, request_data: RequestData, operation_id: str) -> Dict[str, Any]:
        path_parts = path.strip('/').split('/')
        variables = []
        formatted_path_parts = []
        raw_path_parts = []

        placeholder_pattern = r'\{([^}]+)\}'

        for part in path_parts:
            param_names = re.findall(placeholder_pattern, part)
            
            if param_names:
                processed_part = part
                
                for param_name in param_names:
                    param_found = False
                    for k, v in request_data.path_params.items():
                        param = k.removeprefix("request.path_params.")
                        
                        if param != param_name:
                            continue
                        
                        param_found = True
                        full_variable_name = f"{operation_id}.{k}"
                        processed_part = processed_part.replace(f"{{{param_name}}}", f"{{{{{full_variable_name}}}}}")
                        break
                    
                    if not param_found:
                        processed_part = processed_part.replace(f"{{{param_name}}}", param_name)
                
                formatted_path_parts.append(processed_part)
                raw_path_parts.append(processed_part)
            else:
                formatted_path_parts.append(part)
                raw_path_parts.append(part)

        path_part = '/'.join(raw_path_parts)
        if path_part:
            raw_url = f"{{{{baseUrl}}}}/{path_part}"
        else:
            raw_url = "{{baseUrl}}"

        query_params = self._process_parameters(request_data.query_params, "query_params", operation_id)

        if query_params:
            query_string = "&".join([f"{param['key']}={param['value']}" for param in query_params])
            raw_url += f"?{query_string}"

        url_obj = {
            "raw": raw_url,
            "host": ["{{baseUrl}}"],
            "path": formatted_path_parts
        }

        if variables:
            url_obj["variable"] = variables

        if query_params:
            url_obj["query"] = query_params

        return url_obj
        

    def add_postman_test_case(self, operation_flow: OperationFlow, test_case_values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a test case directly to the collection root (not as a subfolder).
        """
        # URL-encode query parameters that need encoding
        test_case_values = self._encode_query_parameters(test_case_values)
        
        for operation in operation_flow.executed_operations:
            operation_id = operation.operation_id
            method = operation.method.upper()
            path = operation.path

            self.add_request_to_collection(operation_id, method, path, test_case_values)

    def add_request_to_collection(self, operation_id: str, method: str, path: str, test_case_values: Dict[str, Any]):
        request_data, response_data = self.parse_operation(operation_id, test_case_values)

        if not isinstance(request_data, RequestData):
            raise ValueError(f"Invalid request data for operation {operation_id}")
        if not isinstance(response_data, ResponseData):
            raise ValueError(f"Invalid response data for operation {operation_id}")
            
        set_request_variables_script = []
        set_request_variables_script.append("let template = '';")
        for i, (k, v) in enumerate(test_case_values.items()):
            if not k.startswith(f"{operation_id}.request."):
                continue
            if isinstance(v, OperationParameter) and v.source == ParameterSource.DEPENDENT:
                if len(v.source_keys) == 1 and f"{{{{{v.source_keys[0]}}}}}" == v.value_with_placeholder:
                    source_key = v.source_keys[0]
                    set_request_variables_script.append(f"pm.collectionVariables.set('{k}', pm.collectionVariables.get('{source_key}'));")
                else:
                    value_template = v.value_with_placeholder
                    set_request_variables_script.append(f"template = `{value_template}`;")
                    for source_key in v.source_keys:
                        set_request_variables_script.append(f"template = template.replace(`{{{{{source_key}}}}}`, pm.collectionVariables.get('{source_key}'));")
                    set_request_variables_script.append(f"pm.collectionVariables.set('{k}', template);")
            elif isinstance(v, OperationParameter) and v.source == ParameterSource.GENERATED:
                set_request_variables_script.append(f"pm.collectionVariables.set('{k}', {prepare_js_value(v.value)});")
            else:
                set_request_variables_script.append(f"pm.collectionVariables.set('{k}', {prepare_js_value(v)});")

        
        headers = self._process_parameters(request_data.headers, "headers", operation_id)
        cookies = self._process_parameters(request_data.cookies, "cookies", operation_id)
        body = self._generate_body_obj(request_data, test_case_values, operation_id, headers) 
        url = self._generate_url_obj(path, request_data, operation_id)

        expected_response_body_fields = []

        for k, v in test_case_values.items():
            if k.startswith(f"{operation_id}.response.body."):
                field_path = k.replace(f"{operation_id}.response.body.", "")
                expected_response_body_fields.append(field_path)

        script = []
        if 200 <= response_data.status_code < 300:
            script =  [
                "pm.test('Response status code is 2xx', function () {",
                "    pm.expect(pm.response.code || pm.response.status).to.be.within(200, 299);",
                "});",
                "",
                "try {",
            ]
            # set response variables
            if expected_response_body_fields:
                script.extend(self.GET_RESPONSE_BODY_VALUE_JS_FUNCTION)
                script.extend([
                    "    // Extract response body values",
                    "    const responseJson = pm.response.json();",
                    "",
                    "    // Store expected body fields",
                ])
                for i, field in enumerate(expected_response_body_fields):
                    script.append(f"    const x{i} = getValueByPath(responseJson, '{field}');")
                    script.append(f"    if (x{i} !== undefined) " + "{")
                    script.append(f"        pm.collectionVariables.set('{operation_id}.response.body.{field}', x{i});")
                    script.append("    }")

            script.extend([
                "",
                "    // Store response headers",
                "    pm.response.headers.each(function(header) {",
                f"        pm.collectionVariables.set('{operation_id}.response.headers.' + header.key, header.value);",
                "    });",
                "",
                "    // Store response cookies",
                "    pm.response.cookies.each(function(cookie) {",
                f"        pm.collectionVariables.set('{operation_id}.response.cookies.' + cookie.name, cookie.value);",
                "    });",
                "",
                "    // Store status code",
                f"    pm.collectionVariables.set('{operation_id}.response.status_code', pm.response.code);",
                "} catch (error) {",
                "    console.error('Failed to process response:', error.message);",
                "}"])
        elif 400 <= response_data.status_code < 500:
            script.append("pm.test('Response status code is 4xx', function () {")
            script.append("    pm.expect(pm.response.code || pm.response.status).to.be.within(400, 499);")
            script.append("});")

        new_item = {
            "name": operation_id,
            "request": {
                "method": method,
                "header": headers,
                "body": body,
                "cookies": cookies,
                "url": url
            },
            "event": [
                {
                    "listen": "test",
                    "script": {
                        "type": "text/javascript",
                        "exec": script
                    }
                },
                {
                    "listen": "prerequest",
                    "script": {
                        "type": "text/javascript",
                        "exec": set_request_variables_script
                    }
                }
            ]
        }
        
        # Add directly to collection root
        self.collection["item"].append(new_item)

    def save_to_file(self, file_name: str, create_subdirectory: bool = False, subdirectory_name: str = None) -> Path:
        output_dir = Path(__file__).parent / self.output_dir
        
        if create_subdirectory and subdirectory_name:
            output_dir = output_dir / subdirectory_name
        
        output_dir.mkdir(exist_ok=True, parents=True)
        
        file_path = output_dir / file_name
        
        with open(file_path, 'w') as f:
            json.dump(self.collection, f, indent=4)
        
        return file_path
    
    @staticmethod
    def parse_operation(operation_id: str, operation_value_flow: Dict[str, Any]) -> tuple[RequestData, ResponseData]:
        """
        Parse the operation value flow to extract request and response components.
        """
        operation_values = {}
        for k, v in operation_value_flow.items():
            if k.startswith(f"{operation_id}."):
                param_name = k[len(f"{operation_id}."):]
                operation_values.update({param_name: v})

        request_data = RequestData.from_dict(operation_values)
        response_data = ResponseData.from_dict(operation_values)

        return request_data, response_data

    def _process_parameters(self, params_dict: Dict[str, Any], param_type: str, operation_id: str) -> List[Dict[str, str]]:
        """
        Process request parameters (headers, cookies, query params) into Postman format.
        
        Args:
            params_dict: Dictionary of parameter names and values
            param_type: Type of parameter ('headers', 'cookies', or 'query_params')
        
        Returns:
            List of parameter objects in Postman format
        """
        result = []
        for k, v in params_dict.items():
            if not k.startswith(f"request.{param_type}."):
                continue

            param_name = k.removeprefix(f"request.{param_type}.")
            
            if param_name == "":
                continue

            if isinstance(v, OperationParameter) and v.source == ParameterSource.DEPENDENT:
                collection_key = f"{operation_id}.{k}"
                result.append({"key": param_name, "value": f"{{{{{collection_key}}}}}"})
            elif isinstance(v, OperationParameter) and v.source == ParameterSource.GENERATED:
                actual_value = v.value
                result.append({"key": param_name, "value": str(actual_value) if actual_value is not None else "null"})
            else:
                actual_value = v
                result.append({"key": param_name, "value": str(actual_value) if actual_value is not None else "null"})
        return result
    
    @staticmethod
    def execute_collection(collection_file: Path, environment_initializer: ScriptExecutor = None):
        """
        Execute a Postman collection file.
        
        Args:
            collection_file: Path to the collection file to execute (Path)
            environment_initializer: Environment initializer instance for initializing before each test case
        """
        if environment_initializer:
            environment_initializer.execute_script()
            
        try:
            # Generate a unique report file name based on the collection file
            reports_dir = Paths.get_reports()
            if not reports_dir:
                print("No reports directory available")
                return
                
            reports_dir.mkdir(exist_ok=True, parents=True)

            test_suite_name = collection_file.parent.name
            full_test_name = collection_file.stem.split('.')[0]  # Remove .postman_collection from the name
            
            newman_report_raw_file = reports_dir / f"{full_test_name}_report_raw.json"
            
            newman_path = shutil.which("newman")
            command = [newman_path, "run", str(collection_file), "--reporters", "json", "--reporter-json-export", str(newman_report_raw_file)]
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')

            if result.stderr != "":
                print(f"Error executing Postman collection: {result.stderr}")
            else:
                print(result.stdout)

            if newman_report_raw_file.exists():
                report_manager = TestReportManager()
                with open(newman_report_raw_file, "r", encoding="utf-8") as f:
                    report_data = json.load(f)

                report_manager.process_collection_results(test_suite_name, report_data)

                try:
                    newman_report_raw_file.unlink()
                except Exception as e:
                    print(f"Failed to delete report file {newman_report_raw_file}: {e}")

        except FileNotFoundError:
            print("Newman not found. Install it using: npm install -g newman")

    @staticmethod
    def execute_test_suite_collections(test_suite_folder: Path, environment_initializer: ScriptExecutor = None):
        """
        Execute all individual test case collections in a test suite folder.
        
        Args:
            test_suite_folder: Path to the test suite folder containing individual test case collections (Path)
            environment_initializer: Environment initializer instance for initializing before each test case
        """
        if not test_suite_folder.exists():
            print(f"Test suite folder not found: {test_suite_folder}")
            return

        collection_files = [f for f in test_suite_folder.iterdir() if f.name.endswith(".postman_collection.json")]
        
        if not collection_files:
            print(f"No Postman collections found in {test_suite_folder}")
            return

        print(f"Found {len(collection_files)} test case collections in {test_suite_folder}")
        
        for collection_file in collection_files:
            print(f"Executing test case collection: {collection_file.name}")
            PostmanCollectionBuilder.execute_collection(collection_file, environment_initializer)

    @staticmethod
    def execute_all_test_suites(tests_folder: Path = None, environment_initializer: ScriptExecutor = None):
        """
        Execute all test suites (folders) containing individual test case collections.
        
        Args:
            tests_folder: tests folder containing test suite subfolders (Path)
            environment_initializer: Environment initializer instance
        """
        if not tests_folder or not tests_folder.exists():
            print(f"Tests folder not found: {tests_folder}")
            return

        # Look for test suite folders (subdirectories)
        test_suite_folders = [
            folder for folder in tests_folder.iterdir() 
            if folder.is_dir() and not folder.name.startswith('.')
        ]

        if not test_suite_folders:
            print(f"No test suite folders found in {tests_folder}")
            return

        print(f"Found {len(test_suite_folders)} test suite folders")
        
        for test_suite_folder in test_suite_folders:
            suite_name = test_suite_folder.name
            print(f"\n{'='*60}")
            print(f"Executing test suite: {suite_name}")
            print(f"{'='*60}")
            PostmanCollectionBuilder.execute_test_suite_collections(test_suite_folder, environment_initializer)