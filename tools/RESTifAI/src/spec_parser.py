import json
import jsonref
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class Endpoint:
    path: str
    method: str
    operation_id: Optional[str]
    summary: Optional[str]
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    responses: Dict[str, Any] = field(default_factory=dict)
    dependent_operations: Optional[List[str]] = None
    usage_guide: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Endpoint dataclass instance to a dictionary for JSON serialization.
        """
        return {
            "path": self.path,
            "method": self.method,
            "operation_id": self.operation_id,
            "summary": self.summary,
            "parameters": self.parameters,
            "request_body": self.request_body,
            "responses": self.responses,
            "dependent_operations": self.dependent_operations,
            "usage_guide": self.usage_guide,
        }

    def to_string(self) -> str:
        """
        Convert the Endpoint dataclass instance to a markdown string representation for prompts.
        """
        params_lines = []
        for param in self.parameters:
            for key, value in param.items():
                params_lines.append(f"  - {key}: {value}")
        params_str = "\n".join(params_lines) if params_lines else "None"
        request_body_str = str(self.request_body) if self.request_body else "None"
        responses_str = str(self.responses) if self.responses else "None"
        return (
            f"#### {self.operation_id}\n"
            f"- Method: {self.method}\n"
            f"- Path: {self.path}\n"
            f"- Parameters:\n{params_str}\n"
            f"- Request Body Schema:\n{request_body_str}\n"
            f"- Responses:\n{responses_str}\n"
        )

class OpenAPISpecParser:
    def __init__(self, spec_path):
        self.spec_path = spec_path
        try:
            self.spec = self.load_spec_from_file(spec_path)
        except (FileNotFoundError, ValueError) as e:
            raise ValueError(f"Failed to load OpenAPI specification from {spec_path}: {e}")
        self.paths = self.spec.get("paths", {})

    def get_endpoints(self) -> List[Endpoint]:
        """
        Extract all endpoints with their HTTP methods, parameters, request_body schemas, and responses.
        Returns a list of Endpoint dataclass instances.
        """
        endpoints = []
        for path, methods in self.paths.items():
            extracted_path_params = self._extract_parameters(methods)

            for method, details in methods.items():
                if method.lower() not in ["get", "post", "put", "delete", "patch", "options", "head"]:
                    continue
                # Extract method-level parameters
                method_params = self._extract_parameters(details)
                # Combine path-level and method-level parameters, avoiding duplicates by name and 'in'
                combined_params = extracted_path_params.copy()
                existing_keys = {(p["name"], p["in"]) for p in combined_params}
                for p in method_params:
                    key = (p.get("name"), p.get("in"))
                    if key not in existing_keys:
                        combined_params.append(p)
                        existing_keys.add(key)

                endpoint = Endpoint(
                    path=path,
                    method=method.upper(),
                    operation_id=details.get("operationId"),
                    summary=details.get("summary"),
                    parameters=combined_params,
                    request_body=self._extract_request_body(details),
                    responses=details.get("responses", {}),
                )
                endpoints.append(endpoint)
        return endpoints

    def _extract_parameters(self, details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract parameters for the endpoint, including path, query, header parameters.
        Also extracts if the parameter is required and all schema restrictions like maxLength, minimum, maximum, pattern, enum, etc.
        """
        params = details.get("parameters", [])
        extracted_params = []
        for param in params:
            param_info = {
                "name": param.get("name"),
                "in": param.get("in"),
                "required": param.get("required", False),
                "description": param.get("description"),
            }
            schema = param.get("schema", {})
            # Extract all schema properties (restrictions and info)
            if isinstance(schema, dict):
                for key, value in schema.items():
                    param_info[key] = value
            extracted_params.append(param_info)
        return extracted_params

    def _extract_request_body(self, details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract the request body schema if present.
        """
        request_body = details.get("requestBody")
        if not request_body:
            return None
        content = request_body.get("content", {})
        if not content:
            return None
        return content

    @staticmethod
    def filter_2xx_responses(endpoints: List[Endpoint]) -> List[Endpoint]:
        """
        Filter the endpoints_info list to include only responses with status codes starting with '2' (e.g., 200, 201).
        This reduces prompt size by excluding non-2xx responses.
        """
        filtered_endpoints = []
        for ep in endpoints:
            if isinstance(ep.responses, dict):
                filtered_responses = {status: resp for status, resp in ep.responses.items() if str(status).startswith("2")}
                ep_copy = Endpoint(
                    path=ep.path,
                    method=ep.method,
                    operation_id=ep.operation_id,
                    summary=ep.summary,
                    parameters=ep.parameters,
                    request_body=ep.request_body,
                    responses=filtered_responses,
                )
                filtered_endpoints.append(ep_copy)
            else:
                filtered_endpoints.append(ep)
        return filtered_endpoints

    @staticmethod
    def endpoints_to_string(endpoints: List[Endpoint]) -> str:
        """
        Convert a list of Endpoint instances to a markdown string representation for prompts.
        """
        return "\n".join([ep.to_string() for ep in endpoints])

    @staticmethod
    def load_spec_from_file(filepath) -> Dict[str, Any]:
        if isinstance(filepath, str):
            filepath = Path(filepath)
        
        if not filepath:
            raise ValueError("File path must be provided to load OpenAPI specification.")
        
        if not filepath.exists():
            raise FileNotFoundError(f"OpenAPI specification file not found: {filepath}")
        
        suffix = filepath.suffix.lower()
        if suffix in [".yaml", ".yml"]:
            import yaml
            with open(filepath, "r", encoding="utf-8") as f:
                spec = yaml.safe_load(f)
        elif suffix == ".json":
            with open(filepath, "r", encoding="utf-8") as f:
                spec = json.load(f)
        else:
            raise ValueError(f"Unsupported file format: {suffix}. File must be JSON or YAML.")
        
        #resolve refs to other files and refs in the spec
        absolute_filepath = filepath.resolve()
        base_uri = absolute_filepath.parent.as_uri() + "/"
        resolved_spec = jsonref.replace_refs(spec, base_uri=base_uri)

        return resolved_spec


def demo():
    from config import Paths
    spec_path = Paths.get_specifications() / "fdic.json"
    parser = OpenAPISpecParser(spec_path)
    endpoints = parser.get_endpoints()
    endpoints = OpenAPISpecParser.filter_2xx_responses(endpoints)
    print(parser.endpoints_to_string(endpoints))
    print(f"Total endpoints: {len(endpoints)}")
    print(f"len of the spec: {len(parser.endpoints_to_string(endpoints))} characters")

if __name__ == "__main__":
    demo()
