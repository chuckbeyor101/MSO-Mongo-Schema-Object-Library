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
from pymongo import MongoClient
from MSO.generator import get_model
from pprint import pprint

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "mydb")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

# Get the model for the "people" collection
People = get_model(db, "people")

# Valid object
person1 = People(name="Alice", age=30, gender="Female")

# Intentionally use a dict with an invalid field (age as str)
person2_data = {
    "name": "Alice",
    "age": 50,  # wrong type
    "gender": "Female"
}

# Automatically handled by diff (no validation exception will occur)
diff_result = People.diff(person1, person2_data, strict=True)

from pprint import pprint
pprint(diff_result)