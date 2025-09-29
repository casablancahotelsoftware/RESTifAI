from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union, Tuple
from enum import Enum
from requests import Response
import re
import json

from spec_parser import Endpoint


class OperationFlowResult(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    SERVER_ERROR = "server_error"


class ParameterSource(Enum):
    DEPENDENT = "dependent"
    GENERATED = "generated"


@dataclass
class OperationParameter:
    value: Any
    source: ParameterSource
    source_keys: Optional[List[str]] = None
    value_with_placeholder: str = None


def add_prefix_to_keys(dict: Dict[str, Any], prefix) -> Dict[str, Any]:
    items = {}
    for k, v in dict.items():
        new_key = f"{prefix}{k}"
        items[new_key] = v
    return items

def resolve_values(dict: Dict[str, OperationParameter]) -> Dict[str, Any]:
    """
    Replace OperationParameter objects in the dictionary with their values.
    """
    new_dict = {}
    for k, v in dict.items():
        if isinstance(v, OperationParameter):
            new_dict[k] = v.value
        else:
            new_dict[k] = v
    return new_dict

@dataclass
class RequestData:
    path_params: Dict[str, OperationParameter] = field(default_factory=dict)
    query_params: Dict[str, OperationParameter] = field(default_factory=dict)
    headers: Dict[str, OperationParameter] = field(default_factory=dict)
    cookies: Dict[str, OperationParameter] = field(default_factory=dict)
    body_flatten: Dict[str, OperationParameter] = field(default_factory=dict)
    body: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Flatten the request data into a single dictionary.
        This is useful for easier access to nested values.
        """

        flat_dict = {}
        flat_dict.update(add_prefix_to_keys(self.path_params, 'request.path_params.'))
        flat_dict.update(add_prefix_to_keys(self.query_params, 'request.query_params.'))
        flat_dict.update(add_prefix_to_keys(self.headers, 'request.headers.'))
        flat_dict.update(add_prefix_to_keys(self.cookies, 'request.cookies.'))
        flat_dict.update(add_prefix_to_keys(self.body_flatten, 'request.body.'))
        return flat_dict
    
    def resolve_path_params(self) -> Dict[str, Any]:
        return resolve_values(self.path_params)
    
    def resolve_query_params(self) -> Dict[str, Any]:
        return resolve_values(self.query_params)
    
    def resolve_headers(self) -> Dict[str, Any]:
        return resolve_values(self.headers)
    
    def resolve_cookies(self) -> Dict[str, Any]:
        return resolve_values(self.cookies)
    
    @staticmethod
    def from_dict(data: Dict[str, OperationParameter]):
        """
        Create a RequestData object from a dictionary.
        This is useful for initializing the object with data from an external source.
        """
        request_data = RequestData()
        request_data.path_params = {k: v for k, v in data.items() if k.startswith('request.path_params.')}
        request_data.query_params = {k: v for k, v in data.items() if k.startswith('request.query_params.')}
        request_data.headers = {k: v for k, v in data.items() if k.startswith('request.headers.')}
        request_data.cookies = {k: v for k, v in data.items() if k.startswith('request.cookies.')}
        request_data.body_flatten = {k: v for k, v in data.items() if k.startswith('request.body.')}
        return request_data


class ResponseData:
    status_code: int
    headers: Dict[str, Any] = field(default_factory=dict)
    cookies: Dict[str, Any] = field(default_factory=dict)
    body_flatten: Dict[str, Any] = field(default_factory=dict)
    body: Optional[Any] = None

    def __init__(self, response: Optional[Response] = None):
        if response is not None:
            self.status_code = response.status_code
            self.headers = dict(response.headers)
            self.cookies = response.cookies.get_dict()

            try:
                body = response.json()
                if isinstance(body, list) and len(body) > 10:
                    print("Response body is a list with more than 10 items, truncating to 10 items!")
                    body = body[:10]
            except ValueError:
                body = response.text

            self.body = body
            self.body_flatten = flatten_body_data(body, "response.body") if body is not None else {}
        else:
            self.status_code = None
            self.headers = {}
            self.cookies = {}
            self.body_flatten = {}
            self.body = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Flatten the response data into a single dictionary.
        This is useful for easier access to nested values.
        """
        flat_dict = {}
        flat_dict.update(self.body_flatten)
        flat_dict.update(add_prefix_to_keys(self.headers, 'response.headers.'))
        flat_dict.update(add_prefix_to_keys(self.cookies, 'response.cookies.'))
        flat_dict['response.status_code'] = self.status_code
        return flat_dict
    
    @staticmethod
    def from_dict(data: Dict[str, Any]):
        """
        Create a ResponseData object from a dictionary.
        This is useful for initializing the object with data from an external source.
        """
        response_data = ResponseData()
        response_data.status_code = data.get('response.status_code', 200)
        response_data.headers = {k: v for k, v in data.items() if k.startswith('response.headers.')}
        response_data.cookies = {k: v for k, v in data.items() if k.startswith('response.cookies.')}
        response_data.body_flatten = {k: v for k, v in data.items() if k.startswith('response.body.')}
        return response_data


@dataclass
class ExecutedOperation:
    operation_id: str
    method: str
    path: str 
    response: ResponseData
    request: RequestData

    def flatten(self) -> Dict[str, Any]:
        """
        Flatten the executed operation into a single dictionary.
        This is useful for easier access to nested values.
        """
        flat_dict = {}
        flatten_request = self.request.to_dict()
        flatten_request = resolve_values(flatten_request)
        flatten_response = self.response.to_dict()
        flat_dict.update(add_prefix_to_keys(flatten_request, self.operation_id + '.'))
        flat_dict.update(add_prefix_to_keys(flatten_response, self.operation_id + '.'))
        return flat_dict
    
    def flatten_with_refs(self) -> Dict[str, Any]:
        flat_dict = {}
        flatten_request = self.request.to_dict()
        flatten_response = self.response.to_dict()
        flat_dict.update(add_prefix_to_keys(flatten_request, self.operation_id + '.'))
        flat_dict.update(add_prefix_to_keys(flatten_response, self.operation_id + '.'))
        return flat_dict


@dataclass
class OperationFlow:
    operation_id: str
    selected_operations: List[str]
    usage_guide: str
    executed_operations: List[ExecutedOperation] = field(default_factory=list)
    result: OperationFlowResult = OperationFlowResult.FAILURE

    def _get_new_operation_id(self, operation_id: str) -> str:
        """
        Generate a new operation Id by appending a suffix if the operation Id already exists in the context.
        """
        for n, executed_operation in enumerate(self.executed_operations):
            if executed_operation.operation_id.startswith(operation_id):
                self.executed_operations[n].operation_id = operation_id + "_1"
                # If the operation Id already exists, append a suffix to create a new unique ID
                suffix = 2
                new_operation_id = f"{operation_id}_{suffix}"
                while any(op.operation_id == new_operation_id for op in self.executed_operations):
                    suffix += 1
                    new_operation_id = f"{operation_id}_{suffix}"
                return new_operation_id
        return operation_id

    def add_executed_operation(self, endpoint: Endpoint, request_data: RequestData, response_data: ResponseData) -> None:
        """
        Add an executed operation to the context.
        This is useful for tracking the operations that have been run and their parameters.
        If the operation Id already exists, update the new one to opertionId_1, opertionId_2, etc.
        This is to avoid duplicates in the operation history.
        """
        operation_id = self._get_new_operation_id(endpoint.operation_id)

        new_operation = ExecutedOperation(
            operation_id=operation_id,
            method=endpoint.method,
            path=endpoint.path,
            response=response_data,
            request=request_data
        )

        self.executed_operations.append(new_operation)

    def to_string(self) -> str:
        operation_values = self.previous_values_to_string()

        return f"""
        Executed operations:
        "operation_id": "{self.operation_id}",
        "selected_operations": {self.selected_operations},
        "usage_guide": "{self.usage_guide}",
        "executed_operations": {operation_values}
        """
    
    def values_with_refs_to_string(self) -> str:
        """
        Convert the request and response data to a string for easier readability.
        """
        params = []
        for op in self.executed_operations:
            for key, value in op.flatten_with_refs().items():
                if isinstance(value, OperationParameter) and value.source == ParameterSource.DEPENDENT:
                    value = value.value_with_placeholder
                if isinstance(value, OperationParameter) and value.source == ParameterSource.GENERATED:
                    value = value.value
                params.append(f"{key}: {value}")
        return "\n".join(params)
    
    def get_values_with_ref_objects(self) -> Dict[str, Any]:
        """
        Get the request and response data as a dictionary with references to the original source.
        """
        params = {}
        for op in self.executed_operations:
            for key, value in op.flatten_with_refs().items():
                params.update({key: value})
        return params
    
    def previous_values_to_dict(self) -> Dict[str, Any]:
        """
        Flatten the previous values into a single dictionary and resolve the values.
        """
        params = {}
        for op in self.executed_operations:
            for key, value in op.flatten().items():
                params[key] = value

        params = resolve_values(params)
        return params
    
    def previous_values_to_string(self) -> str:
        resolved_values = self.previous_values_to_dict()
        params = []
        for key, value in resolved_values.items():
            params.append(f"{key}: {value}")
        return "\n".join(params)


def flatten_body_data(data, prefix="") -> Dict[str, OperationParameter]:
    """
    Flattens a JSON response into a dictionary where each key represents a path to a value.
    Handles dicts, lists, and primitive values.
    """
    flat_dict = {}

    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            flat_dict.update(flatten_body_data(value, prefix=full_key))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            full_key = f"{prefix}[{i}]" if prefix else f"[{i}]"
            flat_dict.update(flatten_body_data(item, prefix=full_key))
    elif prefix:
        flat_dict[prefix] = data

    return flat_dict

def unflatten_body_data(flat_data: Dict[str, Any]) -> Union[Dict, list]:
    """
    Reconstructs nested data from a flattened dictionary.
    Keys like 'user.name.first' or 'items[0].product_id' will be expanded
    into nested dicts/lists.
    """
    # Determine if root should be a list or dict by checking if any key starts with [index]
    should_be_list = any(key.startswith('[') and re.match(r'^\[\d+\]', key) for key in flat_data.keys())
    root = [] if should_be_list else {}

    for compound_key, value in flat_data.items():
        current = root
        # Match parts of key: 'user.name', 'items[0].product_id' -> ['items', '[0]', 'product_id']
        parts = re.split(r'(\[\d+\])|\.', compound_key)
        parts = [p for p in parts if p not in (None, '')]

        for i, part in enumerate(parts):
            if re.fullmatch(r'\[\d+\]', part):  # It's a list index
                index = int(part[1:-1])
                if not isinstance(current, list):
                    raise TypeError(f"Expected list at {compound_key} but got {type(current).__name__}")

                # Expand list if needed
                while len(current) <= index:
                    current.append({})
                if i == len(parts) - 1:
                    current[index] = value
                else:
                    if not isinstance(current[index], (dict, list)):
                        # Check next part to decide if it should be a list
                        next_part = parts[i + 1] if i + 1 < len(parts) else None
                        current[index] = [] if next_part and re.fullmatch(r'\[\d+\]', next_part) else {}
                    current = current[index]
            else:  # It's a dict key
                if i == len(parts) - 1:
                    current[part] = value
                else:
                    if part not in current or not isinstance(current[part], (dict, list)):
                        # Check next part to decide if it should be a list
                        next_part = parts[i + 1] if i + 1 < len(parts) else None
                        current[part] = [] if next_part and re.fullmatch(r'\[\d+\]', next_part) else {}
                    current = current[part]

    return root

def test_flatten_unflatten():
    """
    Test the flatten_body_data and unflatten_body_data functions with various complex response objects.
    """
    print("Testing flatten_body_data and unflatten_body_data functions\n")
    print("=" * 80)
    
    # Test case 1: Simple object
    test1 = {
        "name": "John",
        "age": 30,
        "active": True
    }
    
    # Test case 2: Nested object
    test2 = {
        "user": {
            "profile": {
                "name": "Jane",
                "email": "jane@example.com",
                "preferences": {
                    "theme": "dark",
                    "notifications": True
                }
            },
            "metadata": {
                "created_at": "2023-01-01",
                "last_login": "2023-12-31"
            }
        }
    }
    
    # Test case 3: Array at root level (like genome-nexus API)
    test3 = [
        {
            "id": 0,
            "ensemblTranscriptIds": [
                "ENST00000111111.1",
                "ENST00000222222.2"
            ],
            "position": 50
        },
        {
            "id": 1,
            "ensemblTranscriptIds": [
                "ENST00000333333.3",
                "ENST00000444444.4"
            ],
            "position": 75
        }
    ]
    
    # Test case 4: Complex nested with mixed arrays and objects
    test4 = {
        "users": [
            {
                "name": "Alice",
                "roles": ["admin", "user"],
                "profile": {
                    "email": "alice@example.com",
                    "settings": {
                        "notifications": {
                            "email": True,
                            "sms": False
                        }
                    }
                }
            },
            {
                "name": "Bob",
                "roles": ["user"],
                "profile": {
                    "email": "bob@example.com",
                    "settings": {
                        "notifications": {
                            "email": False,
                            "sms": True
                        }
                    }
                }
            }
        ],
        "metadata": {
            "total": 2,
            "page": 1,
            "filters": ["active", "verified"]
        }
    }
    
    # Test case 5: API response with pagination and data array
    test5 = {
        "status": "success",
        "data": {
            "items": [
                {
                    "id": 123,
                    "attributes": {
                        "name": "Product A",
                        "categories": ["electronics", "gadgets"],
                        "specs": {
                            "dimensions": {
                                "width": 10,
                                "height": 20,
                                "depth": 5
                            },
                            "features": ["wifi", "bluetooth", "touchscreen"]
                        }
                    }
                },
                {
                    "id": 124,
                    "attributes": {
                        "name": "Product B",
                        "categories": ["books", "education"],
                        "specs": {
                            "dimensions": {
                                "width": 15,
                                "height": 22,
                                "depth": 2
                            },
                            "features": ["hardcover", "illustrated"]
                        }
                    }
                }
            ],
            "pagination": {
                "current_page": 1,
                "total_pages": 5,
                "per_page": 10,
                "total_items": 50
            }
        }
    }
    
    # Test case 6: Deeply nested array structure
    test6 = {
        "matrix": [
            [
                {"value": 1, "color": "red"},
                {"value": 2, "color": "blue"}
            ],
            [
                {"value": 3, "color": "green"},
                {"value": 4, "color": "yellow"}
            ]
        ],
        "operations": [
            {
                "type": "transform",
                "steps": [
                    {"action": "rotate", "degrees": 90},
                    {"action": "scale", "factor": 1.5}
                ]
            }
        ]
    }
    
    # Test case 7: Empty and null values
    test7 = {
        "empty_string": "",
        "null_value": None,
        "empty_array": [],
        "empty_object": {},
        "nested_with_empties": {
            "data": [],
            "metadata": None,
            "config": {}
        }
    }
    
    test_cases = [
        ("Simple object", test1),
        ("Nested object", test2),
        ("Array at root level", test3),
        ("Complex nested with mixed arrays/objects", test4),
        ("API response with pagination", test5),
        ("Deeply nested array structure", test6),
        ("Empty and null values", test7)
    ]
    
    passed = 0
    failed = 0
    
    for i, (description, test_data) in enumerate(test_cases, 1):
        print(f"Test {i}: {description}")
        print("-" * 60)
        
        try:
            # Step 1: Flatten the data
            flattened = flatten_body_data(test_data, "")
            print(f"Flattening successful ({len(flattened)} keys)")
            
            # Show some sample flattened keys
            sample_keys = list(flattened.keys())[:5]
            if sample_keys:
                print("   Sample flattened keys:")
                for key in sample_keys:
                    value = flattened[key]
                    print(f"     {key}: {repr(value)}")
                if len(flattened) > 5:
                    print(f"     ... and {len(flattened) - 5} more keys")
            
            # Step 2: Unflatten the data
            unflattened = unflatten_body_data(flattened)
            print(f"Unflattening successful")
            
            # Step 3: Compare original with unflattened
            import json
            original_json = json.dumps(test_data, sort_keys=True, default=str)
            unflattened_json = json.dumps(unflattened, sort_keys=True, default=str)
            
            if original_json == unflattened_json:
                print("Round-trip test PASSED - Original and unflattened data match")
                passed += 1
            else:
                print("Round-trip test FAILED - Data mismatch")
                print("Original:")
                print(json.dumps(test_data, indent=2, default=str)[:200] + "...")
                print("Unflattened:")
                print(json.dumps(unflattened, indent=2, default=str)[:200] + "...")
                failed += 1
                
        except Exception as e:
            print(f"Test FAILED with exception: {str(e)}")
            failed += 1
        
        print("")
    
    print("=" * 80)
    print(f"📊 Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("All tests passed! The flatten/unflatten functions work correctly.")
    else:
        print(f"{failed} test(s) failed. Check the implementation.")
    
    # Additional demonstration: Show how specific paths can be accessed
    print("\nDemonstration: Accessing specific values from flattened data")
    print("-" * 60)
    
    demo_data = test4  # Use the complex nested example
    flattened_demo = flatten_body_data(demo_data, "response.body")
    
    demo_paths = [
        "response.body.users[0].name",
        "response.body.users[1].profile.email", 
        "response.body.users[0].profile.settings.notifications.email",
        "response.body.metadata.total",
        "response.body.metadata.filters[1]"
    ]
    
    for path in demo_paths:
        if path in flattened_demo:
            value = flattened_demo[path]
            print(f"{path}: {repr(value)}")
        else:
            print(f"{path}: NOT FOUND")

def test_response_init():
    class CookieMock:
        def get_dict(self):
            return {}
        
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.headers = {}
            self.cookies = CookieMock()
            self.status_code = status_code
        
        def json(self):
            return self.json_data

    #response json with more then 10 objects in list
    response_json = [
        {"id": 1, "name": "Test 1"},
        {"id": 2, "name": "Test 2"},
        {"id": 3, "name": "Test 3"},
        {"id": 4, "name": "Test 4"},
        {"id": 5, "name": "Test 5"},
        {"id": 6, "name": "Test 6"},
        {"id": 7, "name": "Test 7"},
        {"id": 8, "name": "Test 8"},
        {"id": 9, "name": "Test 9"},
        {"id": 10, "name": "Test 10"},
        {"id": 11, "name": "Test 11"},
        {"id": 12, "name": "Test 12"},
        {"id": 13, "name": "Test 13"},
        {"id": 14, "name": "Test 14"},
        {"id": 15, "name": "Test 15"},
    ]

    mock_response = MockResponse(response_json, 200)

    response = ResponseData(mock_response)
    # Test the json method
    print(response.to_dict())

if __name__ == "__main__":
    #test_flatten_unflatten()
    test_response_init()

