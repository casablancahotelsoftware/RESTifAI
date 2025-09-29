
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from basecase_flow_generator import BaselineFlowGenerator
from test_case_generator import TestCaseGenerator
from spec_parser import OpenAPISpecParser
from operation_flow import OperationFlowResult
from postman_collection_builder import PostmanCollectionBuilder
from src.script_executor import ScriptExecutor
from llm_manager import LLMManager
from test_report_manager import TestReportManager
from config import Paths, MAX_WORKERS, PROJECT_ROOT

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import json

import argparse

def select_operations_for_endpoint(baseline_generator, endpoint):
    """Select operations for a single endpoint - runs in parallel"""
    try:
        operation_id = endpoint.operation_id
        
        selected_operations, usage_guide = baseline_generator.select_operations(operation_id)
        
        endpoint.dependent_operations = selected_operations
        endpoint.usage_guide = usage_guide
        
        return True
        
    except Exception as e:
        print(f"Error selecting operations for {endpoint.operation_id}: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate API test cases")
    parser.add_argument("-u", "--base-url", default="http://localhost:8000", help="Base URL for the API")
    parser.add_argument("-s", "--spec-path", default=Paths.get_specifications() / "petstore.json", help="Path to the OpenAPI specification file e.g. specifications/petstore.json")    
    parser.add_argument("-t", "--structural", type=int, choices=[0, 1], default=1, help="Generate structural negative tests (1=true, 0=false)")
    parser.add_argument("-f", "--functional", type=int, choices=[0, 1], default=1, help="Generate functional negative tests (1=true, 0=false)")
    parser.add_argument("-e", "--environment-initialization-script", default=None, help="Path to script for environment initialization. Gets executed before happy path generation and each test case execution")
    parser.add_argument("-i", "--user-input", default=None, help="Custom additional user input for generating the happy path values")

    args = parser.parse_args()
    
    base_url = args.base_url
    spec_path = args.spec_path
    generate_structural = args.structural
    generate_functional = args.functional
    environment_initialization_script_path = args.environment_initialization_script

    spec_name = Path(spec_path).stem

    user_input = args.user_input.strip() if args.user_input else None

    environment_initializer = None
    if environment_initialization_script_path:
        environment_initializer = ScriptExecutor(environment_initialization_script_path)
    
    if environment_initializer:
        environment_initializer.execute_script()

    generation_start_time = time.time()

    llm_manager = LLMManager()

    parser = OpenAPISpecParser(spec_path)
    endpoints = parser.get_endpoints()
    
    print(f"Using specification file: {spec_path}")
    print(f"Using base URL: {base_url}")
    print(f"Loaded {len(endpoints)} endpoints from specification")
    
    baseline_generator = BaselineFlowGenerator(base_url, endpoints, llm_manager, user_input)
    test_case_generator = TestCaseGenerator(base_url, endpoints, llm_manager, spec_name)

    failures = 0
    server_errors = 0
    successes = 0 

    tests = []
    
    total_endpoints = len(endpoints)
    
    print("Selecting dependent operations for all endpoints in parallel...")
    
    max_workers = min(MAX_WORKERS, total_endpoints)
    completed_selections = 0
    
    # Identify dependent operations for each endpoint in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_endpoint = {
            executor.submit(select_operations_for_endpoint, baseline_generator, endpoint): endpoint 
            for endpoint in endpoints
        }
        
        for future in as_completed(future_to_endpoint):
            endpoint = future_to_endpoint[future]
            completed_selections += 1
            
            try:
                success = future.result()
                if success:
                    print(f"Operations selected for {endpoint.operation_id}: {endpoint.dependent_operations}")
                else:
                    print(f"Failed to select operations for {endpoint.operation_id}")
            except Exception as e:
                print(f"Error selecting operations for {endpoint.operation_id}: {str(e)}")
    
    for i, endpoint in enumerate(endpoints):
        try:
            operation_id = endpoint.operation_id
            
            print(f"\n{'='*60}")
            print(f"Processing {operation_id}... ({i+1}/{total_endpoints})")
            
            if not hasattr(endpoint, 'dependent_operations') or not endpoint.dependent_operations:
                print(f"No selected operations available for {operation_id}. Skipping...")
                failures += 1
                continue
            
            print(f"Using pre-selected operations: {endpoint.dependent_operations}")
            
            if environment_initializer:
                reset_success = environment_initializer.execute_script()

            print("Generating valid operation flow...")
            valid_operation_flow = baseline_generator.generate_valid_operation_flow(
                operation_id, endpoint.dependent_operations, endpoint.usage_guide
            )
            
            if valid_operation_flow.result.value == OperationFlowResult.SERVER_ERROR.value:
                print(f"Server error for operation {operation_id}. Skipping...")
                server_errors += 1
                continue
                
            if valid_operation_flow.result.value == OperationFlowResult.FAILURE.value:
                print(f"Client error for operation {operation_id}. Skipping...")
                failures += 1
                continue
                
            successes += 1
            print("Valid operation flow generated successfully")
            print(f"Flow result: {valid_operation_flow.previous_values_to_string()}")
            print("----")
            
            if not args.structural and not args.functional:
                test_descriptions = []
            else:
                test_type_msg = []
                if args.structural:
                    test_type_msg.append("structural")
                if args.functional:
                    test_type_msg.append("functional")
                    
                print(f"Generating negative test case scenarios ({', '.join(test_type_msg)})...")
                
                test_descriptions = test_case_generator.generate_negative_test_case_descriptions(
                    valid_operation_flow,
                    use_structural=args.structural,
                    use_functional=args.functional
                )
                
                print(f"Generated {len(test_descriptions)} test case scenarios:")
                for test in test_descriptions:
                    print(f"  - {test.test_name}: {test.description}")
                    tests.append(f"{test}\n")

            if test_descriptions:
                print("Generating negative values for test case scenarios...")
            else:
                print("Generating valid test case...")
                
            test_suite_name = f"Test{operation_id.capitalize()}"
            
            test_case_generator.generate_test_suite(
                valid_operation_flow=valid_operation_flow,
                test_suite_name=test_suite_name,
                test_case_descriptions=test_descriptions, 
            )
            
            if test_descriptions:
                print(f"Test suite '{test_suite_name}' generated successfully!")
                tests_dir = Paths.get_tests()
            else:
                print(f"Valid test case '{test_suite_name}' generated successfully!")
                tests_dir = Paths.get_tests()
                
        except Exception as e:
            print(f"Error processing {endpoint.operation_id}: {str(e)}")
            failures += 1
        
    print(f"\n{'='*60}")
    print("Test generation completed!")
    
    generation_end_time = time.time()
    generation_duration_seconds = generation_end_time - generation_start_time

    print("\n" + "="*60)
    print("EXECUTING ALL TEST SUITES")
    print("="*60)
    
    tests_dir = Paths.get_tests()
    if tests_dir:
        PostmanCollectionBuilder.execute_all_test_suites(tests_folder=tests_dir, environment_initializer=environment_initializer)
    
    print("\nAll test suites executed successfully!")
    
    report_manager = TestReportManager()
    report_manager.print_statistics_summary()

    stats = report_manager.get_all_reports_statistics()

    results = {
        "successful_operations": stats.get("total_suites", 0),
        "server_errors": stats.get("total_server_errors", 0),
        "total_tokens": llm_manager.get_total_tokens(),
        "total_cost": float(format(llm_manager.get_total_cost(), '.2f')),
        "total_tests": stats.get("total_cases", 0),
        "failed_tests": stats.get("total_failed", 0),
        "time_duration": int(generation_duration_seconds),
    }

    print("\nFinal Results:")
    print(json.dumps(results, indent=4))

    with open(PROJECT_ROOT / "output/results.json", "w") as f:
        json.dump(results, f, indent=4)

    sys.exit(0)