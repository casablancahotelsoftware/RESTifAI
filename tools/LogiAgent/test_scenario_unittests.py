import test_scenario
from test_scenario import record_useful_items

def test_record_useful_items():
    # Reset useful_items before testing
    test_scenario.useful_items = {}

    # Test Case 1: Original format (simple dictionary)
    simple_input = {
        "user_id": {"value": 123, "description": "The user identifier"},
        "username": {"value": "john", "description": "The user's name"}
    }
    record_useful_items(simple_input)
    assert "user_id" in test_scenario.useful_items
    assert "username" in test_scenario.useful_items
    assert test_scenario.useful_items["user_id"][0]["value"] == 123
    assert test_scenario.useful_items["username"][0]["value"] == "john"
    print("✓ Test Case 1: Simple dictionary format passed")

    # Test Case 2: List format with nested objects
    list_input = {
        "items": {
            "bills": [{
                "billId": {"value": 2818, "description": "Unique identifier for the Bill"},
                "shortTitle": {"value": "Test Bill", "description": "The short title"},
                "currentStage": {
                    "id": {"value": 12655, "description": "Stage ID"},
                    "description": {"value": "2nd reading", "description": "Stage description"}
                }
            }]
        }
    }
    record_useful_items(list_input)
    assert "items.bills.billId" in test_scenario.useful_items
    assert "items.bills.shortTitle" in test_scenario.useful_items
    assert "items.bills.currentStage.id" in test_scenario.useful_items
    assert "items.bills.currentStage.description" in test_scenario.useful_items
    assert test_scenario.useful_items["items.bills.billId"][0]["value"] == 2818
    assert test_scenario.useful_items["items.bills.currentStage.description"][0]["value"] == "2nd reading"
    print("✓ Test Case 2: Nested list format passed")

    # Test Case 3: Multiple values for same parameter
    multiple_values = {
        "status": {"value": "active", "description": "First status"},
    }
    record_useful_items(multiple_values)
    multiple_values = {
        "status": {"value": "inactive", "description": "Second status"},
    }
    record_useful_items(multiple_values)
    assert len(test_scenario.useful_items["status"]) == 2
    assert any(item["value"] == "active" for item in test_scenario.useful_items["status"])
    assert any(item["value"] == "inactive" for item in test_scenario.useful_items["status"])
    print("✓ Test Case 3: Multiple values passed")

    # Test Case 4: Limit of 5 values
    for i in range(7):
        record_useful_items({
            "counter": {"value": i, "description": f"Count {i}"}
        })
    assert len(test_scenario.useful_items["counter"]) == 5
    assert test_scenario.useful_items["counter"][0]["value"] == 2  # Should start from 2, not 0
    assert test_scenario.useful_items["counter"][-1]["value"] == 6
    print("✓ Test Case 4: Five items limit passed")

    # Test Case 5: Update existing value's description
    record_useful_items({
        "test_key": {"value": "test_value", "description": "First description"}
    })
    record_useful_items({
        "test_key": {"value": "test_value", "description": "Updated description"}
    })
    assert len(test_scenario.useful_items["test_key"]) == 1
    assert test_scenario.useful_items["test_key"][0]["description"] == "Updated description"
    print("✓ Test Case 5: Update description passed")

    # Test Case 6: Realworld data: list of bills
    list_of_bills = {"bills":[{"billId":{"value":2818,"description":"Unique identifier for the Abolition of Business Rates Bill."},"shortTitle":{"value":"Abolition of Business Rates Bill","description":"The short title of this Bill."},"currentHouse":{"value":"Commons","description":"The current house where the Bill is."},"originatingHouse":{"value":"Commons","description":"The house where the Bill originated."},"lastUpdate":{"value":"2021-05-04T10:42:08.0579851","description":"Last update timestamp of the Bill."},"isDefeated":{"value":False,"description":"Indicates if the Bill has been defeated."},"billTypeId":{"value":5,"description":"Type identifier for the Bill."},"currentStage":{"id":{"value":12655,"description":"Unique identifier of the current stage."},"stageId":{"value":7,"description":"Identifier for the stage."},"sessionId":{"value":35,"description":"Session identifier associated with the stage."},"description":{"value":"2nd reading","description":"Description of the current stage."},"abbreviation":{"value":"2R","description":"Abbreviation of the current stage."},"house":{"value":"Commons","description":"House relevant to this stage."}}},{"billId":{"value":2302,"description":"Unique identifier for the Abortion Bill."},"shortTitle":{"value":"Abortion Bill","description":"The short title of this Bill."},"currentHouse":{"value":"Commons","description":"The current house where the Bill is."},"originatingHouse":{"value":"Commons","description":"The house where the Bill originated."},"lastUpdate":{"value":"2019-09-17T16:22:10","description":"Last update timestamp of the Bill."},"isDefeated":{"value":False,"description":"Indicates if the Bill has been defeated."},"billTypeId":{"value":5,"description":"Type identifier for the Bill."},"currentStage":{"id":{"value":15039,"description":"Unique identifier of the current stage."},"stageId":{"value":7,"description":"Identifier for the stage."},"sessionId":{"value":30,"description":"Session identifier associated with the stage."},"description":{"value":"2nd reading","description":"Description of the current stage."},"abbreviation":{"value":"2R","description":"Abbreviation of the current stage."},"house":{"value":"Commons","description":"House relevant to this stage."}}},{"billId":{"value":2556,"description":"Unique identifier for the Abortion Bill [HL]."},"shortTitle":{"value":"Abortion Bill [HL]","description":"The short title of this Bill."},"currentHouse":{"value":"Lords","description":"The current house where the Bill is."},"originatingHouse":{"value":"Lords","description":"The house where the Bill originated."},"lastUpdate":{"value":"2021-05-05T11:05:17.4984479","description":"Last update timestamp of the Bill."},"isDefeated":{"value":False,"description":"Indicates if the Bill has been defeated."},"billTypeId":{"value":2,"description":"Type identifier for the Bill."},"currentStage":{"id":{"value":11662,"description":"Unique identifier of the current stage."},"stageId":{"value":2,"description":"Identifier for the stage."},"sessionId":{"value":35,"description":"Session identifier associated with the stage."},"description":{"value":"2nd reading","description":"Description of the current stage."},"abbreviation":{"value":"2R","description":"Abbreviation of the current stage."},"house":{"value":"Lords","description":"House relevant to this stage."}}},{"billId":{"value":2743,"description":"Unique identifier for the Abortion (Cleft Lip, Cleft Palate and Clubfoot) Bill."},"shortTitle":{"value":"Abortion (Cleft Lip, Cleft Palate and Clubfoot) Bill","description":"The short title of this Bill."},"currentHouse":{"value":"Commons","description":"The current house where the Bill is."},"originatingHouse":{"value":"Commons","description":"The house where the Bill originated."},"lastUpdate":{"value":"2021-05-04T10:55:22.6940381","description":"Last update timestamp of the Bill."},"isDefeated":{"value":False,"description":"Indicates if the Bill has been defeated."},"billTypeId":{"value":8,"description":"Type identifier for the Bill."},"currentStage":{"id":{"value":12196,"description":"Unique identifier of the current stage."},"stageId":{"value":7,"description":"Identifier for the stage."},"sessionId":{"value":35,"description":"Session identifier associated with the stage."},"description":{"value":"2nd reading","description":"Description of the current stage."},"abbreviation":{"value":"2R","description":"Abbreviation of the current stage."},"house":{"value":"Commons","description":"House relevant to this stage."}}}]}
    record_useful_items(list_of_bills)

    # Verify bill IDs are captured
    assert "bills.billId" in test_scenario.useful_items
    assert len(test_scenario.useful_items["bills.billId"]) == 4
    assert any(item["value"] == 2818 for item in test_scenario.useful_items["bills.billId"])
    assert any(item["value"] == 2302 for item in test_scenario.useful_items["bills.billId"])
    assert any(item["value"] == 2556 for item in test_scenario.useful_items["bills.billId"])
    assert any(item["value"] == 2743 for item in test_scenario.useful_items["bills.billId"])

    # Verify short titles are captured
    assert "bills.shortTitle" in test_scenario.useful_items
    assert len(test_scenario.useful_items["bills.shortTitle"]) == 4
    assert any(item["value"] == "Abolition of Business Rates Bill" for item in test_scenario.useful_items["bills.shortTitle"])
    assert any(item["value"] == "Abortion Bill" for item in test_scenario.useful_items["bills.shortTitle"])
    assert any(item["value"] == "Abortion Bill [HL]" for item in test_scenario.useful_items["bills.shortTitle"])
    assert any(item["value"] == "Abortion (Cleft Lip, Cleft Palate and Clubfoot) Bill" for item in test_scenario.useful_items["bills.shortTitle"])

    # Verify nested stage information is captured
    assert "bills.currentStage.description" in test_scenario.useful_items
    assert len(test_scenario.useful_items["bills.currentStage.description"]) == 1  # All bills are in "2nd reading"
    assert test_scenario.useful_items["bills.currentStage.description"][0]["value"] == "2nd reading"
    print("✓ Test Case 6: Real-world bills data passed")    

    print("\nAll tests passed successfully!")


if __name__ == '__main__':
    test_record_useful_items()