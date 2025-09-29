from typing import List, Dict, Any, Tuple
from operation_flow import OperationFlow
from spec_parser import Endpoint
from custom_request_sender import CustomRequestSender
from llm_manager import LLMManager
from llm_output_parser import TestCaseDescription
from postman_collection_builder import PostmanCollectionBuilder
from src.script_executor import ScriptExecutor
from config import Paths
import json

class TestCaseGenerator:
    def __init__(self, base_url: str, endpoints: List[Endpoint], llm_manager: LLMManager, spec_name: str):
        self.base_url = base_url
        self.endpoints = endpoints
        self.sender = CustomRequestSender(base_url)
        self.llm_manager = llm_manager
        
        self.run_folder = Paths.create_run_folder(spec_name)
        self.tests_dir = Paths.get_tests()
        
    def _get_relevant_endpoints(self, selected_operations: List[str]) -> List[Endpoint]:
        relevant_endpoints = []
        for endpoint in self.endpoints:
            if endpoint.operation_id in selected_operations:
                relevant_endpoints.append(endpoint)
        return relevant_endpoints

    def generate_negative_test_case_descriptions(self, operation_flow: OperationFlow, use_structural: bool = True, use_functional: bool = True) -> List[TestCaseDescription]:
        """
        Generate negative test case descriptions for the given operation flow.
        
        Args:
            operation_flow: The operation flow to generate test cases for
            use_structural: Whether to generate structural negative test cases
            use_functional: Whether to generate functional negative test cases
            
        Returns:
            List of test case descriptions
        """
        relevant_endpoints = self._get_relevant_endpoints(operation_flow.selected_operations)
        negative_test_case_descriptions: List[TestCaseDescription] = []
        # Generate structural negative test cases if requested
        if use_structural:
            structural_test_cases = self.llm_manager.generate_structural_negative_test_case_descriptions(
                operation_flow, relevant_endpoints
            )
            for test_case in structural_test_cases:
                test_case.test_name = f"{test_case.test_name}_ST"
            negative_test_case_descriptions.extend(structural_test_cases)
            
        # Generate functional negative test cases if requested
        if use_functional:
            existing_test_cases = [tc.to_string() for tc in negative_test_case_descriptions]
            functional_test_cases = self.llm_manager.generate_functional_negative_test_case_descriptions(
                operation_flow, relevant_endpoints, existing_test_cases
            )
            for test_case in functional_test_cases:
                test_case.test_name = f"{test_case.test_name}_FU"
            negative_test_case_descriptions.extend(functional_test_cases)
            
        return negative_test_case_descriptions

    def generate_invalid_values_from_test_case_description(self, operation_flow: OperationFlow, test_case_description: TestCaseDescription) -> Dict[str, Any]:
        operation_value_flow = operation_flow.values_with_refs_to_string()
        operation_value_flow_dict = operation_flow.get_values_with_ref_objects()
        relevant_endpoints = self._get_relevant_endpoints(operation_flow.selected_operations)
        test_case_values = self.llm_manager.generate_invalid_values_from_test_case_description(test_case_description, operation_value_flow, relevant_endpoints, operation_value_flow_dict)
        
        assert f"{operation_flow.selected_operations[-1]}.response.status_code" in test_case_values, f"The generated test case values must include the expected response status code of the last operation. test_case_values: {test_case_values}"

        test_case_values[f"{operation_flow.selected_operations[-1]}.response.status_code"] = 400

        return test_case_values

    def generate_test_suite(self, valid_operation_flow: OperationFlow, test_suite_name: str, test_case_descriptions: List[TestCaseDescription] = []) -> None:
        """
        Generate a test suite with one valid test case and multiple negative test cases.
        
        Args:
            operation_flow: The valid operation flow to base tests on
            test_case_descriptions: List of test case descriptions to generate
            test_suite_name: Name of the test suite (will be used as folder name)
            environment_initializer: Environment initializer instance
            collection_folder: Base output folder
        """
        test_suite_folder = self.tests_dir / test_suite_name
        test_suite_folder.mkdir(exist_ok=True, parents=True)

        self.add_valid_test_case_to_suite(valid_operation_flow, test_suite_name)
        failures = self.add_negative_test_cases_to_suite(valid_operation_flow, test_case_descriptions, test_suite_name)
            
        print(f"\nTest suite '{test_suite_name}' generated successfully!")
        print(f"Location: {test_suite_folder}")
        print(f"Total collections: {len(test_case_descriptions) + 1 - len(failures)} (1 valid + {len(test_case_descriptions)} negative)")
    
    def add_valid_test_case_to_suite(self, valid_operation_flow: OperationFlow, test_suite_name: str) -> None:
        """
        Add a valid test case to a Postman collection.
        Args:
            valid_operation_flow: The valid operation flow to base the test case on
            test_suite_name: Name of the test suite (will be used as folder name)
        """
        valid_test_description = TestCaseDescription("This test case tests the endpoint for valid data and expects a successful response from the service", "validRequest")

        self.add_test_case_to_test_suite(
            valid_operation_flow,
            valid_operation_flow.get_values_with_ref_objects(),
            valid_test_description,
            test_suite_name=test_suite_name
        )

    def add_negative_test_cases_to_suite(self, valid_operation_flow: OperationFlow, test_case_descriptions: List[TestCaseDescription], test_suite_name: str) -> None:
        """
        Add multiple negative test cases to a Postman collection.
        
        Args:
            valid_operation_flow: The valid operation flow to base the test cases on
            test_case_descriptions: List of test case descriptions to add
            test_suite_name: Name of the test suite (will be used as folder name)
        """
        failures: List[TestCaseDescription] = []
        for test_case_description in test_case_descriptions:
            test_case_values = self.generate_invalid_values_from_test_case_description(valid_operation_flow, test_case_description)
            if test_case_values is None:
                print(f"⚠️  Failed to generate values for test case: {test_case_description.test_name}")
                self.save_failed_invalid_value_generation_for_test_case(test_case_description)
                failures.append(test_case_description)
                continue
            
            self.add_test_case_to_test_suite(
                valid_operation_flow,
                test_case_values,
                test_case_description,
                test_suite_name
            )

        return failures

    def add_test_case_to_test_suite(self, operation_flow: OperationFlow, test_case_values: Dict[str, Any], test_case_description: TestCaseDescription, test_suite_name: str) -> None:
        """
        Add a test case to a Postman collection and save test case data to test_data folder.
        
        Args:
            operation_flow: The valid operation flow to base the test case on
            test_case_values: Values for the test case
            test_case_description: Description of the test case to add
            test_suite_name: Name of the test suite (will be used as folder name)
        """
        # Create Postman collection
        postman_collection_builder = PostmanCollectionBuilder(
            base_url=self.base_url,
            test_case_description=test_case_description,
            output_dir=self.tests_dir,
        )
        
        postman_collection_builder.add_postman_test_case(
            operation_flow, 
            test_case_values
        )
        
        # Save the collection with the test case
        collection_name = f"{test_case_description.test_name}.postman_collection.json"
        postman_collection_builder.save_to_file(
            file_name=collection_name, 
            create_subdirectory=True, 
            subdirectory_name=test_suite_name
        )
          # Save test case data to test_data folder
        relevant_endpoints = self._get_relevant_endpoints(operation_flow.selected_operations)
        self._save_test_case_data(operation_flow, test_case_values, test_case_description, test_suite_name, relevant_endpoints)

    def execute_test_suite(self, test_suite_name: str, environment_initializer: ScriptExecutor) -> None:
        """
        Execute all test case collections in a test suite folder.
        
        Args:
            test_suite_name: Name of the test suite folder
            environment_initializer: Environment initializer instance
            collection_folder: Base output folder
        """
        test_suite_folder = self.tests_dir / test_suite_name
        
        if not test_suite_folder.exists():
            print(f"❌ Test suite folder not found: {test_suite_folder}")
            return
        
        print(f"\n🚀 Executing test suite: {test_suite_name}")
        print(f"📁 Folder: {test_suite_folder}")
        
        PostmanCollectionBuilder.execute_test_suite_collections(test_suite_folder, environment_initializer)
        
        print(f"✅ Test suite execution completed: {test_suite_name}")

    def save_failed_invalid_value_generation_for_test_case(self, test_case_description: TestCaseDescription) -> None:
        """
        Save the test case description to a JSON file if invalid values generation fails.
        
        Args:
            test_case_description: The test case description to save
        """
        output_file = Paths.get_failed_testcase_value_generations_file()

        if not output_file.exists():
            with open(output_file, 'w') as f:
                json.dump([], f)
        
        with open(output_file, 'r+') as f:
            data = json.load(f)
            data.append(test_case_description.to_dict())
            f.seek(0)
            json.dump(data, f, indent=4)
        
        print(f"⚠️  Saved failed test case description to {output_file}")

    def _save_test_case_data(self, operation_flow: OperationFlow, test_case_values: Dict[str, Any], test_case_description: TestCaseDescription, test_suite_name: str, relevant_endpoints: List[Endpoint]) -> None:
        """
        Save test case data to the combined_data folder structure in the current run.
        
        Args:
            operation_flow: The operation flow for this test case
            test_case_values: The test case values used
            test_case_description: The test case description
            test_suite_name: The name of the test suite
            relevant_endpoints: List of relevant endpoints for this test case
        """
        # Create combined_data directory structure for this run
        combined_data_dir = Paths.get_combined_data()
        test_suite_data_dir = combined_data_dir / test_suite_name
        test_suite_data_dir.mkdir(exist_ok=True, parents=True)
        
        # Prepare test case data
        test_case_data = {
            "test_name": test_case_description.test_name,
            "description": test_case_description.description,
            "test_suite": test_suite_name,
            "base_url": self.base_url,
            "operations": operation_flow.selected_operations,
            "values_to_create_a_successful_request": operation_flow.previous_values_to_string(),
            "relevant_endpoints": [endpoint.to_string() for endpoint in relevant_endpoints],
            "passed": True,
        }
        
        # Save to JSON file
        file_name = f"{test_case_description.test_name}.json"
        file_path = test_suite_data_dir / file_name
        
        with open(file_path, 'w') as f:
            json.dump(test_case_data, f, indent=2, default=str)

    @staticmethod
    def get_test_type_from_name(test_name: str) -> str:
        """
        Extract test type from test name based on extension.
        
        Args:
            test_name: The test name with type extension
            
        Returns:
            Test type: 'Structural', 'Functional', or 'Valid'
        """
        if test_name.endswith('_ST'):
            return 'Structural'
        elif test_name.endswith('_FU'):
            return 'Functional'
        elif test_name == 'validRequest':
            return 'Valid'
        else:
            return 'Unknown'
    
    @staticmethod
    def get_clean_test_name(test_name: str) -> str:
        """
        Remove test type extension from test name.
        
        Args:
            test_name: The test name with type extension
            
        Returns:
            Clean test name without extension
        """
        if test_name.endswith('_ST') or test_name.endswith('_FU'):
            return test_name[:-3]  # Remove last 3 characters (_ST or _FU)
        return test_name