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

from mso.base_model import MongoModel
from mso.schema_loader import load_schema
from mso.mongo_helpers import MongoHelpersMixin
from typing import Optional, Any

def normalize_bson_type(bson_type):
    if isinstance(bson_type, list):
        for t in bson_type:
            if t != 'null':
                return t
    return bson_type

def normalize_class_name(name):
    return name.replace(' ', '_').replace('-', '_')

def generate_nested_class(name, schema, class_map):
    class_attrs = {
        '_schema': schema
    }
    annotations = {}

    properties = schema.get('properties', {})
    for prop, details in properties.items():
        bson_type = normalize_bson_type(details.get('bsonType', ''))

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

        elif bson_type == 'array':

            item_def = details.get('items', {})

            item_type = normalize_bson_type(item_def.get('bsonType', ''))

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

def create_readonly_model(collection_name, db):
    def wrap(value):
        if isinstance(value, dict):
            return ReadOnlyDocument(value)
        elif isinstance(value, list):
            return [wrap(v) for v in value]
        else:
            return value

    class ReadOnlyDocument:
        def __init__(self, data):
            self._data = {k: wrap(v) for k, v in data.items()}

        def __getattr__(self, item):
            try:
                return self._data[item]
            except KeyError:
                raise AttributeError(f"No such attribute: {item}")

        def __getitem__(self, item):
            return self._data[item]

        def __setattr__(self, key, value):
            if key == "_data":
                super().__setattr__(key, value)
            else:
                self._data[key] = wrap(value)

        def __repr__(self):
            return f"<ReadOnlyDocument {self._data}>"

        def to_dict(self):
            def unwrap(value):
                if isinstance(value, ReadOnlyDocument):
                    return {k: unwrap(v) for k, v in value._data.items()}
                elif isinstance(value, list):
                    return [unwrap(v) for v in value]
                else:
                    return value
            return unwrap(self)

        def save(self):
            raise TypeError(f"Cannot save document from read-only view '{collection_name}'.")

        def delete(self):
            raise TypeError(f"Cannot delete document from read-only view '{collection_name}'.")

    class ReadOnlyModel:
        __collection__ = collection_name
        __db__ = db
        _collection = db[collection_name]
        __is_view__ = True

        @classmethod
        def find(cls, *args, **kwargs):
            return (ReadOnlyDocument(doc) for doc in cls._collection.find(*args, **kwargs))

        @classmethod
        def find_one(cls, *args, **kwargs):
            doc = cls._collection.find_one(*args, **kwargs)
            return ReadOnlyDocument(doc) if doc else None

        @classmethod
        def find_many(cls, *args, **kwargs):
            return list(cls.find(*args, **kwargs))

        @classmethod
        def aggregate(cls, pipeline, *args, **kwargs):
            return (ReadOnlyDocument(doc) for doc in cls._collection.aggregate(pipeline, *args, **kwargs))

        @classmethod
        def count_documents(cls, *args, **kwargs):
            return cls._collection.count_documents(*args, **kwargs)

        @classmethod
        def get(cls, _id):
            return cls.find_one({"_id": _id})

        @classmethod
        def all(cls, *args, **kwargs):
            return list(cls.find(*args, **kwargs))

        def __init__(self, *args, **kwargs):
            raise TypeError(f"'{collection_name}' is a view and cannot be instantiated.")

    ReadOnlyModel.__name__ = normalize_class_name(collection_name)
    return ReadOnlyModel



def get_model(db, collection_name):
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
        name=normalize_class_name(collection_name),
        schema=schema,
        class_map=class_map
    )

    model_name = normalize_class_name(collection_name)

    FinalModel = type(model_name, (model_class, MongoHelpersMixin), {
        "__collection__": collection_name,
        "__db__": db
    })

    # Attach nested classes from model_class
    for attr, val in model_class.__dict__.items():
        if attr.startswith("__class_for__") or attr.endswith("_item"):
            setattr(FinalModel, attr, val)

    return FinalModel
