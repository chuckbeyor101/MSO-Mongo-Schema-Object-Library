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
from bson import ObjectId
from decimal import Decimal
from typing import Any, List, Dict
import pandas as pd
import json
from collections import Counter, defaultdict

# ----------------------------------------------------------------------------------
# BSON Type Mapping (used to validate types from MongoDB schema)
# ----------------------------------------------------------------------------------
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
# ----------------------------------------------------------------------------------
# ListFieldWrapper - A custom list wrapper for MongoDB array fields
# ----------------------------------------------------------------------------------
class ListFieldWrapper(list):
    """
    Custom list wrapper that adds:
    - .add(**kwargs) to create and append a nested item
    - .remove_by(**criteria) to remove items matching criteria
    - .remove_all_by(**criteria) to remove all matching items
    - .remove_at(index) to remove an item at a specific index
    - .move(old_index, new_index) to move an item within the list
    - .swap(index1, index2) to swap two items in the list
    """
    def __init__(self, parent, field_name, item_class, initial=None):
        super().__init__(initial or [])
        self._parent = parent
        self._field_name = field_name
        self._item_class = item_class

    def add(self, *args, **kwargs):
        """
        Add one or more items to the list.

        Supports:
            - .add(key1=value1, key2=value2)                    ← single item with kwargs
            - .add(dict1)                                       ← one item as a dict
            - .add(dict1, dict2)                                ← multiple items
            - .add(*[dict1, dict2])                             ← list of dicts
            - .add(instance)                                    ← instance of _item_class
            - .add(instance1, dict2, instance3)                 ← mix of types
        """
        new_items = []

        # Case: single item via kwargs
        if kwargs:
            item = self._item_class(**kwargs)
            new_items.append(item)

        # Case: one or more positional args
        for arg in args:
            if isinstance(arg, self._item_class):
                new_items.append(arg)
            elif isinstance(arg, dict):
                new_items.append(self._item_class(**arg))
            elif isinstance(arg, list):
                for sub in arg:
                    if isinstance(sub, self._item_class):
                        new_items.append(sub)
                    elif isinstance(sub, dict):
                        new_items.append(self._item_class(**sub))
                    else:
                        raise TypeError(f"Unsupported type in list: {type(sub)}")
            else:
                raise TypeError(f"Unsupported argument type: {type(arg)}")

        # Attach parent context and add to list
        for item in new_items:
            item._parent = self._parent
            item._parent_key = self._field_name
            self.append(item)

        return new_items[0] if len(new_items) == 1 else new_items

    def remove_by(self, **criteria):
        """
        Remove the first matching item from the list based on given criteria.

        Returns:
            bool: True if an item was removed, False otherwise.
        """
        for item in self:
            if isinstance(item, MongoModel):
                if all(getattr(item, k, None) == v for k, v in criteria.items()):
                    self.remove(item)
                    return True
            elif isinstance(item, dict):
                if all(item.get(k) == v for k, v in criteria.items()):
                    self.remove(item)
                    return True
        return False

    def remove_all_by(self, **criteria):
        """
        Remove all items from the list that match the given criteria.

        Returns:
            int: Number of items removed.
        """
        to_remove = []
        for item in self:
            if isinstance(item, MongoModel):
                if all(getattr(item, k, None) == v for k, v in criteria.items()):
                    to_remove.append(item)
            elif isinstance(item, dict):
                if all(item.get(k) == v for k, v in criteria.items()):
                    to_remove.append(item)

        for item in to_remove:
            self.remove(item)

        return len(to_remove)

    def remove_at(self, index: int):
        """
        Remove the item at the specified index from the list.

        Args:
            index (int): The position of the item to remove.

        Raises:
            IndexError: If the index is out of range.
        """
        if index < 0 or index >= len(self):
            raise IndexError(f"Index {index} out of range for field '{self._field_name}'")
        del self[index]

    def move(self, old_index: int, new_index: int):
        """
        Move an item from old_index to new_index within the array.

        Args:
            old_index (int): The current index of the item to move.
            new_index (int): The new index to move the item to.
        """
        if not (0 <= old_index < len(self)):
            raise IndexError(f"old_index {old_index} out of range for list of length {len(self)}")
        if not (0 <= new_index <= len(self)):
            raise IndexError(f"new_index {new_index} out of range for list of length {len(self)}")

        item = self.pop(old_index)
        self.insert(new_index, item)

        # Mark parent object as dirty so it knows to persist the change
        if hasattr(self._parent, "_mark_dirty"):
            self._parent._mark_dirty()

    def swap(self, index1: int, index2: int):
        """
        Swap two items at the given indices in the list.

        Args:
            index1 (int): First index to swap.
            index2 (int): Second index to swap.
        """
        if not (0 <= index1 < len(self)) or not (0 <= index2 < len(self)):
            raise IndexError(f"swap indices out of range for list of length {len(self)}")

        self[index1], self[index2] = self[index2], self[index1]

        # Mark parent object as dirty to reflect changes
        if hasattr(self._parent, "_mark_dirty"):
            self._parent._mark_dirty()

    def to_serializable(self):
        return [item.to_dict() if isinstance(item, MongoModel) else item for item in self]



# ----------------------------------------------------------------------------------
# MongoModel - A dynamic schema-driven base model for MongoDB documents
# ----------------------------------------------------------------------------------
class MongoModel:
    """
    Base class for dynamically generated MongoDB schema-driven models.
    Automatically handles type validation, nested object/array instantiation,
    MongoDB persistence (CRUD), and schema introspection.
    """

    _schema = {}  # JSON schema for the model
    _collection_name = ""  # MongoDB collection name
    _db_name = ""  # MongoDB database name (unused, optional)
    _db = None  # Reference to the active MongoDB client DB object
    timestamps_enabled = True  # Toggle automatic management of created_at/last_modified timestamps


    # ----------------------------------------------------------------------------------
    # Lifecycle Hooks
    # ----------------------------------------------------------------------------------
    _pre_save_hooks = []
    _post_save_hooks = []
    _pre_delete_hooks = []
    _post_delete_hooks = []

    def _run_hooks(self, hook_list):
        for hook in hook_list:
            hook(self)

    # ----------------------------------------------------------------------------------
    # Validate a value against its schema-defined BSON type
    # ----------------------------------------------------------------------------------
    def _validate_field_type(self, name, value):
        """
        Validates the given field's value using the class schema.
        Handles type checking, enum constraints, and array validation.
        """
        if name.startswith("_"):
            return

        schema_props = self._schema.get("properties", {})
        field_schema = schema_props.get(name, {})
        bson_type = field_schema.get("bsonType") or field_schema.get("type")
        enum_values = field_schema.get("enum")

        # ----------------------------
        # ENUM VALIDATION (always check)
        # ----------------------------
        if enum_values is not None and value is not None:
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if item not in enum_values:
                        raise ValueError(
                            f"Invalid value '{item}' in array field '{name}[{i}]'; expected one of {enum_values}"
                        )
            else:
                if value not in enum_values:
                    raise ValueError(
                        f"Invalid value '{value}' for field '{name}'; expected one of {enum_values}"
                    )

        # If no bsonType defined, skip type checking (but we already did enum checking)
        if not bson_type or value is None:
            return

        # ----------------------------
        # MULTI-TYPE SUPPORT
        # ----------------------------
        if isinstance(bson_type, list):
            expected_types = [BSON_TYPE_MAP.get(t, object) for t in bson_type if t in BSON_TYPE_MAP]
        else:
            expected_types = [BSON_TYPE_MAP.get(bson_type, object)]

        # ----------------------------
        # OBJECT VALIDATION
        # ----------------------------
        if bson_type == "object":
            nested_class = getattr(self.__class__, f"__class_for__{name}", None)
            if nested_class and isinstance(value, nested_class):
                return

        # ----------------------------
        # ARRAY VALIDATION
        # ----------------------------
        if bson_type == "array":
            if not isinstance(value, list):
                raise TypeError(f"Expected list for field '{name}', got {type(value).__name__}")

            item_schema = field_schema.get("items", {})
            item_enum = item_schema.get("enum")
            item_type = item_schema.get("bsonType") or item_schema.get("type")
            item_class = getattr(self.__class__, f"{name}_item", None)

            for i, item in enumerate(value):
                # ENUM VALIDATION (scalars)
                if item_enum and not isinstance(item, (dict, MongoModel)):
                    if item not in item_enum:
                        raise ValueError(
                            f"Invalid value '{item}' in array field '{name}[{i}]'; expected one of {item_enum}"
                        )

                # OBJECT VALIDATION
                if item_class and isinstance(item, item_class):
                    continue

                # SCALAR VALIDATION
                expected_item_type = BSON_TYPE_MAP.get(item_type, object)
                if not isinstance(item, expected_item_type):
                    raise TypeError(
                        f"Invalid item type in field '{name}[{i}]': expected {expected_item_type}, got {type(item).__name__}"
                    )
            return

        # ----------------------------
        # BASIC SCALAR TYPE CHECK
        # ----------------------------
        if not any(isinstance(value, t) for t in expected_types):
            raise TypeError(
                f"Invalid type for field '{name}': expected {expected_types}, got {type(value).__name__}"
            )

    # ----------------------------------------------------------------------------------
    # Initialize the model
    # ----------------------------------------------------------------------------------
    def __init__(self, **kwargs):
        self._data = {}  # Holds all dynamic field values
        self._parent = None  # Reference to parent object (used for dirty propagation)
        self._parent_key = None  # Field name this object is nested under

        self._db = getattr(self.__class__, "__db__", None)
        self._collection_name = getattr(self.__class__, "__collection__", None)

        for key, value in kwargs.items():
            setattr(self, key, value)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if callable(attr) and hasattr(attr, "_hook_type"):
                hook_type = attr._hook_type
                getattr(cls, f"_{hook_type}_hooks").append(attr)

    # ----------------------------------------------------------------------------------
    # Dynamic getter - supports nested objects and auto-initializes empty arrays
    # ----------------------------------------------------------------------------------
    def __getattr__(self, name):
        if name in self._data:
            val = self._data[name]
            if isinstance(val, MongoModel):
                val._parent = self
                val._parent_key = name
            return val

        # Auto-instantiate nested object
        nested_class = getattr(self.__class__, name, None)
        if isinstance(nested_class, type) and issubclass(nested_class, MongoModel):
            instance = nested_class()
            instance._parent = self
            instance._parent_key = name
            self._data[name] = instance
            return instance

        # Auto-initialize array fields with ListFieldWrapper if supported
        if name in self._schema.get("properties", {}):
            field_schema = self._schema["properties"][name]
            bson_type = field_schema.get("bsonType") or field_schema.get("type")

            if bson_type == "array":
                item_class = getattr(self.__class__, f"{name}_item", None)
                if item_class:
                    wrapper = ListFieldWrapper(self, name, item_class)
                    self._data[name] = wrapper
                    return wrapper
                else:
                    self._data[name] = []
                    return self._data[name]

            # ✅ Return None for scalar fields if not set yet
            self._data[name] = None
            return None

        raise AttributeError(f"{self.__class__.__name__} has no attribute '{name}'")

    # ----------------------------------------------------------------------------------
    # Dynamic setter - validates type and handles dirty propagation
    # ----------------------------------------------------------------------------------
    def __setattr__(self, name, value):
        if name in {
            "_schema", "_collection_name", "_db_name", "_db",
            "_data", "_parent", "_parent_key"
        }:
            super().__setattr__(name, value)
            return

        value = self._deserialize_field(name, value)
        self._validate_field_type(name, value)

        # Track parent context
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

    # ----------------------------------------------------------------------------------
    # Mark the parent as dirty (used when nested fields change)
    # ----------------------------------------------------------------------------------
    def _mark_dirty(self):
        if hasattr(self, "_parent") and self._parent and hasattr(self, "_parent_key"):
            # Only propagate for object fields (not items in an array)
            if isinstance(self._parent._data.get(self._parent_key), list):
                # Don't overwrite list fields
                return
            self._parent._data[self._parent_key] = self
            self._parent._mark_dirty()

    # ----------------------------------------------------------------------------------
    # Serialize / Deserialize nested objects/arrays based on schema
    # ----------------------------------------------------------------------------------
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

    @classmethod
    def from_dict(cls, data: dict):
        """
        Create an instance of this model from a dictionary of field values.

        Args:
            data (dict): A dictionary where keys are field names and values are field data.

        Returns:
            MongoModel: An initialized instance populated with data.
        """
        instance = cls()
        for key, value in data.items():
            setattr(instance, key, value)
        return instance

    @classmethod
    def from_dict_unvalidated(cls, data: dict):
        """
        Unsafe fallback: creates an instance bypassing validation.
        Only used internally for tools like diff().
        """
        instance = cls.__new__(cls)
        instance._data = {}
        instance._parent = None
        instance._parent_key = None
        instance._db = getattr(cls, "__db__", None)
        instance._collection_name = getattr(cls, "__collection__", None)

        for key, value in data.items():
            instance._data[key] = value
        return instance

    def to_dict(self):
        return self._serialize_data()

    def _serialize_data(self):
        result = {}
        for k, v in self._data.items():
            if isinstance(v, MongoModel):
                result[k] = v.to_dict()
            elif isinstance(v, ListFieldWrapper):
                result[k] = v.to_serializable()
            elif isinstance(v, list):
                result[k] = [i.to_dict() if isinstance(i, MongoModel) else i for i in v]
            else:
                result[k] = v
        return result

    # ----------------------------------------------------------------------------------
    # MongoDB Write Operations
    # ----------------------------------------------------------------------------------
    def save(self):
        self._run_hooks(self.__class__._pre_save_hooks)

        if self.timestamps_enabled:
            self.last_modified = datetime.utcnow()
            if not hasattr(self, 'created_at'):
                self.created_at = self.last_modified

        # Call the actual save method (e.g., insert or update)
        if hasattr(self, '_id') and self._id:  # If document already has _id, and its not none, it's an update
            self._get_collection().replace_one({"_id": self._id}, self.to_dict())
        elif hasattr(self, '_id') and not self._id:
            # remove _id to avoid validation error
            del self._data["_id"]
        else:
            self_dict = self.to_dict()
            self._get_collection().insert_one(self_dict)

        self._run_hooks(self.__class__._post_save_hooks)
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
        self._run_hooks(self.__class__._pre_delete_hooks)
        self._db[self._collection_name].delete_one({"_id": self._data["_id"]})
        self._run_hooks(self.__class__._post_delete_hooks)

    # ----------------------------------------------------------------------------------
    # Comparisons
    # ----------------------------------------------------------------------------------
    @classmethod
    def diff(cls, a, b, *, deep=True, strict=False, include_unchanged=False, ignore_fields=None, flat=False):
        """
        Compare two MongoModel instances or dictionaries and return their differences.

        Args:
            a (MongoModel | dict): The first model or dictionary.
            b (MongoModel | dict): The second model or dictionary.
            deep (bool): Recursively compare nested fields. Default is True.
            strict (bool): If True, compare values with strict type checks.
            include_unchanged (bool): If True, include fields that are the same in the diff output.
            ignore_fields (list): List of field names to skip during comparison.
            flat (bool): If True, return diff as a flat dictionary using dot-notation paths.

        Returns:
            dict: A dictionary describing the differences.
        """
        ignore_fields = set(ignore_fields or [])

        # Coerce both objects into MongoModels using from_dict_unvalidated if needed
        if not isinstance(a, cls):
            a = cls.from_dict_unvalidated(a)
        if not isinstance(b, cls):
            b = cls.from_dict_unvalidated(b)

        def _compare(x, y, path=""):
            diffs = {}

            all_keys = set(x._data.keys()) | set(y._data.keys())
            for key in all_keys:
                if key in ignore_fields:
                    continue

                val1 = x._data.get(key)
                val2 = y._data.get(key)
                full_path = f"{path}.{key}" if path else key

                if isinstance(val1, MongoModel) and isinstance(val2, MongoModel) and deep:
                    nested_diff = _compare(val1, val2, full_path)
                    if nested_diff or include_unchanged:
                        diffs.update(nested_diff)
                    continue

                if isinstance(val1, list) and isinstance(val2, list) and deep:
                    max_len = max(len(val1), len(val2))
                    for i in range(max_len):
                        item_path = f"{full_path}[{i}]"
                        try:
                            item1 = val1[i]
                        except IndexError:
                            item1 = None
                        try:
                            item2 = val2[i]
                        except IndexError:
                            item2 = None

                        if isinstance(item1, MongoModel) and isinstance(item2, MongoModel):
                            nested_diff = _compare(item1, item2, item_path)
                            if nested_diff or include_unchanged:
                                diffs.update(nested_diff)
                            continue

                        if strict:
                            changed = item1 != item2 or type(item1) != type(item2)
                        else:
                            changed = item1 != item2

                        if changed or include_unchanged:
                            diffs[item_path] = {
                                "old": item1,
                                "new": item2,
                                "type_changed": type(item1).__name__ != type(item2).__name__
                            }

                    continue

                # Compare scalars
                if strict:
                    changed = val1 != val2 or type(val1) != type(val2)
                else:
                    changed = val1 != val2

                if changed or include_unchanged:
                    diffs[full_path] = {
                        "old": val1,
                        "new": val2,
                        "type_changed": type(val1).__name__ != type(val2).__name__
                    }

            return diffs

        nested_diffs = _compare(a, b)

        if not flat:
            return nested_diffs

        return nested_diffs  # Already flattened via dot-paths

    # ----------------------------------------------------------------------------------
    # MongoDB Read/Query Operations (class methods)
    # ----------------------------------------------------------------------------------

    @classmethod
    def find_one(cls, filter: dict) -> Any:
        """
        Find and return a single document matching the given filter.

        Args:
            filter (dict): MongoDB filter query.

        Returns:
            MongoModel | None: Instance of the model if found, otherwise None.
        """
        doc = cls._get_collection().find_one(filter)
        if doc:
            return cls.from_dict(doc)
        return None

    @classmethod
    def find_many(cls, filter: dict = None, sort=None, limit=0) -> List[Any]:
        """
        Find and return a list of documents matching the given filter.

        Args:
            filter (dict, optional): MongoDB filter query. Defaults to None (match all).
            sort (list, optional): A list of (field, direction) tuples for sorting.
            limit (int, optional): Maximum number of results to return.

        Returns:
            List[MongoModel]: A list of model instances.
        """
        cursor = cls._get_collection().find(filter or {})
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        return [cls.from_dict(doc) for doc in cursor]

    @classmethod
    def find_by_id(cls, _id):
        """
        Find a document by its MongoDB _id field.

        Args:
            _id: The ObjectId or value of the _id field.

        Returns:
            dict | None: The raw MongoDB document, or None.
        """
        return cls._get_collection().find_one({"_id": _id})

    @classmethod
    def delete_one(cls, filter: dict):
        """
        Delete a single document that matches the filter.

        Args:
            filter (dict): MongoDB filter query.

        Returns:
            DeleteResult: MongoDB deletion result.
        """
        return cls._get_collection().delete_one(filter)

    @classmethod
    def delete_many(cls, filter: dict):
        """
        Delete multiple documents that match the filter.

        Args:
            filter (dict): MongoDB filter query.

        Returns:
            DeleteResult: MongoDB deletion result.
        """
        return cls._get_collection().delete_many(filter)

    @classmethod
    def update_one(cls, filter: dict, update: dict, upsert: bool = False):
        """
        Update a single document.

        Args:
            filter (dict): Query to find the document.
            update (dict): Update operations.
            upsert (bool): Whether to insert the document if it doesn't exist.

        Returns:
            UpdateResult: MongoDB update result.
        """
        return cls._get_collection().update_one(filter, update, upsert=upsert)

    @classmethod
    def update_many(cls, filter: dict, update: dict, upsert: bool = False):
        """
        Update multiple documents.

        Args:
            filter (dict): Query to find documents.
            update (dict): Update operations.
            upsert (bool): Whether to insert documents if none match.

        Returns:
            UpdateResult: MongoDB update result.
        """
        return cls._get_collection().update_many(filter, update, upsert=upsert)

    @classmethod
    def count_documents(cls, filter: dict = None):
        """
        Count the number of documents that match the filter.

        Args:
            filter (dict, optional): MongoDB query filter. Defaults to match all.

        Returns:
            int: Number of matching documents.
        """
        return cls._get_collection().count_documents(filter or {})

    @classmethod
    def exists(cls, filter: dict) -> bool:
        """
       Check if at least one document matches the given filter.

       Args:
           filter (dict): MongoDB query filter.

       Returns:
           bool: True if one or more documents match.
       """
        return cls._get_collection().count_documents(filter, limit=1) > 0

    @classmethod
    def ensure_indexes(cls):
        """
        Ensure indexes are created for fields defined with 'index' in the schema.

        Iterates through the schema's properties and creates ascending indexes
        on fields that contain an 'index' key. Useful for performance optimization.
        """
        collection = cls._get_collection()
        for field, details in cls._schema.get('properties', {}).items():
            if 'index' in details:
                collection.create_index([(field, 1)])  # Example index creation

    @classmethod
    def distinct_values(cls, field: str):
        """
        Retrieve all distinct values for a specified field in the collection.

        Args:
            field (str): Name of the field.

        Returns:
            List[Any]: A list of distinct values.
        """
        return cls._get_collection().distinct(field)

    @classmethod
    def aggregate(cls, pipeline: List[dict]):
        """
        Run an aggregation pipeline on the collection.

        Args:
            pipeline (List[dict]): A list of aggregation stages.

        Returns:
            List[dict]: The aggregation result set.
        """
        return list(cls._get_collection().aggregate(pipeline))

    @classmethod
    def find_and_modify(cls, filter: dict, update: dict, upsert: bool = False):
        """
        Atomically find and update a document.

        Args:
            filter (dict): Filter to locate the document.
            update (dict): Update operations.
            upsert (bool): If True, insert the document if not found.

        Returns:
            dict | None: The document before update, or None.
        """
        return cls._get_collection().find_one_and_update(filter, update, upsert=upsert)

    @classmethod
    def validate_schema(cls, data: dict):
        """
        Validate a data dictionary against the class schema.

        Args:
            data (dict): The input dictionary to validate.

        Raises:
            ValueError: If a field is not in the schema.
            TypeError: If the field type does not match expected BSON type.

        Returns:
            bool: True if data is valid.
        """
        for field, value in data.items():
            if field not in cls._schema['properties']:
                raise ValueError(f"Field {field} is not in schema")
            expected_type = cls._schema['properties'][field].get('bsonType')
            if expected_type and not isinstance(value, expected_type):
                raise TypeError(f"Field {field} should be of type {expected_type}")
        return True

    @classmethod
    def bulk_write(cls, operations: List[Dict]):
        """
        Execute a batch of bulk operations (e.g., insert, update, delete).

        Args:
            operations (List[Dict]): A list of write operations.

        Returns:
            BulkWriteResult: MongoDB result object.
        """
        return cls._get_collection().bulk_write(operations)

    # ----------------------------------------------------------------------------------
    # Introspection & Representation
    # ----------------------------------------------------------------------------------
    def __repr__(self):
        return f"{self.__class__.__name__}({self._data})"

    def __dir__(self):
        return sorted(set(super().__dir__()) | set(self._data.keys()))

    @classmethod
    def pretty_print_schema(cls):
        """
        Nicely print the current MongoModel schema for inspection/debugging.
        """
        import pprint
        pprint.pprint(cls._schema, indent=2)

    @classmethod
    def get_nested_classes(cls):
        """
        Recursively retrieve all nested MongoModel subclasses defined within this class.

        Returns:
            dict: A flat map where keys are attribute names and values are class references.
        """
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

        def type_label(field_schema):
            bson_type = field_schema.get("bsonType") or field_schema.get("type")
            enum = field_schema.get("enum")
            type_map = {
                "string": "str", "int": "int", "bool": "bool", "double": "float",
                "objectId": "ObjectId", "date": "datetime", "array": "List",
                "object": "Object", "null": "None", "long": "int"
            }

            typename = None
            if isinstance(bson_type, list):
                typename = " | ".join([type_map.get(t, t) for t in bson_type])
            elif bson_type:
                typename = type_map.get(bson_type, str(bson_type))

            # Show "enum" if no type is defined but enum exists
            if not typename and enum:
                typename = "enum"

            # Add enum info for scalar fields
            if enum:
                typename += f" [{', '.join(map(str, enum))}]"

            # Add enum info for arrays of scalars
            if bson_type == "array":
                item_schema = field_schema.get("items", {})
                item_enum = item_schema.get("enum")
                if item_enum:
                    typename += f" [{', '.join(map(str, item_enum))}]"

            return typename

        if _depth == 0:
            print(prefix + "└── " + c(cls.__name__, "96"))

        props = cls._schema.get("properties", {})
        children = []

        for field_name, field_schema in props.items():
            typename = type_label(field_schema)
            bson_type = field_schema.get("bsonType") or field_schema.get("type")
            nested_class = None

            if bson_type == "object":
                nested_class = getattr(cls, f"__class_for__{field_name}", None)
            elif bson_type == "array":
                nested_class = getattr(cls, f"{field_name}_item", None)
                if nested_class:
                    typename = f"List[{field_name}_item]"

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

    @classmethod
    def fields(cls) -> dict:
        """
        Return a dictionary of field names and their BSON types (as Python types).
        """
        type_map = {
            "string": "str", "int": "int", "bool": "bool", "double": "float",
            "objectId": "ObjectId", "date": "datetime", "array": "List",
            "object": "dict", "null": "None", "long": "int", "decimal": "Decimal"
        }
        props = cls._schema.get("properties", {})
        return {
            field: type_map.get(details.get("bsonType") or details.get("type"), "Any")
            for field, details in props.items()
        }

    @classmethod
    def enums(cls) -> dict:
        """
        Return a dictionary of enum fields and their allowed values.
        """
        props = cls._schema.get("properties", {})
        return {
            field: details["enum"]
            for field, details in props.items()
            if "enum" in details
        }

    # ----------------------------------------------------------------------------------
    # Data Analysis & Reporting
    # ----------------------------------------------------------------------------------
    @classmethod
    def summarize(cls, sample_size=None, top: int = 5):
        """
        Summarize collection data across all documents.

        Args:
            sample_size (int, optional): Number of documents to sample. Defaults to None (all).
            top (int): Number of top values to include for string fields.

        Returns:
            str: JSON summary with key metrics and top values per field.
        """
        import json
        from statistics import mean, median, stdev
        from collections import Counter, defaultdict

        def flatten(doc, prefix=''):
            """Flatten nested dictionaries using dot notation."""
            out = {}
            for k, v in doc.items():
                key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    out.update(flatten(v, key))
                elif isinstance(v, list):
                    for i, item in enumerate(v):
                        if isinstance(item, dict):
                            out.update(flatten(item, f"{key}[{i}]"))
                        else:
                            out[f"{key}[{i}]"] = item
                else:
                    out[key] = v
            return out

        def analyze(values):
            stats = {}

            cleaned = [v for v in values if v is not None]

            if not cleaned:
                return {"count": 0}

            sample = cleaned[:10]
            dtype = type(sample[0])

            stats["type"] = dtype.__name__
            stats["count"] = len(values)
            stats["missing"] = values.count(None)
            stats["unique"] = len(set(cleaned))

            total = len(cleaned)

            if dtype in (int, float):
                try:
                    stats.update({
                        "min": min(cleaned),
                        "max": max(cleaned),
                        "mean": round(mean(cleaned), 2),
                        "median": round(median(cleaned), 2),
                        "stdev": round(stdev(cleaned), 2) if len(cleaned) > 1 else 0
                    })
                except Exception:
                    pass

            elif dtype == str:
                counter = Counter(cleaned)
                top_items = counter.most_common(top)
                stats[f"top_{top}"] = [
                    {
                        "value": val,
                        "count": cnt,
                        "percent": round(cnt / len(cleaned), 3)
                    } for val, cnt in Counter(cleaned).most_common(top)
                ]

            elif dtype == bool:
                stats["true"] = cleaned.count(True)
                stats["false"] = cleaned.count(False)

            elif dtype in (datetime, ObjectId):
                stats["min"] = min(cleaned)
                stats["max"] = max(cleaned)

            return stats

        # Load and sample from MongoDB
        collection = cls._get_collection()
        cursor = collection.find()
        if sample_size:
            cursor = cursor.limit(sample_size)

        all_docs = list(cursor)
        field_data = defaultdict(list)

        for doc in all_docs:
            flat = flatten(doc)
            for field, value in flat.items():
                field_data[field].append(value)

        result = {
            "sample_size": len(all_docs),
            "fields": {field: analyze(vals) for field, vals in field_data.items()}
        }

        return json.dumps(result, default=str, indent=2)


# ----------------------------------------------------------------------------------
# Lifecycle Hook Functions
# ----------------------------------------------------------------------------------

def pre_save(func):
    func._hook_type = "pre_save"
    return func


def post_save(func):
    func._hook_type = "post_save"
    return func


def pre_delete(func):
    func._hook_type = "pre_delete"
    return func


def post_delete(func):
    func._hook_type = "post_delete"
    return func

