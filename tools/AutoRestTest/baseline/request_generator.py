import os
import random
import time
from dataclasses import dataclass
from typing import List, Dict
import argparse
import threading
import requests
import json
from config import DEV_SERVER_ADDRESS
from specification_parser import SpecificationParser, ItemProperties, ParameterProperties, OperationProperties
from randomizer import RandomizedSelector


@dataclass
class RequestData:
    endpoint_path: str
    http_method: str
    parameters: Dict[str, any]
    request_body: any
    content_type: str
    operation_id: str

@dataclass
class RequestResponse:
    request: RequestData
    response: requests.Response
    response_text: str

@dataclass
class StatusCode:
    status_code: int
    count: int
    requests_and_responses: List[RequestResponse]

class RequestsGenerator:
    def __init__(self, file_path: str, api_url: str, is_local: bool = True, time_duration=600):
        self.file_path = file_path
        self.api_url = api_url
        self.successful_query_data: List[RequestData] = [] # list that will store successfuly query_parameters
        self.status_codes: Dict[int: StatusCode] = {} # dictionary to track status code occurrences
        self.specification_parser: SpecificationParser = SpecificationParser(self.file_path)
        self.operations: Dict[str, OperationProperties] = self.specification_parser.parse_specification()
        self.is_local = is_local
        self.time_duration = time_duration
        self.requests_generated = 0
        self.start_time = None

    def get_simple_type(self, variable):
        """
        Returns a simplified type name as a string for common Python data types.
        """
        type_mapping = {
            int: "integer",
            float: "float",
            str: "string",
            list: "array",
            dict: "object",
            tuple: "tuple",
            set: "set",
            bool: "boolean",
            type(None): "null"
        }
        var_type = type(variable)
        return type_mapping.get(var_type, str(var_type))

    def determine_composite_items(self, item_properties: ItemProperties, curr_value) -> ItemProperties:
        if item_properties.type == "array" and len(curr_value) > 0:
            item_properties.items = ItemProperties(
                type=self.get_simple_type(curr_value[0])
            )
        elif item_properties.type == "object":
            item_properties.properties = {}
            for key, value in curr_value.items():
                item_properties.properties[key] = ItemProperties(
                    type=self.get_simple_type(value)
                )
        return item_properties

    def create_operation_for_mutation(self, query_value: RequestData, operation_properties: OperationProperties) -> OperationProperties:
        """
        Create a new operation for mutation
        """
        if query_value.request_body and operation_properties.request_body_properties:
            for content_type, request_body_properties in operation_properties.request_body_properties.items():
                request_body_properties = ItemProperties(
                    type=self.get_simple_type(query_value.request_body)
                )
                request_body_properties = self.determine_composite_items(request_body_properties, query_value.request_body)
                operation_properties.request_body_properties[content_type] = request_body_properties

        endpoint_path = operation_properties.endpoint_path
        for parameter_name, parameter_properties in operation_properties.parameters.items():
            if parameter_properties.in_value == "path":
                manual_randomizer = RandomizedSelector(operation_properties.parameters, query_value.request_body)
                operation_properties.endpoint_path = endpoint_path.replace(
                    "{" + parameter_name + "}", str(manual_randomizer.randomize_item(parameter_properties.schema)))

        operation_properties.parameters = {}
        if query_value.parameters:
            for parameter_name, parameter_value in query_value.parameters.items():
                parameter_properties = ParameterProperties(
                    name=parameter_name,
                    in_value="query",
                    schema=ItemProperties(
                        type=self.get_simple_type(parameter_value)
                    )
                )
                parameter_properties.schema = self.determine_composite_items(parameter_properties.schema, parameter_value)
                operation_properties.parameters[parameter_name] = parameter_properties

        return operation_properties

    def mutate_requests(self):
        """
        Mutate valid queries for further testing
        """
        print("Mutating Requests...")
        curr_success_queries = self.successful_query_data.copy()
        for query in curr_success_queries:
            print("Time Elapsed: ", time.time() - self.start_time)
            print("Time Remaining: ", self.time_duration - (time.time() - self.start_time))
            print("Requests Sent: ", self.requests_generated)
            print("========================================")
            curr_id = query.operation_id
            operation_details = self.operations.get(curr_id)
            if operation_details is not None:
                new_operation: OperationProperties = operation_details
                new_operation = self.create_operation_for_mutation(query, new_operation)
                self.process_operation(new_operation)
            if (time.time() - self.start_time) > self.time_duration:
                break

    def process_response(self, response: requests.Response, request_data: RequestData):
        """
        Process the response from the API.
        """
        if response is None:
            return

        self.requests_generated += 1

        # print(response.text)
        request_and_response = RequestResponse(
            request=request_data,
            response=response,
            response_text=response.text
        )

        if response.status_code not in self.status_codes:
            self.status_codes[response.status_code] = StatusCode(
                status_code=response.status_code,
                count=1,
                requests_and_responses=[request_and_response],
            )
        else:
            self.status_codes[response.status_code].count += 1
            self.status_codes[response.status_code].requests_and_responses.append(request_and_response)

        if response.status_code // 100 == 2:
            self.successful_query_data.append(request_data)

    def attempt_retry(self, response: requests.Response, request_data: RequestData):
        """
        Attempt retrying request with old query parameters
        """
        if response is None or response.status_code // 100 == 2:
            return

        retries = 1
        indices = list(range(len(self.successful_query_data)))
        random.shuffle(indices)
        for i in indices:
            if response is None or (200 <= response.status_code < 300) or retries > 5:
                break
            old_request = self.successful_query_data[i]
            if old_request.http_method in {"put", "post"}:
                new_params = old_request.request_body
                if new_params is not type(dict):
                    new_params = {"request_body": old_request.request_body}
                new_request = RequestData(
                    endpoint_path=request_data.endpoint_path,
                    http_method=request_data.http_method,
                    parameters=new_params, # use old request body as new query parameters to check for producer-consumer dependency
                    # NEED TO CHECK THAT REQUEST_BODY ISN'T JUST STRING
                    request_body=old_request.request_body,
                    content_type=old_request.content_type,
                    operation_id=request_data.operation_id
                )
                response = self.send_request(new_request)
                self.process_response(response, new_request)
                retries += 1
        return

    def send_request(self, request_data: RequestData) -> requests.Response:
        """
        Send the request to the API.
        """
        endpoint_path = request_data.endpoint_path
        http_method = request_data.http_method
        query_parameters = request_data.parameters
        request_body = request_data.request_body
        content_type = request_data.content_type
        try:
            select_method = getattr(requests, http_method)
            if http_method in {"put", "post"}:
                #if content_type == "json":
                response = select_method(f"{self.api_url}{endpoint_path}", params=query_parameters, json=json.dumps(request_body))
                #else:
                #    print("Request Body: ", request_body)
                #    response = select_method(self.api_url + endpoint_path, params=query_parameters, data=request_body)
                # FORM DATA ERRORING ATM
            else:
                response = select_method(f"{self.api_url}{endpoint_path}", params=query_parameters)
        except requests.exceptions.RequestException as err:
            #print("Request failed due to error: ", err)
            print("Request failed due to error: ", str(err)[:400])
            print("Endpoint Path: ", endpoint_path)
            print("Params: ", query_parameters)
            return None
        except Exception as err:
            print("Request failed due to error: ", str(err)[:400])
            print("Endpoint Path: ", endpoint_path)
            print("Params: ", query_parameters)
            return None
        return response

    def randomize_values(self, parameters: Dict[str, ParameterProperties], request_body) -> (Dict[str, any], any):
        # create randomize object here and return after Object.randomize_parameters() and Object.randomize_request_body() is called
        # do randomize parameter selection, then randomize the values for both parameters and request_body
        randomizer = RandomizedSelector(parameters, request_body)
        return randomizer.randomize_parameters() if parameters else None, randomizer.randomize_request_body() if request_body else None

    def process_operation(self, operation_properties: OperationProperties):
        """
        Process the operation properties to generate the request.
        """
        endpoint_path = operation_properties.endpoint_path
        http_method = operation_properties.http_method

        request_body = None
        content_type = None
        if operation_properties.request_body:
            for content_type_value, request_body_properties in operation_properties.request_body_properties.items():
                content_type = content_type_value.replace("application/", "")
                request_body = request_body_properties

        query_parameters, request_body = self.randomize_values(operation_properties.parameters, request_body)

        for parameter_name, parameter_properties in operation_properties.parameters.items():
            if parameter_properties.in_value == "path":
                manual_randomizer = RandomizedSelector(operation_properties.parameters, request_body)
                endpoint_path = endpoint_path.replace("{" + parameter_name + "}", str(manual_randomizer.randomize_item(parameter_properties.schema)))

        request_data = RequestData(
            endpoint_path=endpoint_path,
            http_method=http_method,
            parameters=query_parameters,
            request_body=request_body,
            content_type=content_type,
            operation_id=operation_properties.operation_id
        )
        #print("Request Sent")
        response = self.send_request(request_data)
        if response is not None:
            self.process_response(response, request_data)
            self.attempt_retry(response, request_data)

    def requests_generate(self):
        """
        Generate the randomized requests based on the specification file.
        """
        print("Generating Request...")
        print()
        if not self.is_local:
            num_workers = 5
            worker_queues = [[] for i in range(num_workers)] 
            for i, (operation_id, operation_properties) in enumerate(self.operations.items()):
                worker_queues[i % num_workers].append((operation_id, operation_properties))
            workers = []
            for i in range(num_workers):
                worker = threading.Thread(target=self.process_operation, args=(worker_queues[i],))
                workers.append(worker)
                worker.start()
            for worker in workers:
                worker.join()
        else:
            self.start_time = time.time()
            while (time.time() - self.start_time) < self.time_duration:
                for operation_id, operation_properties in self.operations.items():
                    print("Time Elapsed: ", time.time() - self.start_time)
                    print("Time Remaining: ", self.time_duration - (time.time() - self.start_time))
                    print("Requests Sent: ", self.requests_generated)
                    print("========================================")
                    for _ in range(1):
                        self.process_operation(operation_properties)
                    if (time.time() - self.start_time) > self.time_duration:
                        break
                self.mutate_requests()


        print("Generated Requests!")

def output_responses(request_generator: RequestsGenerator, service_name: str):
    """
    Output the responses to a file.
    """
    directory = "./testing_output/baseline-logs/"
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(f"./testing_output/baseline-logs/{service_name}.txt", "w") as file:
        file.write(f"BASELINE OUTPUT FOR {service_name}\n")
        for status_code, status_code_data in request_generator.status_codes.items():
            file.write("========================================\n")
            file.write(f"Status Code Category: {status_code}\n")
            file.write(f"Count: {status_code_data.count}\n")
            file.write("----------------------------------------\n")
            for request_response in status_code_data.requests_and_responses:
                file.write(f"Endpoint Path: {request_response.request.endpoint_path}\n")
                file.write(f"Request Parameters: {request_response.request.similar_parameters}\n")
                file.write(f"Request Body: {request_response.request.request_body}\n")
                file.write(f"Status Code: {request_response.response.status_code}\n")
                file.write(f"Response Text: {request_response.response_text}\n")
                file.write("\n")

def argument_parse() -> (str, str):
    service_urls = {
        'fdic': "http://0.0.0.0:9001",
        'genome-nexus': "http://0.0.0.0:9002",
        'language-tool': "http://0.0.0.0:9003",
        'ocvn': "http://0.0.0.0:9004",
        'ohsome': "http://0.0.0.0:9005",
        'omdb': "http://0.0.0.0:9006",
        'rest-countries': "http://0.0.0.0:9007",
        'spotify': "http://0.0.0.0:9008",
        'youtube': "http://0.0.0.0:9009"
    }
    parser = argparse.ArgumentParser(description='Generate requests based on API specification.')
    parser.add_argument('service', help='The service specification to use.')
    parser.add_argument('is_local', help='Whether the services are loaded locally or not.')
    parser.add_argument('time_duration', help='The time duration to run the tests for.')
    args = parser.parse_args()
    api_url = service_urls.get(args.service)
    is_local = args.is_local
    time_duration = float(args.time_duration)
    if api_url is None:
        print(f"Service '{args.service}' not recognized. Available services are: {list(service_urls.keys())}")
        exit(1)
    if is_local not in {"true", "false"}:
        print(f"Invalid value for 'is_local'. Must be either 'true' or 'false'.")
        exit(1)
    if is_local == "false":
        api_url = api_url.replace("0.0.0.0", DEV_SERVER_ADDRESS)  # use config.py for DEV_SERVER_ADDRESS var
        api_url = api_url.replace(":9", ":8") # use public server proxy ports
    return args.service, api_url, time_duration

#testing code
if __name__ == "__main__":
    service_name, api_url, time_duration = argument_parse()
    file_path = f"../specs/original/oas/{service_name}.yaml"
    print("Checking requests at: ", api_url)
    request_generator = RequestsGenerator(file_path=file_path, api_url=api_url, is_local=True, time_duration=time_duration)
    for i in range(1):
        request_generator.requests_generate()
    print([(x.status_code, x.count) for x in request_generator.status_codes.values()])
    output_responses(request_generator, service_name)
