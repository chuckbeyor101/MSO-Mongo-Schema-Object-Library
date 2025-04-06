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
    ├── gender: None
    ├── addresses: List[addresses_item]
    │   ├── type: None
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

# Convert to and from dictionary
```python
person_dict = person.to_dict()
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