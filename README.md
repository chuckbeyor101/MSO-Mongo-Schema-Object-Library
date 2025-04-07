# MSO (Mongo Schema Object Library)

**MSO** is a lightweight **Object-Document Mapper (ODM)** for **MongoDB** that allows Python developers to interact with MongoDB collections in an intuitive and Pythonic way. It offers the flexibility of a schema-less database with the convenience of strongly-typed classes, enabling seamless operations on MongoDB collections using familiar Python patterns.

---

## 🚀 Key Features:

- **Dynamic Model Generation**: Automatically generates Python classes from your MongoDB collection’s `$jsonSchema`.
- **Pythonic API**: Use common patterns like `save()`, `find_one()`, `update_one()`, etc.
- **Deeply Nested Models**: Supports arbitrarily nested schemas, including arrays of objects.
- **Auto-validation**: Ensures types, enums, and structure match your schema.
- **Recursive Object Serialization**: Works out-of-the-box with nested documents and arrays.
- **Developer Tools**: Includes tree views, schema printers, and class introspection.

---

## 📦 Requirements

- Python 3.12+
- MongoDB with `$jsonSchema` validation on your collections

---

## 🔧 Installation

```bash
pip install --upgrade git+https://github.com/chuckbeyor101/MSO-Mongo-Schema-Object-Library.git
```

# 🛠️ Basic Usage
In this basic example we have already created a $jsonSchema validator for the "People" collection in MongoDB. We create a new person, update some information and save the person MongoDB.

```python
from pymongo import MongoClient
from MSO.generator import get_model

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client["mydb"]

# Generate a model based on the "people" collection's schema
People = get_model(db, "people")

# Create a new person
person = People(name="Tony Pajama", age=34)

# Add nested data
person.health.primary_physician.name = "Dr. Strange"
person.address.add(type="home", street="123 Elm", city="NY", state="NY", zip="10001")

# Save to the database
person.save()
```

# 🧪 Want to Explore?
```python
People.print_nested_class_tree()
```
#### Output
```bash
Tree View:
└── people
    ├── name: str
    ├── age: int
    ├── email: str
    ├── gender: enum [Male, Female, Other]
    ├── addresses: List[addresses_item]
    │   ├── type: enum [Home, Business, Other]
    │   ├── street: str
    │   ├── city: str
    │   ├── state: str
    │   └── zip: str
    └── health: Object
        ├── medical_history: Object
        │   ├── conditions: List[conditions_item]
        │   │   ├── name: str
        │   │   ├── diagnosed: str
        │   │   └── medications: List[medications_item]
        │   │       ├── name: str
        │   │       ├── dose: str
        │   │       └── frequency: str
        │   └── allergies: List
        └── primary_physician: Object
            ├── name: str
            └── contact: Object
                ├── phone: str
                └── address: Object
                    ├── street: str
                    ├── city: str
                    ├── state: str
                    └── zip: str
```

# 🔍 Querying the Database
```python
# Find one
person = People.find_one({"name": "Tony Pajama"})

# Find many
person_list = People.find_many(sort=[("created_at", -1)], limit=10)
```

# Document Manipulation
```python
# Delete
person.delete()

# Clone
new_person = person.clone()
```

# 🔍 Document Comparison
MSO makes it easy to compare two MongoDB documents—either as model instances or dictionaries—using the powerful Model.diff() method. It supports:

- Deep recursive comparison of nested objects and arrays
- Detection of value and type changes
- Flat or nested output formatting
- Optional strict mode (type-sensitive)
- Filtering for specific fields or changes

### Basic Example
```python
from MSO.generator import get_model
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["mydb"]
People = get_model(db, "people")

# Create a valid model instance
person1 = People(name="Alice", age=30, gender="Female")

# Use a dictionary with type mismatch (age as string)
person2 = {
    "name": "Alice",
    "age": "30",  # string instead of int
    "gender": "Female"
}

diff = People.diff(person1, person2, strict=True)

from pprint import pprint
pprint(diff)
```
### Example Output
```bash
{
  'age': {
    'old': 30,
    'new': '30',
    'type_changed': True
  }
}
```

# Convert to and from dictionary
```python
person_dict = person.to_dict()
```

# ⏱ Automatic Timestamps
By default, models automatically include created_at and updated_at fields to track when a document is created or modified. These are managed internally and do not need to be defined in your schema.

### 🔧 How it works
created_at is set once, when the document is first saved.

updated_at is updated every time the document is modified and saved.

Both are stored as UTC datetime.datetime objects.

### 🚫 Disabling timestamps
Timestamps are enabled by default. To disable them, set the `timestamps` parameter to `False` when creating a model.

```python
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
```




# 🧩 Lifecycle Hooks
You can use decorators like @pre_save, @post_save, @pre_delete, and @post_delete to hook into model lifecycle events. This is useful for setting defaults, cleaning up, triggering logs, or validating conditions.
### Example: Automatically output a message when a document is saved
```python
from MSO.base_model import MongoModel, pre_save, post_save
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["mydb"]

# Define the model hooks you would like to use
class People(MongoModel):
    @post_save # This method will be called after the document is saved
    def confirm_save(self):
        print(f"[+] Document saved: {self.name}")

        
People = get_model(db, "people")

person = People(name="Jane Doe")
person.save()

# Output:
# [+] Document saved: Jane Doe
```

# LICENSE & COPYWRIGHT WARNING
MSO Copyright (c) 2025 by Charles L Beyor                                                                           
is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International.                          
To view a copy of this license, visit https://creativecommons.org/licenses/by-nc-sa/4.0/                            
                                                                                                                     
Unless required by applicable law or agreed to in writing, software                                                 
distributed under the License is distributed on an **"AS IS" BASIS,                                                   
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND**, either express or implied.

See the License for the specific language governing permissions and limitations under the License.                                                                           
                                                                                                              
Gitlab: https://github.com/chuckbeyor101/MSO-Mongo-Schema-Object-Library.git   

# 