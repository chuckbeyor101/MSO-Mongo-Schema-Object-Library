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
PeopleSummaryView = get_model(db, "people_summary_view")

# Querying documents
person = PeopleSummaryView.find_one({"name": "Tony Pajama Sr"})

# Querying documents
people = PeopleSummaryView.find_many({"name": "Tony Pajama Sr"})

# Manipulate values locally
person.name = "Tony Pajama Updated"

# Print the updated person object
print(f"Updated Person: {person.name}, Age: {person.age}")
# Print Nested Field
print(f"Nested Field - Primary Physician: {person.health.primary_physician.name}")

# This should fail since the view is read-only
try:
    person.save()
except Exception as e:
    print(f"Error saving person: {e}")

for p in people:
    print(f"Person: {p.name}, Age: {p.age}")
    print(f"Nested Field - Primary Physician: {p.health.primary_physician.name}")
    # for each address in p.addresses
    for address in p.addresses:
        print(f"Address: {address.street}")

pass