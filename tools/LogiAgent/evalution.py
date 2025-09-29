def categorize_endpoints_by_status_with_graph(all_request_sequence, rest_graph=None):
    """
    Categorize unique endpoints by HTTP status code ranges using REST graph for normalization.
    
    Args:
        all_request_sequence: List of request/response dictionaries
        rest_graph: RESTGraph instance for endpoint normalization (optional)
        
    Returns:
        dict: Categorized endpoints by status code ranges
    """
    categories = {
        '200': set(),  # 200-299 Success
        '300': set(),  # 300-399 Redirection
        '400': set(),  # 400-499 Client Error
        '500': set()   # 500-599 Server Error
    }

    total_500_count = 0

    for request in all_request_sequence:
        response_code = request.get('response_code')
        method = request.get('method')
        api = request.get('api')
        
        if method and api and response_code:
            if rest_graph:
                # Try to find matching endpoint pattern in REST graph
                endpoint_key = None
                for node_signature in rest_graph.api_nodes:
                    node = rest_graph.api_nodes[node_signature]
                    if node.api_method.upper() == method.upper():
                        # Check if the path matches the pattern
                        if api.startswith(node.api_name.split('{')[0]):
                            endpoint_key = node_signature
                            break
                
            else:
                raise ValueError("Unable to categorize endpoint without REST graph")

            # Categorize by status code range
            if 200 <= response_code < 300:
                category = '200'
            elif 300 <= response_code < 400:
                category = '300'
            elif 400 <= response_code < 500:
                category = '400'
            elif 500 <= response_code < 600:
                category = '500'
                total_500_count += 1
            else:
                continue  # Skip invalid status codes

            categories[category].add(endpoint_key)

    result = {}
    for category in categories:
        if category == '500':
            result[category] = total_500_count
        else:
            result[category] = categories[category]

    return result