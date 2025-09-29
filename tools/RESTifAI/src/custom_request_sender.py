import requests
from typing import Dict, Any, Optional
from urllib.parse import urlencode
from operation_flow import RequestData, ResponseData, ExecutedOperation
from spec_parser import Endpoint


class URLBuilder:
    """
    Utility class for building URLs from endpoint and request data.
    Used for both sending requests and error reporting.
    """
    
    @staticmethod
    def build_url(base_url: str, endpoint: Endpoint, request_data: RequestData) -> str:
        """
        Build the complete URL including path parameters and query string.
        
        :param base_url: Base URL of the API
        :param endpoint: Endpoint object containing method and path
        :param request_data: RequestData object containing parameters
        :return: Complete URL string
        """
        base_url = base_url.rstrip('/')
        path = endpoint.path
        path_params = request_data.resolve_path_params()
        query_params = request_data.resolve_query_params()

        # Replace path parameters
        if path_params:
            for k, v in path_params.items():
                placeholder = '{' + k + '}'
                path = path.replace(placeholder, str(v))

        # Build base URL with path
        url = f"{base_url}{path}"

        # Add query parameters
        if query_params:
            query_string = urlencode(query_params, doseq=True)
            url = f"{url}?{query_string}"

        return url

    @staticmethod
    def get_debug_info(base_url: str, endpoint: Endpoint, request_data: RequestData) -> Dict[str, Any]:
        """
        Get detailed debug information about the URL construction.
        
        :param base_url: Base URL of the API
        :param endpoint: Endpoint object containing method and path
        :param request_data: RequestData object containing parameters
        :return: Dictionary with debug information
        """
        path_params = request_data.resolve_path_params()
        query_params = request_data.resolve_query_params()
        
        return {
            "base_url": base_url.rstrip('/'),
            "original_path": endpoint.path,
            "path_params": path_params,
            "query_params": query_params,
            "final_url": URLBuilder.build_url(base_url, endpoint, request_data),
            "method": endpoint.method.upper()
        }


class CustomRequestSender:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')

    def send_request(
        self,
        endpoint: Endpoint,
        request_data: RequestData,
    ) -> ResponseData:
        """
        Send an HTTP request with arbitrary data, bypassing client validation.

        :param endpoint: Endpoint object containing method, path, and other details
        :param request_data: RequestData object containing path_params, query_params, headers, cookies, and body
        :return: ResponseData object
        """
        method = endpoint.method
        headers = request_data.resolve_headers()
        cookies = request_data.resolve_cookies()
        body = request_data.body

        # Build URL using the new URLBuilder
        url = URLBuilder.build_url(self.base_url, endpoint, request_data)

        if headers is None:
            headers = {}

        if cookies is None:
            cookies = {}

        if body is not None and isinstance(body, (dict, list)) and 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'

        #print(f"Sending {method} request to {url} with headers: {headers}, cookies: {cookies} and body: {body}")

        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            cookies=cookies,
            json=body if headers.get('Content-Type') == 'application/json' else None,
            data=body if headers.get('Content-Type') != 'application/json' else None,
        )

        return ResponseData(
            response
        )

if __name__ == "__main__":
    # test faltten_body_data
    sender = CustomRequestSender("http://localhost:5000")
    data = {
        "key1": "value1",
        "key2": {
            "subkey1": "subvalue1",
            "subkey2": [1, 2, 3],
            "subkey3": {
                "subsubkey1": "subsubvalue1"
            }
        },
        "key3": [4, 5, 6]
    }