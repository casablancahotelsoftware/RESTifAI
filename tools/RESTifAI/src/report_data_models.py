from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union, Any
import json


@dataclass
class UrlVariable:
    """Represents a URL variable in request data"""
    type: str
    value: str
    key: str


@dataclass
class QueryParameter:
    """Represents a query parameter in request data"""
    key: str
    value: str


@dataclass
class Header:
    """Represents a header in request data"""
    key: str
    value: str


@dataclass
class UrlInfo:
    """Represents URL information in request data"""
    path: List[str]
    host: List[str]
    query: List[QueryParameter]
    variable: List[UrlVariable]


@dataclass
class RequestBody:
    """Represents request body data"""
    mode: str
    raw: str
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RequestData:
    """Represents request data structure"""
    url: UrlInfo
    header: List[Header]
    method: str
    body: RequestBody


@dataclass
class ReportAssertionError:
    """Represents an assertion error in test results"""
    name: str
    index: int
    test: str
    message: str
    stack: str


@dataclass
class Assertion:
    """Represents a test assertion"""
    assertion: str
    error: Optional[ReportAssertionError]


@dataclass
class TestRequest:
    """Represents a test request with all its data"""
    name: str
    id: str
    data: RequestData
    success: bool
    assertions: List[Assertion]
    is_server_error: bool
    response_headers: Dict[str, str]
    response_body: Optional[Union[Dict, str, Any]]


@dataclass
class TestCase:
    """Represents a single test case with multiple requests"""
    test_case_name: str
    success: bool
    requests: List[TestRequest]
    has_server_error: bool


@dataclass
class TestStatistics:
    """Represents simplified test statistics"""
    total_test_cases: int
    passed_test_cases: int
    failed_test_cases: int
    test_cases_with_server_errors: int
    total_requests: int
    success_rate: float = 0.0
    avg_requests_per_case: float = 0.0


@dataclass
class TestReport:
    """Represents a complete test report"""
    test_name: str
    test_results: List[TestCase]
    success: bool
    timestamp: str
    statistics: TestStatistics
    
    @classmethod
    def from_newman_report(cls, newman_data: Dict[str, Any]) -> 'TestReport':
        """Create a TestReport instance from Newman report data"""
        from datetime import datetime
        
        # Extract basic fields with defaults
        test_name = newman_data.get('test_name', 'Unknown Test')
        success = newman_data.get('success', False)
        timestamp = newman_data.get('timestamp', datetime.now().isoformat())
        
        # Convert test results
        test_results = []
        if 'test_results' in newman_data and newman_data['test_results']:
            for case_data in newman_data['test_results']:
                test_results.append(cls._convert_to_test_case(case_data))
        
        # Convert statistics
        statistics_data = newman_data.get('statistics', {})
        
        # Handle case where statistics might be missing or incomplete
        if not statistics_data or not isinstance(statistics_data, dict):
            statistics = TestStatistics(
                total_test_cases=len(test_results),
                passed_test_cases=sum(1 for tc in test_results if tc.success),
                failed_test_cases=sum(1 for tc in test_results if not tc.success),
                test_cases_with_server_errors=sum(1 for tc in test_results if tc.has_server_error),
                total_requests=sum(len(tc.requests) for tc in test_results)
            )
            
            # Calculate rates
            if statistics.total_test_cases > 0:
                statistics.success_rate = (statistics.passed_test_cases / statistics.total_test_cases * 100)
                statistics.avg_requests_per_case = (statistics.total_requests / statistics.total_test_cases)
        else:
            statistics = cls._convert_to_test_statistics(statistics_data)
        
        return cls(
            test_name=test_name,
            test_results=test_results,
            success=success,
            timestamp=timestamp,
            statistics=statistics
        )
    
    @staticmethod
    def _convert_to_test_case(data: Dict[str, Any]) -> TestCase:
        """Convert dictionary data to TestCase instance"""
        kwargs = {}
        
        # Handle test_case_name
        kwargs['test_case_name'] = data.get('test_case_name', '')
        
        # Handle success
        kwargs['success'] = data.get('success', False)
        
        # Handle has_server_error
        kwargs['has_server_error'] = data.get('has_server_error', False)
        
        # Handle requests list
        requests_data = data.get('requests', [])
        kwargs['requests'] = [TestReport._convert_to_test_request(req) for req in requests_data if req is not None]
        
        return TestCase(**kwargs)
    
    @staticmethod
    def _convert_to_test_request(data: Dict[str, Any]) -> TestRequest:
        """Convert dictionary data to TestRequest instance"""
        kwargs = {}
        
        # Handle basic fields
        kwargs['name'] = data.get('name', '')
        kwargs['id'] = data.get('id', '')
        kwargs['success'] = data.get('success', False)
        kwargs['is_server_error'] = data.get('is_server_error', False)
        kwargs['response_headers'] = data.get('response_headers', {})
        kwargs['response_body'] = data.get('response_body')
        
        # Handle data field (RequestData)
        data_dict = data.get('data', {})
        kwargs['data'] = TestReport._convert_to_request_data(data_dict)
        
        # Handle assertions list
        assertions_data = data.get('assertions', [])
        kwargs['assertions'] = [TestReport._convert_to_assertion(assertion) for assertion in assertions_data if assertion is not None]
        
        return TestRequest(**kwargs)
    
    @staticmethod
    def _convert_to_request_data(data: Dict[str, Any]) -> RequestData:
        """Convert dictionary data to RequestData instance"""
        kwargs = {}
        
        # Handle method
        kwargs['method'] = data.get('method', '')
        
        # Handle url (UrlInfo)
        url_data = data.get('url', {})
        kwargs['url'] = TestReport._convert_to_url_info(url_data)
        
        # Handle header list
        header_data = data.get('header', [])
        kwargs['header'] = [TestReport._convert_to_header(h) for h in header_data if h is not None]
        
        # Handle body (RequestBody)
        body_data = data.get('body', {})
        kwargs['body'] = TestReport._convert_to_request_body(body_data)
        
        return RequestData(**kwargs)
    
    @staticmethod
    def _convert_to_url_info(data: Dict[str, Any]) -> UrlInfo:
        """Convert dictionary data to UrlInfo instance"""
        kwargs = {}
        
        kwargs['path'] = data.get('path', [])
        kwargs['host'] = data.get('host', [])
        
        # Handle query list
        query_data = data.get('query', [])
        kwargs['query'] = [TestReport._convert_to_query_parameter(q) for q in query_data if q is not None]
        
        # Handle variable list
        variable_data = data.get('variable', [])
        kwargs['variable'] = [TestReport._convert_to_url_variable(v) for v in variable_data if v is not None]
        
        return UrlInfo(**kwargs)
    
    @staticmethod
    def _convert_to_header(data: Dict[str, Any]) -> Header:
        """Convert dictionary data to Header instance"""
        return Header(
            key=data.get('key', ''),
            value=data.get('value', '')
        )
    
    @staticmethod
    def _convert_to_query_parameter(data: Dict[str, Any]) -> QueryParameter:
        """Convert dictionary data to QueryParameter instance"""
        return QueryParameter(
            key=data.get('key', ''),
            value=data.get('value', '')
        )
    
    @staticmethod
    def _convert_to_url_variable(data: Dict[str, Any]) -> UrlVariable:
        """Convert dictionary data to UrlVariable instance"""
        return UrlVariable(
            type=data.get('type', ''),
            value=data.get('value', ''),
            key=data.get('key', '')
        )
    
    @staticmethod
    def _convert_to_request_body(data: Dict[str, Any]) -> RequestBody:
        """Convert dictionary data to RequestBody instance"""
        # Special handling for empty or None body
        if data is None or (isinstance(data, dict) and not data):
            return RequestBody(mode="raw", raw="", options={})
        
        return RequestBody(
            mode=data.get('mode', 'raw'),
            raw=data.get('raw', ''),
            options=data.get('options', {})
        )
    
    @staticmethod
    def _convert_to_assertion(data: Dict[str, Any]) -> Assertion:
        """Convert dictionary data to Assertion instance"""
        kwargs = {}
        
        kwargs['assertion'] = data.get('assertion', 'Unknown assertion')
        
        # Handle error field (ReportAssertionError)
        error_data = data.get('error')
        if error_data is not None:
            kwargs['error'] = TestReport._convert_to_assertion_error(error_data)
        else:
            kwargs['error'] = None
        
        return Assertion(**kwargs)
    
    @staticmethod
    def _convert_to_assertion_error(data: Dict[str, Any]) -> ReportAssertionError:
        """Convert dictionary data to ReportAssertionError instance"""
        return ReportAssertionError(
            name=data.get('name', ''),
            index=data.get('index', 0),
            test=data.get('test', ''),
            message=data.get('message', ''),
            stack=data.get('stack', '')
        )
    
    @staticmethod
    def _convert_to_test_statistics(data: Dict[str, Any]) -> TestStatistics:
        """Convert dictionary data to TestStatistics instance"""
        # If data is already a TestStatistics instance, return it
        if isinstance(data, TestStatistics):
            return data
            
        # Ensure numeric values are properly handled
        total_test_cases = int(data.get('total_test_cases', 0))
        passed_test_cases = int(data.get('passed_test_cases', 0))
        failed_test_cases = int(data.get('failed_test_cases', 0))
        test_cases_with_server_errors = int(data.get('test_cases_with_server_errors', 0))
        total_requests = int(data.get('total_requests', 0))
        
        # Calculate rates if they're not provided or if they're invalid
        if total_test_cases > 0:
            success_rate = float(data.get('success_rate', (passed_test_cases / total_test_cases * 100)))
            avg_requests_per_case = float(data.get('avg_requests_per_case', (total_requests / total_test_cases)))
        else:
            success_rate = 0.0
            avg_requests_per_case = 0.0
            
        return TestStatistics(
            total_test_cases=total_test_cases,
            passed_test_cases=passed_test_cases,
            failed_test_cases=failed_test_cases,
            test_cases_with_server_errors=test_cases_with_server_errors,
            total_requests=total_requests,
            success_rate=success_rate,
            avg_requests_per_case=avg_requests_per_case
        )


@dataclass
class FailedTestReport:
    """Represents a report containing only failed test cases"""
    test_suite_name: str
    timestamp: str
    total_test_cases: int
    failed_test_cases_count: int
    failed_test_cases: List[TestCase] = field(default_factory=list)
    statistics: TestStatistics = field(default_factory=lambda: TestStatistics(
        total_test_cases=0,
        passed_test_cases=0,
        failed_test_cases=0,
        test_cases_with_server_errors=0,
        total_requests=0
    ))


def dataclass_to_dict(obj) -> Dict[str, Any]:
    """Convert a dataclass instance to a dictionary, handling nested dataclasses"""
    if hasattr(obj, '__dataclass_fields__'):
        result = {}
        for field_name, field_def in obj.__dataclass_fields__.items():
            value = getattr(obj, field_name)
            if hasattr(value, '__dataclass_fields__'):
                # Nested dataclass
                result[field_name] = dataclass_to_dict(value)
            elif isinstance(value, list):
                # List of potentially dataclass objects
                result[field_name] = [
                    dataclass_to_dict(item) if hasattr(item, '__dataclass_fields__') else item
                    for item in value
                ]
            elif isinstance(value, dict):
                # Dict with potentially dataclass values
                result[field_name] = {
                    k: dataclass_to_dict(v) if hasattr(v, '__dataclass_fields__') else v
                    for k, v in value.items()
                }
            else:
                result[field_name] = value
        return result
    return obj