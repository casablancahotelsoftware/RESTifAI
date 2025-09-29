from typing import List, Tuple

from spec_parser import Endpoint
from custom_request_sender import CustomRequestSender
from llm_manager import LLMManager
from operation_flow import OperationFlow, OperationFlowResult
from config import MAX_VALID_REQUEST_VALUE_GENERATION_RETRIES

class BaselineFlowGenerator:
    def __init__(self, base_url: str, endpoints: List[Endpoint], llm_manager: LLMManager, user_input: str = None):
        self.base_url = base_url
        self.endpoints = endpoints
        self.sender = CustomRequestSender(base_url)
        self.llm_manager = llm_manager
        self.user_input = user_input

    def select_operations(self, operation_id: str) -> List[str]:
        selected_operations, usage_guide = self.llm_manager.select_operations(endpoints=self.endpoints, operation_id=operation_id, user_input=self.user_input)
        return selected_operations, usage_guide

    def generate_valid_operation_flow(self, operation_id: str, selected_operations: List[str], usage_guide: str) -> OperationFlow:
        self._initialize_context(operation_id, selected_operations, usage_guide)

        opid_to_endpoint = {ep.operation_id: ep for ep in self.endpoints if ep.operation_id in selected_operations}

        for idx, opid in enumerate(selected_operations):
            endpoint = opid_to_endpoint.get(opid)
            if not endpoint:
                print(f"Warning: operation Id {opid} not found in spec endpoints.")
                continue

            is_successful = self._process_operation(endpoint)

            if not is_successful:
                print(f"Failed to process operation {opid}. Stopping execution.")
                return self.operation_flow

        self._print_final_context(selected_operations)
        return self.operation_flow

    def _initialize_context(self, operation_id: str, selected_operations: List[str], usage_guide: str):
        self.operation_flow = OperationFlow(
            operation_id=operation_id,
            selected_operations=selected_operations,
            usage_guide=usage_guide,
            executed_operations=[],
            result=OperationFlowResult.FAILURE
        )

    def _process_operation(self, endpoint: Endpoint):
        print(f"Running endpoint {endpoint.operation_id} {endpoint.method} {endpoint.path}")
        max_retries = MAX_VALID_REQUEST_VALUE_GENERATION_RETRIES
        attempt = 0
        status_code = 200
        while attempt < max_retries:
            attempt += 1
            
            if status_code >= 200 and status_code < 300:
                request_data, raw_llm_output = self.llm_manager.generate_valid_values_for_endpoint(endpoint=endpoint, operation_flow_history=self.operation_flow, user_input=self.user_input)  
            else:
                request_data, raw_llm_output = self.llm_manager.fix_values_for_endpoint(
                    endpoint=endpoint,
                    operation_flow_history=self.operation_flow,
                    response_data=response_data,
                    raw_llm_output=raw_llm_output,
                    status_code=status_code,
                    user_input=self.user_input
                )

            if request_data is None:
                print(f"Failed to generate valid values for {endpoint.operation_id}. Stopping execution.")
                return False
            
            if endpoint.method.upper() in ['POST', 'PUT', 'PATCH']:
                request_data.body = request_data.body or {}
            else:
                request_data.body = None

            response_data = self.sender.send_request(
                endpoint=endpoint,
                request_data=request_data
            )
            
            status_code = response_data.status_code

            if 500 <= status_code < 600:
                print(f"Server error {status_code} encountered. Stopping execution.")
                print("Context that produced the error:")
                print(str(request_data.to_dict()))
                
                self.operation_flow.add_executed_operation(
                    endpoint=endpoint,
                    request_data=request_data,
                    response_data=response_data
                )
                self.operation_flow.result = OperationFlowResult.SERVER_ERROR
                return False

            if 400 <= status_code < 500:
                print(f" Request failed with status {status_code}, regenerating input and retrying...")
                self.operation_flow.result = OperationFlowResult.FAILURE
                continue

            if 200 <= status_code < 300:
                self._remove_previous_4xx_failed_requests()
                print(f"Request successful with status {status_code}.")
                self.operation_flow.result = OperationFlowResult.SUCCESS
                break


        if attempt == max_retries and (status_code < 200 or status_code >= 300):
            print(f"Failed to get successful response for {endpoint.operation_id} after {max_retries} attempts.")
            self.operation_flow.result = OperationFlowResult.FAILURE
            return False

        print("----")

        self.operation_flow.add_executed_operation(
            endpoint=endpoint,
            request_data=request_data,
            response_data=response_data
        )

        return True

    def _remove_previous_4xx_failed_requests(self):
        self.operation_flow.executed_operations = [
            op for op in self.operation_flow.executed_operations
            if not (400 <= op.response.status_code < 500)
        ]

    def _print_final_context(self, selected_operations: List[str]):
        all_successful = all(
            200 <= op.response.status_code < 300
            for op in self.operation_flow.executed_operations
        ) and len(self.operation_flow.executed_operations) == len(selected_operations)

        if all_successful:
            print("All requests successful. Context stored in structured dataclasses.")
        else:
            print("Some requests failed. Context stored in structured dataclasses.")
