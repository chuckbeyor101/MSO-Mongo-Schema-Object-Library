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
from datetime import datetime
from mso.base_model import MongoModel
from mso.schema_loader import load_schema
from mso.mongo_helpers import MongoHelpersMixin
from mso.read_only_model import create_readonly_model
from typing import Optional, Any
from mso import utils


def generate_nested_class(name, schema, class_map):
    """
        Recursively generates a nested Python class based on a MongoDB $jsonSchema object definition.

        Each generated class inherits from `MongoModel` and is stored in the provided `class_map`
        using the generated class name as the key. The result is a full class hierarchy that allows
        attribute-style access to deeply nested MongoDB documents.

        Args:
            name (str): The name to use for the generated class (typically based on the field path).
            schema (dict): The MongoDB $jsonSchema definition for the object.
            class_map (dict): A dictionary to collect all generated classes by name.

        Returns:
            Type[MongoModel]: The dynamically generated class corresponding to the input schema.
        """
    class_attrs = {
        '_schema': schema
    }
    annotations = {}

    properties = schema.get('properties', {})
    for prop, details in properties.items():
        # Determine the first non-null bsonType in the bsonType list for this field
        bson_type = utils.get_primary_bson_type(details.get('bsonType', ''))

        # For nested objects, generate a new class and create a property that returns an instance of that class
        if bson_type == 'object':
            nested_class = generate_nested_class(f"{name}_{prop}", details, class_map)

            def _make_instance(self, cls=nested_class, key=prop):
                if key in self._data and isinstance(self._data[key], MongoModel):
                    return self._data[key]

                instance = cls()
                instance._parent = self
                instance._parent_key = key
                self._data[key] = instance
                return instance

            class_attrs[prop] = property(_make_instance)
            class_attrs[f"__class_for__{prop}"] = nested_class
            annotations[prop] = Optional[nested_class]

        # For arrays, we need to handle the type for the items in the array
        elif bson_type == 'array':

            item_def = details.get('items', {})

            # Determine the first non-null bsonType in the bsonType list for this field
            item_type = utils.get_primary_bson_type(item_def.get('bsonType', ''))

            # If the item type is an object, generate a nested class for it
            if item_type == 'object':
                nested_class = generate_nested_class(f"{name}_{prop}_item", item_def, class_map)

                # Attach item class to parent class so it can be used for construction
                class_attrs[f"{prop}_item"] = nested_class

            annotations[prop] = Optional[list]


        else:
            annotations[prop] = Optional[Any]

    class_attrs['__annotations__'] = annotations
    class_attrs.setdefault("__init__", MongoModel.__init__)  # ✅ Ensure instance fields like _data get set
    if "__init__" not in class_attrs:
        class_attrs["__init__"] = MongoModel.__init__
    new_class = type(name, (MongoModel,), class_attrs)
    class_map[name] = new_class
    return new_class


def get_model(db, collection_name):
    """
    Dynamically generates a Python class model for a MongoDB collection using its $jsonSchema validator.

    This function connects to the specified MongoDB collection, detects whether it is a view or a regular
    collection, and constructs a dynamic Python class based on its schema. For views, a read-only model
    is returned. For regular collections with schema validation, the schema is parsed and a full class
    hierarchy is generated using nested Python classes that mirror the schema structure.

    Args:
        db (pymongo.database.Database): The MongoDB database object.
        collection_name (str): The name of the collection to model.

    Returns:
        Type[MongoModel]: A dynamically generated class representing the MongoDB collection,
                          including any nested subdocuments.
    """

    # Fetch collection info to detect if it's a view
    info = db.command("listCollections", filter={"name": collection_name})
    collection_info = info["cursor"]["firstBatch"][0]
    is_view = collection_info.get("type") == "view"

    if is_view:
        return create_readonly_model(collection_name, db)

    # Otherwise, proceed as a regular collection with $jsonSchema
    schema = load_schema(db, collection_name)
    class_map = {}

    model_class = generate_nested_class(
        name=utils.normalize_class_name(collection_name),
        schema=schema,
        class_map=class_map
    )

    model_name = utils.normalize_class_name(collection_name)

    FinalModel = type(model_name, (model_class, MongoHelpersMixin), {
        "__collection__": collection_name,
        "__db__": db
    })

    # Attach nested classes from model_class
    for attr, val in model_class.__dict__.items():
        if attr.startswith("__class_for__") or attr.endswith("_item"):
            setattr(FinalModel, attr, val)

    return FinalModel
