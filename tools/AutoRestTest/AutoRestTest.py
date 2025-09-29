import argparse
import json
import os
import shelve

from src.generate_graph import OperationGraph
from src.marl import QLearning
from src.request_generator import RequestGenerator

from dotenv import load_dotenv

from src.graph.specification_parser import SpecificationParser
from src.utils import OpenAILanguageModel, construct_db_dir, is_json_seriable, EmbeddingModel, get_api_url, INPUT_COST_PER_TOKEN

from configurations import USE_CACHED_GRAPH, USE_CACHED_TABLE, \
    LEARNING_RATE, DISCOUNT_FACTOR, MAX_EXPLORATION, MUTATION_RATE, SPECIFICATION_LOCATION, \
    ENABLE_HEADER_AGENT, OPENAI_LLM_ENGINE

load_dotenv()

time_duration = None

def parse_args():
    parser = argparse.ArgumentParser(description='Generate requests based on API specification.')
    parser.add_argument("num_specs", choices=["one", "many"],
                        help="Specifies the number of specifications: 'one' or 'many'")
    parser.add_argument("local_test", type=lambda x: (str(x).lower() == 'true'),
                        help="Specifies whether the test is local (true/false)")
    parser.add_argument("-s", "--spec_name", type=str, default=None, help="Optional name of the specification")
    return parser.parse_args()

def output_q_table(q_learning: QLearning, spec_name):
    parameter_table = q_learning.parameter_agent.q_table
    body_obj_table = q_learning.body_object_agent.q_table
    value_table = q_learning.value_agent.q_table
    operation_table = q_learning.operation_agent.q_table
    data_source_table = q_learning.data_source_agent.q_table
    dependency_table = q_learning.dependency_agent.q_table
    header_table = q_learning.header_agent.q_table if q_learning.header_agent.q_table else "Disabled"

    simplified_param_table = {}
    for operation, operation_values in parameter_table.items():
        simplified_param_table[operation] = {"params": {}, "body": {}}
        for parameter, parameter_values in operation_values["params"].items():
            simplified_param_table[operation]["params"][str(parameter)] = parameter_values
        for body, body_values in operation_values["body"].items():
            simplified_param_table[operation]["body"][str(body)] = body_values

    simplified_body_table = {}
    for operation, operation_values in body_obj_table.items():
        simplified_body_table[operation] = {}
        for mime_type, mime_values in operation_values.items():
            if mime_type not in simplified_body_table[operation]:
                simplified_body_table[operation][mime_type] = {}
            for body, body_values in mime_values.items():
                simplified_body_table[operation][mime_type][str(body)] = body_values

    compiled_q_table = {
        "OPERATION AGENT": operation_table,
        "HEADER AGENT": header_table,
        "PARAMETER AGENT": simplified_param_table,
        "VALUE AGENT": value_table,
        "BODY OBJECT AGENT": simplified_body_table,
        "DATA SOURCE AGENT": data_source_table,
        "DEPENDENCY AGENT": dependency_table
    }
    output_dir = os.path.join(os.path.dirname(__file__), f"data/{spec_name}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(f"{output_dir}/q_tables.json", "w") as f:
        json.dump(compiled_q_table, f, indent=2)

def output_successes(q_learning: QLearning, spec_name: str):
    output_dir = os.path.join(os.path.dirname(__file__), f"data/{spec_name}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(f"{output_dir}/successful_parameters.json", "w") as f:
        json.dump(q_learning.successful_parameters, f, indent=2)

    with open(f"{output_dir}/successful_bodies.json", "w") as f:
        json.dump(q_learning.successful_bodies, f, indent=2)

    with open(f"{output_dir}/successful_responses.json", "w") as f:
        json.dump(q_learning.successful_responses, f, indent=2)

    with open(f"{output_dir}/successful_primitives.json", "w") as f:
        json.dump(q_learning.successful_primitives, f, indent=2)

def output_errors(q_learning: QLearning, spec_name: str):
    output_dir = os.path.join(os.path.dirname(__file__), f"data/{spec_name}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    seriable_errors = {}
    for operation_idx, unique_errors in q_learning.unique_errors.items():
        seriable_errors[operation_idx] = [error for error in unique_errors if is_json_seriable(error)]

    with open(f"{output_dir}/server_errors.json", "w") as f:
        json.dump(seriable_errors, f, indent=2)

def output_operation_status_codes(q_learning: QLearning, spec_name: str):
    output_dir = os.path.join(os.path.dirname(__file__), f"data/{spec_name}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(f"{output_dir}/operation_status_codes.json", "w") as f:
        json.dump(q_learning.operation_response_counter, f, indent=2)

def output_report(q_learning: QLearning, spec_name: str, spec_parser: SpecificationParser):
    output_dir = os.path.join(os.path.dirname(__file__), f"data/{spec_name}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    title = spec_parser.get_api_title() if spec_parser.get_api_title() else spec_name
    title = f"'{title}' ({spec_name})"

    unique_processed_200s = set()
    for operation_idx, status_codes in q_learning.operation_response_counter.items():
        for status_code in status_codes:
            if status_code // 100 == 2:
                unique_processed_200s.add(operation_idx)

    unique_errors = 0
    for operation_idx in q_learning.unique_errors:
        unique_errors += len(q_learning.unique_errors[operation_idx])

    total_requests = sum(q_learning.responses.values())

    report_content = {
        "Title": "AutoRestTest Report for " + title,
        "Duration": f"{q_learning.time_duration} seconds",
        "Total Requests Sent": total_requests,
        "Status Code Distribution": dict(q_learning.responses),
        "Number of Total Operations": len(q_learning.operation_agent.q_table),
        "Number of Successfully Processed Operations": len(unique_processed_200s),
        "Percentage of Successfully Processed Operations": str(round(len(unique_processed_200s) / len(q_learning.operation_agent.q_table) * 100, 2)) + "%",
        "Number of Unique Server Errors": unique_errors,
        "Operations with Server Errors": q_learning.errors,
    }

    with open(f"{output_dir}/report.json", "w") as f:
        json.dump(report_content, f, indent=2)

    results = {
        "successful_operations": len(unique_processed_200s),
        "server_errors": unique_errors,
        "total_tokens": OpenAILanguageModel.get_cumulative_tokens(),
        "total_cost": round(OpenAILanguageModel.get_cumulative_cost(), 2),
        "total_tests": None,
        "failed_tests": None,
        "time_duration": int(q_learning.time_duration),
    }

    print("JSON_RESULTS_START")
    print(json.dumps(results, indent=4))
    print("JSON_RESULTS_END")

    with open(f"data/results.json", "w") as f:
        json.dump(results, f, indent=4)

def parse_specification_location(spec_loc: str):
    directory, file_name = os.path.split(spec_loc)
    file_name, ext = os.path.splitext(file_name)
    return directory, file_name, ext

class AutoRestTest:
    def __init__(self, spec_dir: str):
        self.spec_dir = spec_dir
        self.local_test = True
        self.is_naive = False
        construct_db_dir()
        self.use_cached_graph = USE_CACHED_GRAPH
        self.use_cached_table = USE_CACHED_TABLE

    def init_graph(self, spec_name: str, spec_path: str, embedding_model: EmbeddingModel) -> OperationGraph:
        spec_parser = SpecificationParser(spec_path=spec_path, spec_name=spec_name)
        api_url = get_api_url(spec_parser, self.local_test)
        operation_graph = OperationGraph(spec_path=spec_path, spec_name=spec_name, spec_parser=spec_parser, embedding_model=embedding_model)
        request_generator = RequestGenerator(operation_graph=operation_graph, api_url=api_url, is_naive=self.is_naive)
        operation_graph.assign_request_generator(request_generator)
        return operation_graph

    def generate_graph(self, spec_name: str, ext: str, embedding_model: EmbeddingModel):
        spec_path = f"{self.spec_dir}/{spec_name}{ext}"
        db_graph = os.path.join(os.path.dirname(__file__), f"src/cache/graphs/{spec_name}")
        print("CREATING SEMANTIC OPERATION DEPENDECY GRAPH...")
        with shelve.open(db_graph) as db:

            loaded_from_shelf = False
            if spec_name in db and self.use_cached_graph:
                print(f"Loading graph for {spec_name} from shelve.")
                operation_graph = self.init_graph(spec_name, spec_path, embedding_model)

                try:
                    graph_properties = db[spec_name]
                    operation_graph.operation_edges = graph_properties["edges"]
                    operation_graph.operation_nodes = graph_properties["nodes"]
                    print(f"Loaded graph for {spec_name} from shelve.")
                    loaded_from_shelf = True

                except Exception as e:
                    print("Error loading graph from shelve.")
                    loaded_from_shelf = False

            if not loaded_from_shelf:
                print(f"Initializing new graph for {spec_name}.")
                operation_graph = self.init_graph(spec_name, spec_path, embedding_model)
                operation_graph.create_graph()

                graph_properties = {
                    "edges": operation_graph.operation_edges,
                    "nodes": operation_graph.operation_nodes
                }

                try:
                    db[spec_name] = graph_properties
                except Exception as e:
                    print("Error saving graph to shelve.")

                print(f"Initialized new graph for {spec_name}.")
        print("GRAPH CREATED!!!")
        return operation_graph

    def perform_q_learning(self, operation_graph: OperationGraph, spec_name: str, time_duration: int):
        print("INITIATING Q-TABLES...")
        q_learning = QLearning(operation_graph, alpha=LEARNING_RATE, gamma=DISCOUNT_FACTOR, epsilon=MAX_EXPLORATION,
                               time_duration=time_duration, mutation_rate=MUTATION_RATE)
        db_q_table = os.path.join(os.path.dirname(__file__), f"src/cache/q_tables/{spec_name}")
    
        q_learning.operation_agent.initialize_q_table()
        print("Initialized operation agent Q-table.")
        q_learning.parameter_agent.initialize_q_table()
        print("Initialized parameter agent Q-table.")
        q_learning.body_object_agent.initialize_q_table()
        print("Initialized body object agent Q-table.")
        q_learning.dependency_agent.initialize_q_table()
        print("Initialized dependency agent Q-table.")
        q_learning.data_source_agent.initialize_q_table()
        print("Initialized data source agent Q-table.")

        output_q_table(q_learning, spec_name)

        with shelve.open(db_q_table) as db:
            loaded_value_from_shelf = False
            loaded_header_from_shelf = False

            if spec_name in db and self.use_cached_table:
                print(f"Loading Q-tables for {spec_name} from shelve.")

                compiled_q_table = db[spec_name]

                try:
                    q_learning.value_agent.q_table = compiled_q_table["value"]
                    print(f"Initialized value agent's Q-table for {spec_name} from shelve.")
                    loaded_value_from_shelf = True
                except Exception as e:
                    print("Error loading value agent from shelve.")
                    loaded_value_from_shelf = False

                if ENABLE_HEADER_AGENT:
                    try:
                        q_learning.header_agent.q_table = compiled_q_table["header"]
                        print(f"Initialized header agent's Q-table for {spec_name} from shelve.")
                        loaded_header_from_shelf = True if q_learning.header_agent.q_table else False
                        # If the header agent is disabled, the Q-table will be None.
                    except Exception as e:
                        print("Error loading header agent from shelve.")
                        loaded_header_from_shelf = False


            if not loaded_value_from_shelf:
                q_learning.value_agent.initialize_q_table()
                print(f"Initialized new value agent Q-table for {spec_name}.")

            if ENABLE_HEADER_AGENT and not loaded_header_from_shelf:
                q_learning.header_agent.initialize_q_table()
                print(f"Initialized new header agent Q-table for {spec_name}.")
            elif not ENABLE_HEADER_AGENT:
                q_learning.header_agent.q_table = None

            try:
                db[spec_name] = {
                    "value": q_learning.value_agent.q_table,
                    "header": q_learning.header_agent.q_table
                }
            except Exception as e:
                print("Error saving Q-tables to shelve.")

        output_q_table(q_learning, spec_name)
        print("Q-TABLES INITIALIZED...")

        print("BEGINNING Q-LEARNING...")
        q_learning.run()
        print("Q-LEARNING COMPLETED!!!")
        return q_learning

    def print_performance(self):
        print("Total tokens of the tool: ", round(OpenAILanguageModel.get_cumulative_tokens(), 2))
        if OPENAI_LLM_ENGINE in INPUT_COST_PER_TOKEN:
            print("Total cost of the tool: $", round(OpenAILanguageModel.get_cumulative_cost(), 2))
        else:
            print("Price tracking is not available for the selected OpenAI engine.")

    def run_all(self):
        for spec in os.listdir(self.spec_dir):
            spec_name = spec.split(".")[0]
            print(f"Running tests for {spec_name}")
            self.run_single(spec_name)

    def run_single(self, spec_name: str, ext: str, time_duration: int = None):
        print("BEGINNING AUTO-REST-TEST...")
        embedding_model = EmbeddingModel()
        operation_graph = self.generate_graph(spec_name, ext, embedding_model)
        q_learning = self.perform_q_learning(operation_graph, spec_name, time_duration=time_duration)
        self.print_performance()
        output_q_table(q_learning, spec_name)
        output_successes(q_learning, spec_name)
        output_errors(q_learning, spec_name)
        output_operation_status_codes(q_learning, spec_name)
        output_report(q_learning, spec_name, operation_graph.spec_parser)
        print("AUTO-REST-TEST COMPLETED!!!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoRestTest")
    parser.add_argument("-s", dest="specification", type=str, help="Path to the specification file")
    parser.add_argument("-t", "--time", dest="time_duration", type=int, help="Duration for Q-learning in seconds")
    args = parser.parse_args()

    AVAILABLE_SPECIFICATIONS = ["language-tool", "genome-nexus", "fdic", "ohsome", "rest-countries"]

    if args.specification not in AVAILABLE_SPECIFICATIONS:
        print(f"Specification '{args.specification}' is not available.")
        exit(1)

    spec_name = args.specification
    spec_path = "specs/" + args.specification + ".json"
    
    # Use command line argument if provided, otherwise use default values
    if args.time_duration:
        time_duration = args.time_duration
    else:
        if spec_name == "fdic":
            time_duration = 521
        elif spec_name == "ohsome":
            time_duration = 10456
        elif spec_name == "genome-nexus":
            time_duration = 1069
        elif spec_name == "language-tool":
            time_duration = 74
        elif spec_name == "rest-countries":
            time_duration = 349

    specification_directory, specification_name, ext = parse_specification_location(spec_path)

    auto_rest_test = AutoRestTest(spec_dir=specification_directory)
    auto_rest_test.run_single(specification_name, ext, time_duration=time_duration)