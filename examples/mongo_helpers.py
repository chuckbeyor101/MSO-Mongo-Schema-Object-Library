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

import os
from pymongo import MongoClient
from mso.generator import get_model

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "mydb")
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

# Get the model for the collection
People = get_model(db, "people")

# Querying documents
print("Querying documents...")
for doc in People.query({"name": "Person 1"}, sort=[("age", 1)], limit=5):
    print("-", doc.name)

# Count
print("Counting People:")
print("Total:", People.count())

# Distinct
print("Distinct Names:")
distinct_names = People.distinct("name")
print(distinct_names)

# Aggregation
print("Aggregating People By Name:")
pipeline = [
    {"$group": {"_id": "$name", "total": {"$sum": 1}}},
    {"$sort": {"total": -1}}
]
for doc in People.aggregate(pipeline):
    print(doc)

# Regex Query
print("Regex Match:")
for doc in People.regex_query("name", "^([A-Za-z]+)\sPajama$"):
    print("-", doc.name)

# Text Search (ensure you have a text index on the "name" field)
# Requires text search field
# print("Text Search:")
# for doc in People.text_search("Person 50"):
#     print("-", doc.name)

# Update One
print("Update One:")
People.update_one({"name": "Person 1"}, {"$set": {"name": "Person 100"}})

# Update Many
print("Update Many:")
People.update_many({"age": 25}, {"$set": {"age": 26}})

# Paginate
print("Paginate Results:")
for doc in People.paginate({"age": {"$gte": 30}}, page=2, page_size=5):
    print(doc.name)

# Check Existence
print("Check if Person Exists:")
exists = People.exists({"name": "Person 1"})
print("Exists:", exists)

# Get One
print("Get One Person:")
person = People.get_one({"name": "Person 1"})
if person:
    print(person.name)
else:
    print("Person not found")

# Bulk Save
print("Bulk Save:")
people_to_save = [
    People(name="Tony", age=30),
    People(name="Anna", age=25),
]
People.bulk_save(people_to_save)

# Delete By ID
print("Delete By ID:")
People.delete_by_id(person._id)

# Delete Many
print("Delete Many People:")
People.delete_many({"age": 26})

# Clone Document
print("Cloning a Document:")
clone_person = People.clone(person._id)
print("Cloned:", clone_person.name)

# Update from Dict
print("Update Document from Dictionary:")
People.update_from_dict({"name": "Person 100"}, {"age": 27})

# Find and Modify Document
print("Find and Modify Document:")
updated_person = People.find_and_modify({"name": "Person 100"}, {"$set": {"name": "Person 101"}})
print("Updated Person:", updated_person)

# Soft Delete
print("Soft Deleting Person:")
People.soft_delete({"name": "Person 100"})

# Restore Soft Deleted Person
print("Restoring Soft Deleted Person:")
People.restore_deleted({"name": "Person 100"})
