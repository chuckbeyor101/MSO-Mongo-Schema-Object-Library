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

from datetime import datetime
from bson import ObjectId
from decimal import Decimal
from typing import Any, List, Dict

BSON_TYPE_MAP = {
    "string": str,
    "int": int,
    "bool": bool,
    "double": float,
    "date": datetime,
    "objectId": ObjectId,
    "binData": bytes,
    "decimal": Decimal,
    "long": int,
    "timestamp": datetime,
    "null": type(None),
    "object": dict,
    "array": list,
}

class MongoModel:
    _schema = {}
    _collection_name = ""
    _db_name = ""
    _db = None

    timestamps_enabled = True  # Class-level option to enable or disable timestamps

    def _validate_field_type(self, name, value):
        if name.startswith("_"):
            return

        schema_props = self._schema.get("properties", {})
        field_schema = schema_props.get(name, {})
        bson_type = field_schema.get("bsonType") or field_schema.get("type")

        if not bson_type or value is None:
            return

        # Handle multi-type fields (e.g., ["null", "object"])
        if isinstance(bson_type, list):
            expected_types = [BSON_TYPE_MAP.get(t, object) for t in bson_type if t in BSON_TYPE_MAP]
        else:
            expected_types = [BSON_TYPE_MAP.get(bson_type, object)]

        # 👇 Special handling for dynamically generated object/array classes
        if bson_type == "object":
            nested_class = getattr(self.__class__, f"__class_for__{name}", None)
            if nested_class and isinstance(value, nested_class):
                return

        if bson_type == "array":
            if isinstance(value, list):
                item_class = getattr(self.__class__, f"{name}_item", None)
                if item_class and all(isinstance(v, item_class) or not isinstance(v, dict) for v in value):
                    return

        if not any(isinstance(value, t) for t in expected_types):
            raise TypeError(
                f"Invalid type for field '{name}': expected {expected_types}, got {type(value).__name__}"
            )

    def __init__(self, **kwargs):
        self._data = {}
        self._parent = None
        self._parent_key = None

        self._db = getattr(self.__class__, "__db__", None)
        self._collection_name = getattr(self.__class__, "__collection__", None)

        for key, value in kwargs.items():
            setattr(self, key, value)

    def __getattr__(self, name):
        if name in self._data:
            val = self._data[name]
            if isinstance(val, MongoModel):
                val._parent = self
                val._parent_key = name
            return val

        nested_class = getattr(self.__class__, name, None)

        if isinstance(nested_class, type) and issubclass(nested_class, MongoModel):
            instance = nested_class()
            instance._parent = self
            instance._parent_key = name
            self._data[name] = instance
            return instance

        raise AttributeError(f"{self.__class__.__name__} has no attribute '{name}'")

    def __setattr__(self, name, value):
        if name in {
            "_schema", "_collection_name", "_db_name", "_db",
            "_data", "_parent", "_parent_key"
        }:
            super().__setattr__(name, value)
            return

        value = self._deserialize_field(name, value)
        self._validate_field_type(name, value)

        if isinstance(value, MongoModel):
            value._parent = self
            value._parent_key = name
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, MongoModel):
                    item._parent = self
                    item._parent_key = name

        self._data[name] = value
        self._mark_dirty()

    def _mark_dirty(self):
        if hasattr(self, "_parent") and self._parent and hasattr(self, "_parent_key"):
            self._parent._data[self._parent_key] = self
            self._parent._mark_dirty()

    def _deserialize_field(self, name, value):
        schema_props = self._schema.get("properties", {})
        field_schema = schema_props.get(name, {})
        bson_type = field_schema.get("bsonType") or field_schema.get("type")

        if isinstance(bson_type, list):
            bson_type = next((t for t in bson_type if t != "null"), None)

        if bson_type == "object":
            nested_class = getattr(self.__class__, f"__class_for__{name}", None)
            if nested_class and isinstance(value, dict):
                return nested_class(**value)

        if bson_type == "array" and "items" in field_schema:
            item_schema = field_schema["items"]
            item_bson_type = item_schema.get("bsonType") or item_schema.get("type")
            if isinstance(item_bson_type, list):
                item_bson_type = next((t for t in item_bson_type if t != "null"), None)

            item_class = getattr(self.__class__, f"{name}_item", None)
            if item_bson_type == "object" and item_class and isinstance(value, list):
                return [item_class(**v) if isinstance(v, dict) else v for v in value]

        return value

    def to_dict(self):
        return self._serialize_data()

    def _serialize_data(self):
        result = {}
        for k, v in self._data.items():
            if isinstance(v, MongoModel):
                result[k] = v.to_dict()
            elif isinstance(v, list):
                result[k] = [i.to_dict() if isinstance(i, MongoModel) else i for i in v]
            else:
                result[k] = v
        return result

    def save(self):
        if self.timestamps_enabled:
            self.last_modified = datetime.utcnow()
            if not hasattr(self, 'created_at'):
                self.created_at = self.last_modified



        # Call the actual save method (e.g., insert or update)
        if hasattr(self, '_id'):  # If document already has _id, it's an update
            self._get_collection().replace_one({"_id": self._id}, self.to_dict())
        else:
            self._get_collection().insert_one(self.to_dict())

        return self

    def refresh(self):
        doc = self._db[self._collection_name].find_one({"_id": self._data["_id"]})
        if doc:
            self._data = doc

    def clone(self):
        original = self._get_collection().find_one({"_id": self._id})
        if original:
            del original["_id"]  # Remove the _id to insert as a new document
            return self.from_dict(original)
        raise ValueError(f"No document found with _id {str(self._id)}")

    def soft_delete(self):
        """Soft delete this document by setting 'is_deleted' to True."""
        result = self._get_collection().update_one(
            {"_id": self._id},
            {"$set": {"is_deleted": True}}
        )
        return result

    def restore_deleted(self):
        """Restore this soft-deleted document by setting 'is_deleted' to False."""
        result = self._get_collection().update_one(
            {"_id": self._id},
            {"$set": {"is_deleted": False}}
        )
        return result

    def delete(self):
        self._db[self._collection_name].delete_one({"_id": self._data["_id"]})

    def __repr__(self):
        return f"{self.__class__.__name__}({self._data})"

    def __dir__(self):
        return sorted(set(super().__dir__()) | set(self._data.keys()))

    @classmethod
    def from_dict(cls, data: dict):
        instance = cls()
        for key, value in data.items():
            setattr(instance, key, value)
        return instance

    @classmethod
    def find_one(cls, filter: dict) -> Any:
        """Find one document by filter."""
        doc = cls._get_collection().find_one(filter)
        if doc:
            return cls.from_dict(doc)
        return None

    @classmethod
    def find_many(cls, filter: dict = None, sort=None, limit=0) -> List[Any]:
        """Find multiple documents by filter, supporting optional sort and limit."""
        cursor = cls._get_collection().find(filter or {})
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        return [cls.from_dict(doc) for doc in cursor]

    @classmethod
    def find_by_id(cls, _id):
        return cls._get_collection().find_one({"_id": _id})

    @classmethod
    def delete_one(cls, filter: dict):
        return cls._get_collection().delete_one(filter)

    @classmethod
    def delete_many(cls, filter: dict):
        return cls._get_collection().delete_many(filter)

    @classmethod
    def update_one(cls, filter: dict, update: dict, upsert: bool = False):
        return cls._get_collection().update_one(filter, update, upsert=upsert)

    @classmethod
    def update_many(cls, filter: dict, update: dict, upsert: bool = False):
        return cls._get_collection().update_many(filter, update, upsert=upsert)

    @classmethod
    def count_documents(cls, filter: dict = None):
        return cls._get_collection().count_documents(filter or {})

    @classmethod
    def exists(cls, filter: dict) -> bool:
        return cls._get_collection().count_documents(filter, limit=1) > 0

    @classmethod
    def ensure_indexes(cls):
        collection = cls._get_collection()
        for field, details in cls._schema.get('properties', {}).items():
            if 'index' in details:
                collection.create_index([(field, 1)])  # Example index creation

    @classmethod
    def distinct_values(cls, field: str):
        return cls._get_collection().distinct(field)

    @classmethod
    def aggregate(cls, pipeline: List[dict]):
        return list(cls._get_collection().aggregate(pipeline))

    @classmethod
    def find_and_modify(cls, filter: dict, update: dict, upsert: bool = False):
        return cls._get_collection().find_one_and_update(filter, update, upsert=upsert)

    @classmethod
    def validate_schema(cls, data: dict):
        for field, value in data.items():
            if field not in cls._schema['properties']:
                raise ValueError(f"Field {field} is not in schema")
            expected_type = cls._schema['properties'][field].get('bsonType')
            if expected_type and not isinstance(value, expected_type):
                raise TypeError(f"Field {field} should be of type {expected_type}")
        return True

    @classmethod
    def bulk_write(cls, operations: List[Dict]):
        return cls._get_collection().bulk_write(operations)

    @classmethod
    def pretty_print_schema(cls):
        import pprint
        pprint.pprint(cls._schema, indent=2)

    @classmethod
    def get_nested_classes(cls):
        result = {}

        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, type) and issubclass(attr, MongoModel):
                result[attr_name] = attr
                result.update(attr.get_nested_classes())

        return result

    @classmethod
    def print_nested_class_tree(cls, prefix="", is_last=True, seen=None, *, show_scalars=True, max_depth=None,
                                color=True, _depth=0):
        if seen is None:
            seen = set()

        if cls in seen:
            return
        seen.add(cls)

        if max_depth is not None and _depth > max_depth:
            return

        def c(text, color_code):
            if not color:
                return text
            return f"\033[{color_code}m{text}\033[0m"

        def type_label(bson_type):
            type_map = {
                "string": "str", "int": "int", "bool": "bool", "double": "float",
                "objectId": "ObjectId", "date": "datetime", "array": "List",
                "object": "Object", "null": "None", "long": "int"
            }
            if isinstance(bson_type, list):
                return " | ".join([type_map.get(t, t) for t in bson_type])
            return type_map.get(bson_type, bson_type)

        connector = "└── " if is_last else "├── "

        if _depth == 0:
            print(prefix + "└── " + c(cls.__name__, "96"))

        props = cls._schema.get("properties", {})
        children = []

        for field_name, field_schema in props.items():
            bson_type = field_schema.get("bsonType") or field_schema.get("type")
            typename = type_label(bson_type)
            nested_class = None

            if bson_type == "object":
                nested_class = getattr(cls, f"__class_for__{field_name}", None)
            elif bson_type == "array":
                nested_class = getattr(cls, f"{field_name}_item", None)
                if nested_class:
                    typename = f"List[{field_name}_item]"
                else:
                    typename = "List"

            if nested_class:
                children.append((field_name, typename, nested_class))
            elif show_scalars:
                children.append((field_name, typename, None))  # scalar

        for i, (field_name, typename, nested_cls) in enumerate(children):
            last = (i == len(children) - 1)
            child_prefix = prefix + ("    " if is_last else "│   ")
            connector = "└── " if last else "├── "
            print(f"{child_prefix}{connector}{c(field_name, '93')}: {c(typename, '92')}")
            if nested_cls:
                nested_cls.print_nested_class_tree(
                    prefix=child_prefix,
                    is_last=last,
                    seen=seen,
                    show_scalars=show_scalars,
                    max_depth=max_depth,
                    color=color,
                    _depth=_depth + 1
                )
