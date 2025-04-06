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
from pprint import pprint

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "mydb")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

# Get the model for the collection
People = get_model(db, "people")

person = People()
person.name="Tony Pajama"
person.addresses.add(type="Home", street="123 Main St", city="Panama", state="NJ", zip="14862")

# This should fail because age is a string, not int.
person.age="34"

# This should fail because Rabbit is not an allowed enum value for this field
person.gender = "Rabbit"

# this should fail because address type cant be Vacation
person.addresses[0].type = "Vacation"

pass
