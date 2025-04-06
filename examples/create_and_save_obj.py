# ######################################################################################################################
#  MSO Copyright (c) 2025 by Charles L Beyor                                                                           #
#  is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International.                          #
#  To view a copy of this license, visit https://creativecommons.org/licenses/by-nc-sa/4.0/                            #
#                                                                                                                      #
#  Unless required by applicable law or agreed to in writing, software                                                 #
#  distributed under the License is distributed on an "AS IS" BASIS,                                                   #
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.                                            #
#  See the License for the specific language governing permissions and                                                 #
#  limitations under the License.                                                                                      #
#                                                                                                                      #
#  Gitlab: https://github.com/chuckbeyor101/MSO-Mongo-Schema-Object-Library-                                           #
# ######################################################################################################################

import os
from pymongo import MongoClient
from MSO.generator import get_model

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "mydb")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

# Get the model for the "people" collection
People = get_model(db, "people")

new_person = People(name="Tony Pajama", age=34)
new_person.health.primary_physician.name = "Dr. Strange"

# Save to MongoDB
new_person.save()
print("Saved person:")
print(new_person)

# Modify and resave
new_person.health.primary_physician.contact.phone = "123-456-7890"

# add an address using add()
new_person.addresses.add(type="work",street="789 Oak St",city="Panama",state="NJ",zip="14862")

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
address1 = People.addresses_item(type="home",city="Panama",state="NJ",zip="14862")
new_person.addresses.append(address1)

# Modify medication by index reference
new_person.health.medical_history.conditions[0].medications[0].dose = "1000mg"


print()
print("Serialized before save:", new_person.to_dict())

new_person.save()
print("\nResaved with updates:")
print(new_person)