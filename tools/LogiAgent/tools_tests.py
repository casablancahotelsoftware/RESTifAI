import pytest
from tools import remove_duplicate_path_segment
import unittest


class TestRemoveDuplicatePathSegment(unittest.TestCase):
    def test_normal_api_path(self):
        """Test normal 'api' duplicate path"""
        base_url = "http://example.com/api"
        api_path = "/api/users"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "http://example.com/api/users")

    def test_api_path_with_trailing_slash(self):
        """Test base_url with trailing slash"""
        base_url = "http://example.com/api/"
        api_path = "/api/users"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "http://example.com/api/users")

    def test_api_path_with_leading_slash(self):
        """Test api_path with leading slash"""
        base_url = "http://example.com/api"
        api_path = "api/users" # Intentionally without leading /, function should handle it
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "http://example.com/api/users")

    def test_api_v1_path(self):
        """Test 'api/v1' type duplicate path"""
        base_url = "https://example.com/api/v1"
        api_path = "/api/v1/resources"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "https://example.com/api/v1/resources")

    def test_api_v2_path(self):
        """Test 'api/v2' type duplicate path, verify version number matching"""
        base_url = "https://service.com/api/v2"
        api_path = "/api/v2/data"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "https://service.com/api/v2/data")

    def test_v_number_path(self):
        """Test 'v-number' type duplicate path"""
        base_url = "https://domain.com/v3"
        api_path = "/v3/items"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "https://domain.com/v3/items")

    def test_no_duplicate_path(self):
        """Test case with no duplicate path - expect single slash"""
        base_url = "https://example.net/base"
        api_path = "/new_api/endpoint"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "https://example.net/base/new_api/endpoint") # expect single slash

    def test_similar_but_not_duplicate_path(self):
        """Test similar but not completely duplicate paths, should not deduplicate - expect single slash"""
        base_url = "http://example.com/api_base"
        api_path = "/api_path/users"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "http://example.com/api_base/api_path/users") # expect single slash

    def test_version_mismatch_no_dedup(self):
        """Test version number mismatch case, should not deduplicate - expect single slash"""
        base_url = "http://api.test.com/api/v1"
        api_path = "/api/v2/resources"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "http://api.test.com/api/v1/api/v2/resources") # expect single slash

    def test_empty_base_url(self):
        """Test empty base_url case - expect single slash"""
        base_url = ""
        api_path = "/api/items"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "/api/items") # expect single slash

    def test_empty_api_path(self):
        """Test empty api_path case - expect single slash"""
        base_url = "https://domain.info/root"
        api_path = ""
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "https://domain.info/root/") # expect single slash (keep trailing slash)

    def test_both_empty_strings(self):
        """Test both base_url and api_path are empty strings - expect single slash"""
        base_url = ""
        api_path = ""
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "/") # expect single slash

    def test_complex_nested_api_path(self):
        """Test more complex API path structure"""
        base_url = "https://complex.org/service/api/v3"
        api_path = "/api/v3/module/action"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "https://complex.org/service/api/v3/module/action")

    def test_unconcerned_api_duplicate(self):
        """Test API path duplication that should not be removed"""
        base_url = "http://host.net/app"
        api_path = "/app/api/data"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "http://host.net/app/app/api/data")

    def test_longer_version_number(self):
        """Test version numbers with multiple digits, e.g., v10, api/v25"""
        base_url = "http://long-version.com/api/v10"
        api_path = "/api/v10/info"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "http://long-version.com/api/v10/info")

    def test_base_url_substring_no_rule_match(self):
        """Test base_url is substring of api_path but doesn't match dedup rules - expect single slash"""
        base_url = "testapi"
        api_path = "/testing_api/users"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "testapi/testing_api/users") # expect single slash

    def test_case_sensitive_overlap(self):
        """Test case-sensitive overlap, should be case-sensitive, no dedup - expect single slash"""
        base_url = "http://example.com/API"
        api_path = "/api/users" # Note: api is lowercase
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "http://example.com/API/api/users") # expect single slash

    def test_special_chars_in_path_no_dedup(self):
        """Test paths with special characters like _ - and should not be deduped"""
        base_url = "https://special-chars.com/api-test_v1"
        api_path = "/api-test_v1/data"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "https://special-chars.com/api-test_v1/api-test_v1/data")

    def simple_tests(self):
        # Test normal api path
        base_url = "http://example.com/api"
        api_path = "/api/users"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "http://example.com/api/users")

    def test_api_v1_path2(self):
        # Test path with version number
        base_url = "http://example.com/api/v1"
        api_path = "/api/v1/users"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "http://example.com/api/v1/users")

    def test_v_number_path2(self):
        # Test pure version number path
        base_url = "http://example.com/v1"
        api_path = "/v1/users"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "http://example.com/v1/users")

    def test_no_duplicate_path2(self):
        # Test path that doesn't need merging
        base_url = "http://example.com/api"
        api_path = "/users"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "http://example.com/api/users")

    def test_trailing_slash_in_base_url(self):
        # Test base_url with trailing slash
        base_url = "http://example.com/api/"
        api_path = "/api/users"
        result = remove_duplicate_path_segment(base_url, api_path)
        self.assertEqual(result, "http://example.com/api/users")


if __name__ == '__main__':
    unittest.main()
