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
#  Gitlab: https://github.com/chuckbeyor101/MSO-Mongo-Schema-Object-Library                                            #
# ######################################################################################################################

import os
from time import sleep
from pymongo import MongoClient
from MSO.generator import get_model

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "mydb")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

# Get the model for the collection
People = get_model(db, "people")


# Disable timestamps for a specific model or instance
People.timestamps_enabled = False

# Create a new person
new_person = People(name="Tony Pajama Timestamp", age=34)

# Save without modifying timestamps
new_person.save()

# Enable timestamps back again
People.timestamps_enabled = True

# save with timestamps
new_person.save()
print(f"Person saved with timestamps- Created At: {new_person.created_at}, Last Modified: {new_person.last_modified}")

sleep(2)

# Save the person again to update the timestamps
new_person.save()
print(f"Person saved again with timestamps- Created At: {new_person.created_at}, Last Modified: {new_person.last_modified}")
