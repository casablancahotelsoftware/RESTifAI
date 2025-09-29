import os
import json
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from config import Paths
from report_data_models import (
    TestCase, TestRequest, RequestData, UrlInfo, RequestBody, Header, UrlVariable, QueryParameter,
    Assertion, ReportAssertionError, TestStatistics, TestReport, FailedTestReport,
    dataclass_to_dict
)

class TestReportManager:
    def __init__(self):
        self.reports: Dict[str, TestReport] = {}
        self.reports_folder = Paths.get_reports()
        if self.reports_folder:
            self._load_reports()

    def _load_reports(self):
        """Load reports from the current reports folder"""
        if not self.reports_folder or not self.reports_folder.exists():
            return

        for filepath in self.reports_folder.glob("*.json"):
            if filepath.name.endswith("_raw.json"):
                continue
                
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                test_name = data.get("test_name", filepath.stem)
                self.reports[test_name] = TestReport.from_newman_report(data)
            except Exception as e:
                print(f"Failed to load report {filepath.name}: {e}")

    def get_test_names(self) -> List[str]:
        """Get test names by scanning the reports folder for fresh data"""
        if not self.reports_folder or not self.reports_folder.exists():
            return []
        
        test_names = []
        for filepath in self.reports_folder.glob("*.json"):
            if filepath.name.endswith("_raw.json"):
                continue
            test_name = filepath.stem
            test_names.append(test_name)
        
        return test_names

    def get_test_report(self, test_name: str) -> Optional[TestReport]:
        """Get test report by reading fresh data from disk"""
        if not self.reports_folder:
            return None
            
        filepath = self.reports_folder / f"{test_name}.json"
        
        if not filepath.exists():
            return None
            
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            report = TestReport.from_newman_report(data)
            # Update cache with fresh data
            self.reports[test_name] = report
            return report
        except Exception as e:
            print(f"Failed to load report {test_name}: {e}")
            return None

    def get_test_report_dict(self, test_name: str) -> Optional[dict]:
        """Get test report as dictionary for backward compatibility"""
        report = self.reports.get(test_name)
        return dataclass_to_dict(report) if report else None

    def save_report(self, test_name: str, test_results: List[TestCase]):
        if not self.reports_folder:
            print("Cannot save report: No reports folder selected")
            return
            
        if not self.reports_folder.exists():
            self.reports_folder.mkdir(exist_ok=True, parents=True)
        
        # Check if a report already exists and merge test results
        existing_test_results = []
        filepath = self.reports_folder / f"{test_name}.json"
        
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                existing_test_results = existing_data.get("test_results", [])
                
                # Convert existing results back to TestCase objects if they're dicts
                if existing_test_results and isinstance(existing_test_results[0], dict):
                    existing_test_results = [TestReport._convert_to_test_case(tc) for tc in existing_test_results]
            except Exception as e:
                print(f"Warning: Could not load existing report {filepath}: {e}")
                existing_test_results = []
        
        # Merge new test results with existing ones
        # Remove any existing test cases with the same name to avoid duplicates
        new_test_case_names = {tc.test_case_name for tc in test_results}
        merged_test_results = [tc for tc in existing_test_results if tc.test_case_name not in new_test_case_names]
        merged_test_results.extend(test_results)
        
        # Calculate simplified statistics
        stats = self.calculate_report_statistics(merged_test_results)
        
        report = TestReport(
            test_name=test_name,
            test_results=merged_test_results,
            success=all(result.success for result in merged_test_results) if merged_test_results else True,
            timestamp=datetime.now().isoformat(),
            statistics=stats
        )
        
        # Convert to dict for JSON serialization
        report_dict = dataclass_to_dict(report)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=4)
        self.reports[test_name] = report
          # Update test case data in test_data folder (only for new test results)
        self._update_test_case_data(test_name, test_results)

    def _update_test_case_data(self, test_name: str, test_results: List[TestCase]):
        """
        Update test case data files in combined_data folder with test execution results.
        
        Args:
            test_name: Name of the test (test suite name)
            test_results: List of test case results from the report
        """
        combined_data_dir = Paths.get_combined_data()
        if not combined_data_dir:
            print("No combined data directory available")
            return
            
        test_suite_data_dir = combined_data_dir / test_name
        
        if not os.path.exists(test_suite_data_dir):
            print(f"Test data directory not found: {test_suite_data_dir}")
            return
        
        for test_case in test_results:
            test_case_file = os.path.join(test_suite_data_dir, f"{test_case.test_case_name}.json")
            
            if not os.path.exists(test_case_file):
                print(f"Test case data file not found: {test_case_file}")
                print(f"Also checked: {test_case.test_case_name}_ST.json and {test_case.test_case_name}_FU.json")
                continue
            
            try:
                # Load existing test case data
                with open(test_case_file, 'r') as f:
                    test_case_data = json.load(f)
                  # Update passed status
                test_case_data["passed"] = test_case.success
                
                # Add complete test results (always, not just for failed tests)
                test_results_data = []
                for request in test_case.requests:
                    # Format request body as JSON if possible
                    formatted_request_body = self._format_json_body(request.data.body.raw) if request.data.body else None
                    
                    # Format response body as JSON if possible
                    formatted_response_body = self._format_json_body(request.response_body)
                    
                    request_data = {
                        "request_name": request.name,
                        "request_id": request.id,
                        "success": request.success,
                        "is_server_error": request.is_server_error,
                        "request_data": {
                            "method": request.data.method,
                            "url": {
                                "path": request.data.url.path,
                                "host": request.data.url.host,
                                "query": [{"key": q.key, "value": q.value} for q in request.data.url.query],
                                "variable": [{"key": v.key, "value": v.value, "type": v.type} for v in request.data.url.variable]
                            },
                            "headers": [{"key": h.key, "value": h.value} for h in request.data.header],
                            "body": formatted_request_body
                        },
                        "response_data": {
                            "headers": request.response_headers,
                            "body": formatted_response_body
                        },
                        "assertions": [
                            {
                                "assertion": assertion.assertion,
                                "error": {
                                    "name": assertion.error.name,
                                    "index": assertion.error.index,
                                    "test": assertion.error.test,
                                    "message": assertion.error.message,
                                    "stack": assertion.error.stack
                                } if assertion.error else None
                            } for assertion in request.assertions
                        ]
                    }
                    test_results_data.append(request_data)
                
                test_case_data["test_results"] = test_results_data
                
                # Save updated test case data
                with open(test_case_file, 'w') as f:
                    json.dump(test_case_data, f, indent=2, default=str)
            except Exception as e:
                print(f"Error updating test case data {test_case_file}: {e}")

    def _format_json_body(self, body_data: Union[str, Dict, Any]) -> Union[Dict, str, None]:
        """
        Format body data as JSON for better readability.
        
        Args:
            body_data: The body data to format (string, dict, or other)
            
        Returns:
            Formatted JSON object if possible, original data otherwise
        """
        if body_data is None:
            return None
            
        # If it's already a dict, return as-is
        if isinstance(body_data, dict):
            return body_data
            
        # If it's a string, try to parse as JSON
        if isinstance(body_data, str):
            try:
                # Try to parse as JSON
                parsed = json.loads(body_data)
                return parsed
            except (json.JSONDecodeError, ValueError):
                # If not valid JSON, return as string
                return body_data
                
        # For other types, convert to string
        return str(body_data)

    def calculate_report_statistics(self, test_results: List[TestCase]) -> TestStatistics:
        """Calculate simplified test statistics"""
        total_test_cases = len(test_results)
        passed_test_cases = 0
        failed_test_cases = 0
        test_cases_with_server_errors = 0
        total_requests = 0
        
        for test_case in test_results:
            # Count test case outcomes
            if test_case.success:
                passed_test_cases += 1
            else:
                failed_test_cases += 1
            
            if test_case.has_server_error:
                test_cases_with_server_errors += 1
            
            # Count total requests
            total_requests += len(test_case.requests)
        
        # Calculate rates
        success_rate = (passed_test_cases / total_test_cases * 100) if total_test_cases > 0 else 0.0
        avg_requests_per_case = total_requests / total_test_cases if total_test_cases > 0 else 0.0
        
        return TestStatistics(
            total_test_cases=total_test_cases,
            passed_test_cases=passed_test_cases,
            failed_test_cases=failed_test_cases,
            test_cases_with_server_errors=test_cases_with_server_errors,
            total_requests=total_requests,
            success_rate=success_rate,
            avg_requests_per_case=avg_requests_per_case
        )

    def process_collection_results(self, test_name: str, report_data: dict) -> List[TestCase]:
        """Process Newman output and save results to a test report"""
        test_results = []

        collection_items = report_data.get("collection", {}).get("item", [])
        
        # Always use flat structure processing (new individual test case format)
        test_results = self._process_flat_collection_structure(collection_items, report_data, test_name)

        self.save_report(test_name, test_results)
        return test_results

    def _process_flat_collection_structure(self, collection_items: list, report_data: dict, test_name: str) -> List[TestCase]:
        """Process collections with flat structure (new individual test case format)"""
        test_results = []
        
        # Extract test case name from collection name
        # Collection names are like "TestCreateContingent_validRequest"
        # We want the test case name to be "validRequest" or similar
        collection_info = report_data.get("collection", {}).get("info", {})
        test_case_name = collection_info.get("name", test_name)
        
        test_success = True
        case_has_server_error = False
        requests = []
        
        for item in collection_items:
            if item.get("name") == "Set base URL":
                continue  # Skip the base URL setup item
            
            test_request = self._process_request(item, report_data)
            
            if not test_request.success:
                test_success = False
            if test_request.is_server_error:
                case_has_server_error = True
                test_success = False
            
            requests.append(test_request)
        
        # Create a single test case containing all requests from this individual collection
        test_case = TestCase(
            test_case_name=test_case_name,
            success=test_success,
            requests=requests,
            has_server_error=case_has_server_error
        )
        test_results.append(test_case)
        
        return test_results

    def _process_request(self, request_item: dict, report_data: dict) -> TestRequest:
        """Process a single request item and return TestRequest object"""
        request_name = request_item.get("name")
        request_id = request_item.get("id")
        request_values = request_item.get("request", {})
        
        # Convert dict data to dataclass structures
        url_data = request_values.get("url", {})
        url_info = UrlInfo(
            path=url_data.get("path", []),
            host=url_data.get("host", []),
            query=[QueryParameter(key=q.get("key", ""), value=q.get("value", "")) 
                   for q in url_data.get("query", [])],
            variable=[UrlVariable(type=v.get("type", ""), value=v.get("value", ""), key=v.get("key", "")) 
                     for v in url_data.get("variable", [])]
        )
        
        headers = [Header(key=h.get("key", ""), value=h.get("value", "")) 
                  for h in request_values.get("header", [])]
        
        body_data = request_values.get("body", {})
        body = RequestBody(
            mode=body_data.get("mode", ""),
            raw=body_data.get("raw", ""),
            options=body_data.get("options", {})
        )
        
        request_data_obj = RequestData(
            url=url_info,
            header=headers,
            method=request_values.get("method", ""),
            body=body
        )
        
        test_request = TestRequest(
            name=request_name,
            id=request_id,
            data=request_data_obj,
            success=False,
            assertions=[],
            is_server_error=False,
            response_headers={},
            response_body=None
        )
    
        # Find corresponding execution data
        for run in report_data.get("run", {}).get("executions", []):
            run_id = run.get("item", {}).get("id")
            if request_id == run_id:
                run_success = True
                
                # Check for request errors (like ECONNRESET)
                request_failure = run.get("requestError")
                if request_failure:
                    run_success = False
                    # Create an assertion error for the connection issue
                    connection_error = ReportAssertionError(
                        name="ConnectionError",
                        index=0,
                        test="Connection Test",
                        message=f"Request failed: {request_failure.get('message', 'Unknown connection error')} (Code: {request_failure.get('code', 'Unknown')})",
                        stack=request_failure.get('stack', '')
                    )
                    test_request.assertions.append(Assertion(
                        assertion="Connection should be successful",
                        error=connection_error
                    ))

                # Extract response information
                response = run.get("response", {})
                status_code = response.get("code", 0)
                response_headers = {h.get("key", ""): h.get("value", "") for h in response.get("header", [])}
                response_body = response.get("stream", {})
                
                # Convert Buffer response body to readable text
                readable_response_body = self._convert_buffer_to_text(response_body)
                
                # Update test request with response info (excluding status code)
                test_request.response_headers = response_headers
                test_request.response_body = readable_response_body
                
                # Check for server errors in the response (simplified check)
                if 500 <= status_code <= 599:
                    test_request.is_server_error = True
                    run_success = False
                
                # Process assertions
                for assertion in run.get("assertions", []):
                    error_data = assertion.get("error")
                    assertion_error = None
                    if error_data is not None:
                        run_success = False
                        assertion_error = ReportAssertionError(
                            name=error_data.get("name", ""),
                            index=error_data.get("index", 0),
                            test=error_data.get("test", ""),
                            message=error_data.get("message", ""),
                            stack=error_data.get("stack", "")
                        )
                    
                    test_request.assertions.append(Assertion(
                        assertion=assertion.get("assertion", "Unknown assertion"),
                        error=assertion_error
                    ))
                
                test_request.success = run_success
                break
        
        return test_request

    def _convert_buffer_to_text(self, buffer_data):
        """Convert Newman buffer response to readable text"""
        if not buffer_data:
            return None
            
        if isinstance(buffer_data, dict) and "data" in buffer_data:
            # Handle Newman buffer format
            data = buffer_data["data"]
            if isinstance(data, list):
                try:
                    # Convert byte array to string
                    return ''.join(chr(byte) for byte in data if 0 <= byte <= 127)
                except (ValueError, TypeError):
                    return str(buffer_data)
        
        return str(buffer_data) if buffer_data else None

    def get_all_failed_reports(self) -> List[FailedTestReport]:
        """
        Get all test reports that contain failed test cases
        
        Returns:
            List of FailedTestReport objects containing only failed test cases
        """
        failed_reports = []
        
        for test_name in self.get_test_names():
            report = self.get_test_report(test_name)
            if not report:
                continue
            
            # Find failed test cases in this report
            failed_test_cases = [tc for tc in report.test_results if not tc.success]
            
            if failed_test_cases:
                # Create a FailedTestReport for this test suite
                failed_report = FailedTestReport(
                    test_suite_name=test_name,
                    failed_test_cases=failed_test_cases,
                    failed_test_cases_count=len(failed_test_cases),
                    total_test_cases=len(report.test_results),
                    timestamp=report.timestamp,
                    statistics=report.statistics
                )
                failed_reports.append(failed_report)
        
        return failed_reports


    def get_all_reports_statistics(self) -> Dict[str, Any]:
        """
        Generate comprehensive statistics for all test reports in the current run.
        Reuses existing calculate_report_statistics method for consistency.
        Returns detailed statistics including per-suite breakdown and overall totals.
        """
        if not self.reports_folder or not self.reports_folder.exists():
            return {
                'error': 'No reports directory found',
                'total_suites': 0,
                'total_cases': 0,
                'total_passed': 0,
                'total_failed': 0,
                'total_server_errors': 0,
                'overall_success_rate': 0.0,
                'suites': []
            }

        report_files = list(self.reports_folder.glob('*.json'))
        # Filter out _raw.json files
        report_files = [f for f in report_files if not f.name.endswith('_raw.json')]
        
        if not report_files:
            return {
                'total_suites': 0,
                'total_cases': 0,
                'total_passed': 0,
                'total_failed': 0,
                'total_server_errors': 0,
                'overall_success_rate': 0.0,
                'suites': []
            }

        total_suites = len(report_files)
        total_cases = 0
        total_passed = 0
        total_failed = 0
        total_server_errors = 0
        suites_details = []

        for report_file in report_files:
            try:
                # Load the report and get test cases
                report = self.get_test_report(report_file.stem)
                
                if not report:
                    suites_details.append({
                        'name': report_file.stem,
                        'status': "ERROR",
                        'error': "Could not load report",
                        'total': 0,
                        'passed': 0,
                        'failed': 0,
                        'server_errors': 0,
                        'success_rate': 0.0
                    })
                    continue

                # Reuse existing calculate_report_statistics method
                suite_stats = self.calculate_report_statistics(report.test_results)
                
                # Determine overall status
                if suite_stats.test_cases_with_server_errors > 0:
                    status = "SERVER_ERROR"
                elif suite_stats.failed_test_cases > 0:
                    status = "FAILED"
                else:
                    status = "PASSED"

                # Add suite details
                suites_details.append({
                    'name': report_file.stem,
                    'status': status,
                    'total': suite_stats.total_test_cases,
                    'passed': suite_stats.passed_test_cases,
                    'failed': suite_stats.failed_test_cases,
                    'server_errors': suite_stats.test_cases_with_server_errors,
                    'success_rate': suite_stats.success_rate
                })

                # Update totals
                total_cases += suite_stats.total_test_cases
                total_passed += suite_stats.passed_test_cases
                total_failed += suite_stats.failed_test_cases
                total_server_errors += suite_stats.test_cases_with_server_errors

            except Exception as e:
                # Add error suite
                suites_details.append({
                    'name': report_file.stem,
                    'status': "ERROR",
                    'error': str(e),
                    'total': 0,
                    'passed': 0,
                    'failed': 0,
                    'server_errors': 0,
                    'success_rate': 0.0
                })

        # Calculate overall success rate
        overall_success_rate = (total_passed / total_cases * 100) if total_cases > 0 else 0

        return {
            'total_suites': total_suites,
            'total_cases': total_cases,
            'total_passed': total_passed,
            'total_failed': total_failed,
            'total_server_errors': total_server_errors,
            'overall_success_rate': overall_success_rate,
            'suites': suites_details
        }

    def print_statistics_summary(self) -> None:
        """
        Print a formatted statistics summary to console.
        Useful for CLI reporting.
        """
        stats = self.get_all_reports_statistics()
        
        if 'error' in stats:
            print(f"Error generating statistics: {stats['error']}")
            return

        print("\n" + "="*60)
        print("TEST EXECUTION STATISTICS")
        print("="*60)
        
        if stats['total_suites'] == 0:
            print("No test suites found in reports directory.")
            return

        print(f"Test Suites: {stats['total_suites']}")
        print(f"Total Cases: {stats['total_cases']}")
        print(f"Passed: {stats['total_passed']}")
        print(f"Failed: {stats['total_failed']}")
        print(f"Server Errors: {stats['total_server_errors']}")
        print(f"Success Rate: {stats['overall_success_rate']:.1f}%")


