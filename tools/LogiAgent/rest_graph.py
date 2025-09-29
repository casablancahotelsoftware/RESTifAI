import copy
import json
import os
import random

import pydot

from graphviz import Digraph


class APINode:
    def __init__(self, dot_node, api_method, api_name, openapi_doc: str, node_id):
        self.dot_node = dot_node
        self.api_method = api_method
        self.api_name = api_name
        self.openapi_doc = openapi_doc
        self.node_id = node_id

        self.source_node_ids = []
        self.dest_node_ids = []

    def __hash__(self):
        return hash((self.api_method, self.api_name))

    def __eq__(self, other):
        if not isinstance(other, APINode):
            return False
        return (self.api_method, self.api_name) == (other.api_method, other.api_name)

    def get_api_signature(self):
        return f"{self.api_method} {self.api_name}"

    def add_source_node_id(self, source_node_id):
        self.source_node_ids.append(source_node_id)

    def add_dest_node_id(self, dest_node_id):
        self.dest_node_ids.append(dest_node_id)

    def get_in_cnt(self):
        return len(self.source_node_ids)

    def get_out_cnt(self):
        return len(self.dest_node_ids)

    def get_simple_info(self):
        swagger_info = json.loads(self.openapi_doc)
        summary = swagger_info.get("summary", "")
        operation_id = swagger_info.get("operationId", "")

        return summary, operation_id

    def get_llm_info(self):
        summary, operation_id = self.get_simple_info()
        llm_string = f"{self.api_method} {self.api_name}"
        if operation_id:
            llm_string += f" OperationId:{operation_id}"
        if summary:
            llm_string += f" Summary:{summary}"
        return llm_string

    def __repr__(self):
        return f"{self.api_method} {self.api_name}"

class RESTGraph:
    def __init__(self, dot_graph: pydot.Graph, swagger_path, base_url, edges_json_path: str = None):

        self.base_url = base_url

        self.api_nodes = {}  # type: dict[str:APINode]
        if edges_json_path is not None and len(edges_json_path) > 0 and os.path.isfile(edges_json_path):
            with open(edges_json_path) as f:
                edge_results = json.load(f)
                edge_results = edge_results["edge_results"]
            self.api_edges = edge_results
        else:
            self.api_edges = []

        # 'ApiResponse': {'type': 'object', 'propert... }
        self.model_map = {}  # type: dict[str:dict]
        # 'POST /store/order': {'tags':['store'], 'summary': 'Place an order for a pet', 'operationId': 'placeOrder'..}
        self.api_swagger_map = {}  # type: dict[str:dict]

        self._init_rest_graph(swagger_path)
        self._init_swagger_info(swagger_path)

        # For graph traversal, used to prioritize unvisited API nodes
        self.visited_cnt_map = {}  # type: dict[APINode, int]

        # Initialize visit count in visited_cnt_map
        for node in self.api_nodes.values():
            if node not in self.visited_cnt_map:
                self.visited_cnt_map[node] = 0

    def _init_rest_graph(self, swagger_path):
        with open(swagger_path, 'r') as f:
            swagger = json.loads(f.read())

        paths = swagger["paths"]  # type: dict
        for path_name, methods in paths.items():
            for method_name, method_api_doc in methods.items():
                api_node = APINode(None, method_name.upper(), path_name, json.dumps(method_api_doc), None)
                self.api_nodes[api_node.get_api_signature()] = api_node

        if len(self.api_edges) > 0:
            for edge in self.api_edges:
                assert len(edge) == 2
                source_node_signature = edge[0]
                dest_node_signature = edge[1]
                source_node = self.api_nodes[source_node_signature]  # type: APINode
                dest_node = self.api_nodes[dest_node_signature]  # type: APINode
                source_node.add_dest_node_id(dest_node.get_api_signature())
                dest_node.add_dest_node_id(source_node.get_api_signature())

    def _init_swagger_info(self, swagger_file_path):
        # _init_rest_graph invoked
        assert len(self.api_nodes) > 0

        # Models load
        with open(swagger_file_path, 'r') as f:
            swagger = json.loads(f.read())
        swagger = self.remove_xml_keys(swagger)
        components = swagger.get("components", {})
        if components:
            models = components.get("schemas", {})
        else:
            models = {}

        # load and expand models
        if type(models) == dict and len(models) > 0:
            for model_name, model_val in models.items():
                self.model_map[model_name] = model_val
            self.model_map = self.expand_references(self.model_map)

        for node in self.api_nodes.values():
            swagger_dict = json.loads(node.openapi_doc)
            swagger_dict = self.remove_xml_keys(swagger_dict)
            swagger_expanded = self.expand_refs_in_paths(swagger_dict)
            self.api_swagger_map[node.get_api_signature()] = swagger_expanded

    # swagger utils
    def remove_xml_keys(self, data):
        """
        Recursively remove 'xml' and 'application/xml' keys from JSON data structure.
        """
        if isinstance(data, dict):
            data.pop("xml", None)
            data.pop("application/xml", None)
            for key, value in list(data.items()):
                data[key] = self.remove_xml_keys(value)
        elif isinstance(data, list):
            data = [self.remove_xml_keys(item) for item in data]
        return data

    # swagger utils
    def expand_references(self, model_map):
        """
        Expand $ref references in Swagger model map to their actual data structures.
        """
        expanded_map = copy.deepcopy(model_map)

        def expand_properties(properties):
            for key, value in properties.items():
                if isinstance(value, dict) and "$ref" in value:
                    ref = value["$ref"]
                    ref_name = ref.split("/")[-1]
                    properties[key] = self.expand_references(expanded_map[ref_name])
                elif isinstance(value, dict):
                    expand_properties(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            expand_properties(item)

        for model_name, model_content in expanded_map.items():
            if type(model_content) is dict and 'properties' in model_content:
                expand_properties(model_content['properties'])

        return expanded_map

    # swagger utils
    def expand_refs_in_paths(self, swagger_content):
        """
        Replace $ref references in Swagger paths with their corresponding model content.
        """
        if isinstance(swagger_content, dict):
            if "$ref" in swagger_content:
                ref_path = swagger_content["$ref"]
                ref_name = ref_path.split("/")[-1]
                return copy.deepcopy(self.model_map.get(ref_name, {}))
            else:
                return {key: self.expand_refs_in_paths(value) for key, value in
                        swagger_content.items()}
        elif isinstance(swagger_content, list):
            return [self.expand_refs_in_paths(item) for item in swagger_content]
        else:
            return swagger_content

    def get_init_nodes(self):
        """
        Get initial API nodes.
        """
        available_nodes = []  # type: list[APINode]

        for api_node in self.api_nodes.values():
            if api_node.get_out_cnt() == 0:
                available_nodes.append(api_node)
            elif api_node.api_method.lower() == 'post':
                available_nodes.append(api_node)

        return available_nodes

    def get_next_available_node(self, current_api_node: APINode):
        available_ids = current_api_node.dest_node_ids + current_api_node.source_node_ids
        available_nodes = [self.api_nodes[aid] for aid in available_ids]
        return available_nodes

    def get_base_url(self):
        return self.base_url

    def graph_walk(self, node_cnt: int = 10) -> list[APINode]:
        if len(self.api_edges) == 0:
            raise Exception("Empty edge is true when init graph. In this case, we can not walk the graph.")

        max_api_cnt = node_cnt
        assert max_api_cnt <= len(self.api_nodes)
        visited_nodes = set()
        result_nodes = []

        # Randomly select initial node
        current_node = random.choice(list(self.api_nodes.values()))  # type: APINode
        result_nodes.append(current_node)
        visited_nodes.add(current_node)

        retry_cnt = 0
        while len(result_nodes) < max_api_cnt and retry_cnt < 10:
            retry_cnt += 1
            # Get next available nodes from current node
            next_nodes = self.get_next_available_node(current_node)
            next_nodes = list(next_nodes)  # Convert to list for sorting

            # Sort next_nodes by visit count in visited_cnt_map, randomize when counts are equal
            next_nodes.sort(key=lambda n: (self.visited_cnt_map[n], random.random()))
            found_next = False

            for next_node in next_nodes:
                if next_node not in visited_nodes:  # If node hasn't been visited
                    current_node = next_node  # Set as current node
                    result_nodes.append(current_node)  # Add to result list
                    visited_nodes.add(current_node)  # Mark as visited
                    found_next = True
                    break

            if not found_next:  # If no unvisited node found
                # Choose a random unvisited node
                unvisited_nodes = [node for node in self.api_nodes.values() if node not in visited_nodes]
                if not unvisited_nodes:  # If all nodes have been visited, restart random selection
                    raise Exception("Code should not run into here if max_api_cnt <= len(rest_graph.api_nodes)")
                else:
                    print(f"re-random choice")
                    current_node = random.choice(unvisited_nodes)

        # Update visit count in visited_cnt_map, initialize to 0 if not exists
        for node in result_nodes:
            if node not in self.visited_cnt_map:
                self.visited_cnt_map[node] = 0
            self.visited_cnt_map[node] += 1

        return result_nodes

    def graph_walk_llm_wrapper(self, node_cnt: int = 10) -> str:
        """
        Generate a string representation of API nodes for LLM processing, either randomly shuffled or via graph walk.
        """
        if node_cnt >= len(self.api_nodes) or len(self.api_nodes) <= node_cnt:
            result_nodes = list(self.api_nodes.values())    # type:list[APINode]
            random.shuffle(result_nodes)
        else:
            try:
                result_nodes = self.graph_walk(node_cnt)    # type:list[APINode]
            except Exception as e:
                print(f"`!!Note from the RESTifAI Team!!` This is a added exeption catch used for the evaluation of the ohsome service, because generating the graph for 134 operations would take ages (135*134 LLM invocations) and it is not necessary becasue every endpoint has no dependencies in the ohsome service. Therefore we just randomly select a single node for the good of LogiAgent.")
                result_nodes = [random.choice(list(self.api_nodes.values()))]
        return '\n'.join([node.get_llm_info() for node in result_nodes])

    def generate_svg_graph(self, svg_path: str = "output_graph.svg"):
        """
        Generate and save a directed graph visualization in SVG format using the API nodes and edges.
        """
        dot = Digraph(comment='API Graph')

        for node_key in self.api_nodes:
            dot.node(node_key, node_key)

        for edge in self.api_edges:
            from_key, to_key = edge
            dot.edge(from_key, to_key)

        dot.render(svg_path, format='svg')
        print(f"SVG graph has been generated and saved to {svg_path}")
