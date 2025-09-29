
def generate_example(schema: dict) -> dict:
    """Generate a JSON example from a Swagger schema."""
    example = {}
    properties = schema.get("properties", {})
    required_fields = schema.get("required", [])

    for field, field_schema in properties.items():
        field_type = field_schema.get("type", "string")
        field_example = f"{field} example"  # Default example text

        # Define example values based on field type
        if field_type == "string":
            field_example = field_schema.get("example", f"{field} example")
        elif field_type == "integer":
            field_example = field_schema.get("example", 123)
        elif field_type == "boolean":
            field_example = field_schema.get("example", True)
        elif field_type == "array":
            item_schema = field_schema.get("items", {})
            field_example = [generate_example(item_schema)]
        elif field_type == "object":
            field_example = generate_example(field_schema)

        # Set required fields with defined example or default example
        if field in required_fields:
            example[field] = field_example
        elif "example" in field_schema:
            example[field] = field_example

    return example


def parse_request_body(request_body: dict) -> dict:
    """Parse Swagger requestBody schema to JSON example."""
    if 'content' not in request_body:
        raise ValueError("Invalid request body schema")

    # Extract JSON schema from the request body content
    json_schema = request_body['content'].get('application/json', {}).get('schema', {})
    return generate_example(json_schema)


def schema_to_text(schema, indent=0, max_indent=10000):
    """
    Converts a JSON schema to a readable text format.

    Parameters:
        schema (dict): The JSON schema to be converted.
        indent (int): The indentation level for nested objects.
        max_indent (int): The maximum indentation level for nested objects.

    Returns:
        str: Text representation of the schema.
    """
    text = ""
    indent_str = "  " * indent

    if indent > max_indent:
        indent_str = indent_str + " "*2
        text += f"{indent_str}(The content is too long, omit it.)\n"
        return text

    if "type" in schema:
        schema_type = schema["type"]
        if schema_type == "object":
            text += f"{indent_str}Object with properties:\n"
            properties = schema.get("properties", {})
            for prop, prop_schema in properties.items():
                prop_type = prop_schema.get("type", "Unknown type")
                prop_desc = prop_schema.get("description", "")
                prop_enum = prop_schema.get("enum", [])
                if prop_enum:
                    text += f"{indent_str}- {prop} ({prop_type}): {prop_desc}. Enum for this prop:{prop_enum}\n"
                else:
                    text += f"{indent_str}- {prop} ({prop_type}): {prop_desc}\n"
                # Recursively handle nested objects
                if prop_type == "object" or prop_type == "array":
                    text += schema_to_text(prop_schema, indent + 1, max_indent)
        elif schema_type == "array":
            items = schema.get("items", {})
            text += f"{indent_str}Array of:\n"
            text += schema_to_text(items, indent + 1, max_indent)
        else:
            text += f"{indent_str}{schema_type.capitalize()}\n"
    elif "properties" in schema:
        properties = schema.get("properties", {})
        for prop, prop_schema in properties.items():
            prop_type = prop_schema.get("type", "Unknown type")
            prop_desc = prop_schema.get("description", "")
            prop_enum = prop_schema.get("enum", [])
            if prop_enum:
                text += f"{indent_str}- {prop} ({prop_type}): {prop_desc}. Enum for this prop:{prop_enum}\n"
            else:
                text += f"{indent_str}- {prop} ({prop_type}): {prop_desc}\n"
            # Recursively handle nested objects
            if prop_type == "object" or prop_type == "array":
                text += schema_to_text(prop_schema, indent + 1, max_indent)

    return text


def swagger_to_text(endpoint):
    """
    Converts a single Swagger endpoint specification into an English textual description.

    Parameters:
        endpoint (dict): A dictionary representing a single Swagger endpoint specification.

    Returns:
        str: A textual description of the endpoint.
    """
    # Extract essential parts of the endpoint
    tags = ", ".join(endpoint.get("tags", []))
    summary = endpoint.get("summary", "")
    operation_id = endpoint.get("operationId", "")
    request_body = endpoint.get("requestBody", {})
    responses = endpoint.get("responses", {})

    # Construct the basic description with summary and tags
    description = f"OperationId: {operation_id}: {summary}\n"

    # Handle request parameters if they exist
    parameters = endpoint.get("parameters", [])
    if parameters:
        description += "Parameters:\n"
        for param in parameters:
            param_desc = param.get("description", "No description provided.")
            param_name = param.get("name", "Unnamed")
            param_required = "Required" if param.get("required", False) else "Optional"
            param_type = param.get("schema", {}).get("type", "Unknown type")
            description += f"- {param_name} ({param_type}, {param_required}): {param_desc}\n"

    # Handle request body if it exists
    if request_body:
        description += f"Request Body:\n"
        rb_description = request_body.get("description", "")
        if rb_description:
            description += f"Description: {rb_description}.\n"

        request_body_content = request_body.get("content", {})
        if len(request_body_content) > 1:
            # default request body type
            request_body_type = "application/json"
        elif len(request_body_content) == 0:
            request_body_type = "No request body in document\n"
        else:
            request_body_type = list(request_body_content.keys())[0]
        if request_body_type == "application/json":
            description += f"Content Type: {request_body_type}\n"
        else:
            description += f"**Content Type**: **{request_body_type}**\n"

        body_schema = request_body_content.get(request_body_type).get("schema", {})
        if body_schema:
            description += "Body schema:\n" + schema_to_text(body_schema)


    # Handle responses
    if responses:
        description += "Responses:\n"
        for status, response in responses.items():
            response_desc = response.get("description", "No description provided.")
            resp_body_schema = response.get("content", {}).get("application/json", {}).get("schema", {})
            description += f"- Status {status}: {response_desc}. "
            if resp_body_schema and type(resp_body_schema) == dict:
                description += "Response Body:\n"
                valida_description = schema_to_text(resp_body_schema, indent=2)
                if len(valida_description) > 10000:
                    valida_description = schema_to_text(resp_body_schema, indent=2, max_indent=3)
                description += valida_description
            else:
                description += "\n"

    return description
