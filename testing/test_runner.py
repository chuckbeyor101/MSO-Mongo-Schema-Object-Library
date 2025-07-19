# ######################################################################################################################
#  MSO Copyright (c) 2025 by Charles L Beyor and Beyotek Inc.                                                          #
#  is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International.                          #
#  To view a copy of this license, visit https://creativecommons.org/licenses/by-nc-sa/4.0/                            #
#                                                                                                                      #
#  Unless required by applicable law or agreed to in writing, software                                                 #
#  distributed under the License is distributed on an "AS IS" BASIS,                                                   #
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.                                            #
#  See the License for the specific language governing permissions and                                                 #
#  limitations under the License.                                                                                      #
#                                                                                                                      #
#  Gitlab: https://github.com/chuckbeyor101/MSO-Mongo-Schema-Object-Library                                            #
# ######################################################################################################################
import sys

from testing.database import initialize_test_db
from mso.generator import get_model
from mso.generator import get_model
from mso.base_model import MongoModel, pre_save, post_save
import pytest

test_paths = []
db = initialize_test_db.main()


# ####################################################################################################################################
# ------------------------------------------- Test Cases for Model / Schema Initialization -------------------------------------------
# ####################################################################################################################################
def test_get_model():
    People = get_model(db, "people")
    assert People is not None, "Failed to get model for 'people' collection"


# ####################################################################################################################################
# ------------------------------------------- Test Cases for Schema and Model Inspection -------------------------------------------
# ####################################################################################################################################
def test_tree_view():
    People = get_model(db, "people")
    People.print_nested_class_tree()


def test_pretty_print_schema():
    People = get_model(db, "people")
    People.print_nested_class_tree()


def test_print_fields():
    People = get_model(db, "people")
    print(People.fields())


def test_print_all_enums():
    People = get_model(db, "people")
    print(People.enums())


# ####################################################################################################################################
# ------------------------------------------- Test Cases for Developer Utilities ---------------------------------------------------
# ####################################################################################################################################
def test_life_cycle_hooks():
    test_state = {"post_save_called": False}

    class People(MongoModel):
        @post_save
        def announce_save(self):
            print("Saved: {}".format(self.name))
            # This is a post-save hook that will be called after the object is saved
            test_state["post_save_called"] = True

    People = get_model(db, "people")

    person = People(name="Tony Pajama Post Save Hook", age=34)
    person.health.primary_physician.name = "Dr. Strange"
    person.save()  # This should trigger the post_save hook and print "Saved: Tony Pajama"

    assert test_state["post_save_called"], "Post-save hook was not called"


# ####################################################################################################################################
# --------------------------------- Test Cases for Creating, Modifying, and Saving Objects -------------------------------------------
# ####################################################################################################################################
def test_create_save_from_dict():
    People = get_model(db, "people")

    person_data = {
        "name": "Tony Pajama From Dict",
        "age": 34,
        "health": {
            "primary_physician": {
                "name": "Dr. Strange",
                "contact": {
                    "phone": "123-456-7890"
                }
            }
        }
    }

    new_person = People.from_dict(person_data)
    new_person.save()

    assert new_person is not None, "Failed to create person from dict"


def test_create_save_from_obj():
    People = get_model(db, "people")

    new_person = People(name="Tony Pajama From Object", age=34)
    new_person.health.primary_physician.name = "Dr. Strange"
    new_person.health.primary_physician.contact.phone = "123-456-7890"
    new_person.addresses.add(type="Other", street="789 Oak St", city="Panama", state="NJ", zip="14862")

    # Add a new condition to the person's medical history
    condition = new_person.health.medical_history.conditions.add(
        name="Diabetes",
        diagnosed="2022-01-01"
    )

    # Now it's safe to call `.add()` because `medications` will auto-init
    condition.medications.add(
        name="Metformin",
        dose="500mg",
        frequency="2x daily"
    )

    # add an address using append
    address1 = People.addresses_item(type="Home", street="112 Rampart Rd", city="Panama", state="NJ", zip="14862")
    new_person.addresses.append(address1)

    # Modify medication by index reference
    new_person.health.medical_history.conditions[0].medications[0].dose = "1000mg"

    new_person.save()

    assert new_person is not None, "Failed to create person from object"


def test_soft_delete_and_restore():
    People = get_model(db, "people")

    person = People(name="Person to Restore", age=25)
    person.save()

    person.soft_delete()
    person.restore_deleted()


def test_permenantly_delete():
    People = get_model(db, "people")

    person = People(name="Person to Delete", age=25)
    person.save()

    person.delete()


def test_clone():
    People = get_model(db, "people")

    person = People(name="Person to Clone", age=25)
    person.save()

    cloned_person = person.clone()

    assert cloned_person is not None, "Failed to clone person"
    assert cloned_person.name == "Person to Clone", "Cloned person's name does not match original"
    assert cloned_person.age == 25, "Cloned person's age does not match original"


def test_find_and_modify():
    People = get_model(db, "people")

    # Create and save a person
    person = People(name="Person to Modify", age=25)
    person.save()

    # Find and modify the person
    modified_person = People.find_and_modify(
        {"name": "Person to Modify"},
        {"$set": {"age": 30}},
    )

    assert modified_person is not None, "Failed to find and modify person"


def test_bulk_save():
    People = get_model(db, "people")

    # Create multiple people
    person1 = People(name="Person Bulk Save One", age=30)
    person2 = People(name="Person Bulk Save Two", age=35)

    # Bulk save the people
    People.bulk_save([person1, person2])

    # Verify that both persons are saved
    found_people = People.find_many({"age": {"$gte": 30}})

    assert len(found_people) >= 2, "Bulk save did not save all persons"


def test_field_validation():
    People = get_model(db, "people")
    invalid_data = False

    # Create a person with invalid data
    try:
        person = People(name="Invalid Person", age="not_a_number")
        person.save()
    except ValueError as e:
        invalid_data = True
    except TypeError as e:
        invalid_data = True

    # Create a person with valid data
    person = People(name="Valid Person", age=25)
    person.save()

    assert invalid_data == True, "Field validation did not catch invalid data"
    assert person is not None, "Failed to create valid person"


# ####################################################################################################################################
# ------------------------------------------- Test Cases for Querying Database ---------------------------------------------------
# ####################################################################################################################################
def test_find_one():
    People = get_model(db, "people")

    # Create and save a person
    person = People(name="Person to Find", age=25)
    person.save()

    # Query the database
    found_person = People.find_one({"name": "Person to Find"})

    assert found_person is not None, "Failed to find person in database"
    assert found_person.name == "Person to Find", "Found person does not match expected name"


def test_find_many():
    People = get_model(db, "people")

    # Create and save multiple people
    person1 = People(name="Person One", age=30)
    person2 = People(name="Person Two", age=35)
    person1.save()
    person2.save()

    # Query the database
    found_people = People.find_many({"age": {"$gte": 30}})

    assert len(found_people) >= 2, "Failed to find multiple people in database"
    assert any(p.name == "Person One" for p in found_people), "Person One not found in results"
    assert any(p.name == "Person Two" for p in found_people), "Person Two not found in results"


def test_count():
    People = get_model(db, "people")

    # Create and save multiple people
    person1 = People(name="Person Count One", age=30)
    person2 = People(name="Person Count Two", age=35)
    person1.save()
    person2.save()

    # Count the number of people in the database
    count = People.count({"age": {"$gte": 30}})

    assert count >= 2, "Count of people in database does not match expected value"


def test_query():
    People = get_model(db, "people")

    # Create and save multiple people
    person1 = People(name="Person Query One", age=30)
    person2 = People(name="Person Query Two", age=35)
    person1.save()
    person2.save()

    # Query the database
    query_result = People.query({"age": {"$gte": 30}})

    assert len(query_result) >= 2, "Query did not return expected number of results"
    assert any(p.name == "Person Query One" for p in query_result), "Person Query One not found in results"
    assert any(p.name == "Person Query Two" for p in query_result), "Person Query Two not found in results"


def test_distinct():
    People = get_model(db, "people")

    # Create and save multiple people
    person1 = People(name="Person Distinct One", age=30)
    person2 = People(name="Person Distinct Two", age=35)
    person3 = People(name="Person Distinct Three", age=30)  # Same age as person1
    person1.save()
    person2.save()
    person3.save()

    # Get distinct ages
    distinct_ages = People.distinct("age")

    assert len(distinct_ages) > 2, "Distinct ages count does not match expected value"
    assert 30 in distinct_ages, "Age 30 not found in distinct ages"
    assert 35 in distinct_ages, "Age 35 not found in distinct ages"


def test_regex_query():
    People = get_model(db, "people")

    # Create and save multiple people
    person1 = People(name="Alice Smith", age=30)
    person2 = People(name="Bob Johnson", age=35)
    person3 = People(name="Charlie Brown", age=40)
    person1.save()
    person2.save()
    person3.save()

    # Query using regex
    regex_query = People.regex_query("name", ".*Smith")

    assert len(regex_query) == 1, "Regex query did not return expected number of results"


def test_paginate():
    People = get_model(db, "people")

    # Create and save multiple people
    person1 = People(name="Person Paginate One", age=30)
    person2 = People(name="Person Paginate Two", age=35)
    person3 = People(name="Person Paginate Three", age=40)
    person4 = People(name="Person Paginate Four", age=45)
    person1.save()
    person2.save()
    person3.save()
    person4.save()

    # Paginate the results
    page_size = 2
    page_number = 1
    paginated_results = People.paginate({}, page_number, page_size)

    assert len(paginated_results) == page_size, "Paginated results do not match expected page size"


def test_exists():
    People = get_model(db, "people")

    # Create and save a person
    person = People(name="Person Exists", age=25)
    person.save()

    # Check if the person exists
    exists = People.exists({"name": "Person Exists"})

    assert exists, "Person should exist in the database"


def test_get_one():
    People = get_model(db, "people")

    # Create and save a person
    person = People(name="Person Get One", age=25)
    person.save()

    # Get the person by name
    found_person = People.get_one({"name": "Person Get One"})

    assert found_person is not None, "Failed to get one person from database"
    assert found_person.name == "Person Get One", "Found person does not match expected name"


# ####################################################################################################################################
# ------------------------------------------- Test Cases for Model Data Inspection ---------------------------------------------------
# ####################################################################################################################################
def test_to_dict():
    People = get_model(db, "people")

    # Create and serialize
    person = People(name="Person Serialized To Dict", age=25)
    person.save()

    person_dict = person.to_dict()
    person_json = person.to_dict(output_json=True)

    assert isinstance(person_dict, dict), "to_dict() did not return a dictionary"
    assert isinstance(person_json, dict), "to_dict(output_json=True) did not return a JSON string"


# ####################################################################################################################################
# ------------------------------------- Main Execution Block If File Is Run Directly -------------------------------------------------
# ####################################################################################################################################
if __name__ == "__main__":
    args = test_paths
    exit_code = pytest.main(args)
    sys.exit(exit_code)
