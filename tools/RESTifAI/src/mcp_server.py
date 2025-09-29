#!/usr/bin/env python3
"""
FastMCP Server for RESTifAI - API Testing Framework
Provides tools for executing tests and retrieving test reports using FastMCP
"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import json
import logging
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from config import Paths
from test_report_manager import TestReportManager
from postman_collection_builder import PostmanCollectionBuilder
from src.script_executor import ScriptExecutor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("restifai-fastmcp-server")

# Initialize FastMCP server
mcp = FastMCP("RESTifAI API Testing Framework")

# Global instances - initialize lazily to avoid startup delays
test_report_manager = None
environment_initializer = None

def get_test_report_manager():
    """Get or initialize TestReportManager instance"""
    global test_report_manager
    if test_report_manager is None:
        try:
            test_report_manager = TestReportManager()
        except Exception as e:
            logger.error(f"Failed to initialize TestReportManager: {e}")
            raise
    return test_report_manager

def initialize_environment_initializer():
    """Initialize environment initializer with default configuration"""
    global environment_initializer
    if environment_initializer is None:
        script_path = Paths.get_env_init_script()
        
        if not script_path:
            logger.warning("ENVIRONMENT_INIT_SCRIPT environment variable not set")
            return
            
        try:
            environment_initializer = ScriptExecutor(script_path)
        except Exception as e:
            logger.warning(f"Failed to initialize environment initializer: {e}")

@mcp.tool(
    name="execute_all_tests",
    description="Execute all Postman test collections and generate reports. Now supports individual test case collections with environment initialization.",
)
async def execute_all_tests(initialize_environment: bool = True) -> str:
    """Execute all test suites containing individual test case collections"""
    try:
        environment_initializer_instance = None
        if initialize_environment:
            # Get script path from environment
            script_path = Paths.get_env_init_script()
            
            if not script_path:
                return json.dumps({
                    "status": "error",
                    "message": "ENVIRONMENT_INIT_SCRIPT environment variable not set"
                })
            
            environment_initializer_instance = ScriptExecutor(script_path)
        
        # Get the output folder path as a Path object
        output_folder = Paths.get_output()
        
        if not output_folder.exists():
            return json.dumps({
                "status": "error", 
                "message": f"Output folder not found: {output_folder}"
            })
        
        # Execute all test suites using the new structure
        PostmanCollectionBuilder.execute_all_test_suites(output_folder, environment_initializer_instance)
        
        return json.dumps({
            "status": "success",
            "message": "All test suites executed successfully with individual test case collections",
            "environment_initialization": initialize_environment
        })
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Failed to execute tests: {str(e)}"
        })

@mcp.tool(
    name="execute_test_suite", 
    description="Execute a specific test suite containing individual test case collections",
)
async def execute_test_suite(test_suite_name: str, initialize_environment: bool = True) -> str:
    """Execute a specific test suite folder containing individual test case collections"""
    try:
        environment_initializer_instance = None
        if initialize_environment:
            # Get script path from environment
            script_path = Paths.get_env_init_script()
            
            if not script_path:
                return json.dumps({
                    "status": "error",
                    "message": "ENVIRONMENT_INIT_SCRIPT environment variable not set"
                })
            
            environment_initializer_instance = ScriptExecutor(script_path)
        
        # Get the output folder path as a Path object
        output_folder = Path(os.getenv("GENERATED_TEST_DATA_FOLDER")) if os.getenv("GENERATED_TEST_DATA_FOLDER") else Paths.get_output()
        test_suite_folder = output_folder / test_suite_name
        
        if not test_suite_folder.exists():
            return json.dumps({
                "status": "error",
                "message": f"Test suite folder not found: {test_suite_folder}"
            })
        
        # Execute the specific test suite
        PostmanCollectionBuilder.execute_test_suite_collections(test_suite_folder, environment_initializer_instance)
        
        return json.dumps({
            "status": "success", 
            "message": f"Test suite '{test_suite_name}' executed successfully",
            "environment_initialization": initialize_environment
        })
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Failed to execute test suite '{test_suite_name}': {str(e)}"
        })

@mcp.tool(
    name="get_all_test_suites",
    description="Get a list of all available test suites with their summary statistics",
)
async def get_all_test_suites() -> str:
    """
    Get a list of all available test suites with their summary statistics
    
    Returns:
        JSON string with all test suites and their statistics
    """
    try:
        test_names = get_test_report_manager().get_test_names()
        
        if not test_names:
            return json.dumps({
                "status": "info",
                "message": "No test suites found. Run 'execute_all_tests' first to generate reports.",
                "total_suites": 0,
                "test_suites": []
            })
        
        suites_summary = []
        
        for test_name in test_names:
            report = get_test_report_manager().get_test_report(test_name)
            if report:
                stats = report.statistics
                suite_info = {
                    "test_suite_name": test_name,
                    "total_test_cases": stats.total_test_cases,
                    "passed_test_cases": stats.passed_test_cases,
                    "failed_test_cases": stats.failed_test_cases,
                    "server_error_cases": stats.test_cases_with_server_errors,
                    "success_rate": round(stats.success_rate, 2),
                    "total_requests": stats.total_requests,
                    "avg_requests_per_case": round(stats.avg_requests_per_case, 2),
                    "timestamp": report.timestamp,
                    "overall_success": report.success
                }
                suites_summary.append(suite_info)
        
        response = {
            "status": "success",
            "total_suites": len(test_names),
            "test_suites": suites_summary
        }
        
        return json.dumps(response, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting test suites: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Error retrieving test suites: {str(e)}"
        })

@mcp.tool(
    name="get_test_report",
    description="Get detailed test report for a specific test suite",
)
async def get_test_report(test_suite_name: str) -> str:
    """
    Get detailed test report for a specific test suite
    
    Args:
        test_suite_name: Name of the test suite to retrieve report for
        
    Returns:
        JSON string with detailed test report
    """
    if not test_suite_name:
        return json.dumps({
            "status": "error",
            "message": "test_suite_name is required"
        })
    
    try:
        report = get_test_report_manager().get_test_report(test_suite_name)
        
        if not report:
            available_suites = get_test_report_manager().get_test_names()
            return json.dumps({
                "status": "error",
                "message": f"Test suite '{test_suite_name}' not found",
                "available_suites": available_suites
            })
        
        # Convert dataclass to dict for JSON serialization
        from report_data_models import dataclass_to_dict
        report_dict = dataclass_to_dict(report)
        
        # Add status for clarity
        report_dict["status"] = "success"
        
        return json.dumps(report_dict, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting test report: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Error retrieving test report for '{test_suite_name}': {str(e)}"
        })

@mcp.tool(
    name="get_all_failure_reports",
    description="Get all failure reports consolidated into one response",
)
async def get_all_failure_reports() -> str:
    """
    Get all failure reports consolidated into one response
    
    Returns:
        JSON string with all failed test cases across all test suites
    """
    try:
        # Use the get_all_failed_reports method from TestReportManager
        failed_reports = get_test_report_manager().get_all_failed_reports()
        
        if not failed_reports:
            return json.dumps({
                "status": "info",
                "message": "No failure reports found.",
                "total_test_suites_with_failures": 0,
                "total_failed_test_cases": 0,
                "failed_test_suites": []
            })
        
        # Convert dataclass instances to dictionaries for JSON serialization
        from report_data_models import dataclass_to_dict
        failed_reports_dicts = [dataclass_to_dict(report) for report in failed_reports]
        
        # Calculate summary statistics
        total_failed_test_cases = sum(report.failed_test_cases_count for report in failed_reports)
        total_test_suites_with_failures = len(failed_reports)
        
        # Create consolidated failure summary
        failure_summary = []
        for report in failed_reports:
            summary = {
                "test_suite_name": report.test_suite_name,
                "failed_count": report.failed_test_cases_count,
                "total_count": report.total_test_cases,
                "failure_rate": round((report.failed_test_cases_count / report.total_test_cases * 100), 2) if report.total_test_cases > 0 else 0,
                "timestamp": report.timestamp
            }
            failure_summary.append(summary)
        
        # Consolidate all failures into a single report
        consolidated_report = {
            "status": "success",
            "message": "Consolidated failure report",
            "summary": {
                "total_test_suites_with_failures": total_test_suites_with_failures,
                "total_failed_test_cases": total_failed_test_cases,
                "failure_overview": failure_summary
            },
            "detailed_failures": failed_reports_dicts
        }
        
        return json.dumps(consolidated_report, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting failure reports: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Error retrieving failure reports: {str(e)}"
        })

@mcp.tool()
async def get_test_suite_summary() -> str:
    """
    Get a quick summary of all test suites with key metrics
    
    Returns:
        JSON string with high-level summary statistics
    """
    try:
        test_names = get_test_report_manager().get_test_names()
        
        if not test_names:
            return json.dumps({
                "status": "info",
                "message": "No test suites found",
                "summary": {
                    "total_suites": 0,
                    "overall_success_rate": 0,
                    "total_test_cases": 0,
                    "total_passed": 0,
                    "total_failed": 0,
                    "total_server_errors": 0
                }
            })
        
        # Aggregate statistics across all suites
        total_test_cases = 0
        total_passed = 0
        total_failed = 0
        total_server_errors = 0
        suite_statuses = []
        
        for test_name in test_names:
            report = get_test_report_manager().get_test_report(test_name)
            if report:
                stats = report.statistics
                total_test_cases += stats.total_test_cases
                total_passed += stats.passed_test_cases
                total_failed += stats.failed_test_cases
                total_server_errors += stats.test_cases_with_server_errors
                
                suite_statuses.append({
                    "name": test_name,
                    "success": report.success,
                    "success_rate": round(stats.success_rate, 2)
                })
        
        overall_success_rate = (total_passed / total_test_cases * 100) if total_test_cases > 0 else 0
        
        summary = {
            "status": "success",
            "summary": {
                "total_suites": len(test_names),
                "overall_success_rate": round(overall_success_rate, 2),
                "total_test_cases": total_test_cases,
                "total_passed": total_passed,
                "total_failed": total_failed,
                "total_server_errors": total_server_errors,
                "suites_overview": suite_statuses
            }
        }
        
        return json.dumps(summary, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting test suite summary: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Error retrieving summary: {str(e)}"
        })

if __name__ == "__main__":
    # Run the FastMCP server
    mcp.run(transport="sse")