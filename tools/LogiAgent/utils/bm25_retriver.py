import re

from rank_bm25 import BM25Okapi


def bm25_filter_useful_items(useful_item_text: str, tc_info: str, top_n: int = 10) -> str:
    """
    Use BM25 algorithm to find and return top N most relevant items from input text based on query.
    
    Args:
        useful_item_text (str): Input text containing items, split by newlines
        tc_info (str): Query text to match against the items
        top_n (int, optional): Number of most relevant items to return. Defaults to 10

    Returns:
        str: Top N most relevant items joined by newlines
    """
    documents = useful_item_text.split("\n")

    def tokenize(text):
        return re.findall(r'\w+', text.lower())
    tokenized_documents = [tokenize(doc) for doc in documents]
    bm25 = BM25Okapi(tokenized_documents)
    query = tokenize(tc_info)
    scores = bm25.get_scores(query)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_n]
    relevant_items = [documents[i] for i in top_indices]

    return "\n".join(relevant_items)


if __name__ == '__main__':
    item = """The param 'id' has the following previous returned values: 12345.
The param 'username' has the following previous returned values: user_X7YtE9W.
The param 'firstName' has the following previous returned values: John.
The param 'lastName' has the following previous returned values: Doe, Doe_Updated.
The param 'email' has the following previous returned values: john.doe@example.com, john.updated@example.com.
The param 'phone' has the following previous returned values: 123-456-7890.
The param 'userStatus' has the following previous returned values: 1.
The param 'password' has the following previous returned values: password_123."""

    tc_info = """**TestCase**:Validate Updated User Information
**API Endpoint**:GET /user/{{username}}
**Test Description**:Retrieve the updated user information to ensure the changes were successful.
**Expected Response**:A successful response with status code 200 containing the updated user information reflecting the changes made in the previous step.
**Swagger API Info**:Endpoint: GET /user/{username}
OperationId: getUserByName: Get user by user name
Parameters:
- username (string, Required): The name that needs to be fetched. Use user1 for testing. 
Responses:
- Status 200: successful operation. Response Body:
    Object with properties:
    - id (integer): 
    - username (string): 
    - firstName (string): 
    - lastName (string): 
    - email (string): 
    - password (string): 
    - phone (string): 
    - userStatus (integer): User Status
- Status 400: Invalid username supplied. 
- Status 404: User not found. """

    results = bm25_filter_useful_items(item, tc_info, top_n=5)
    print(f"{results}")
