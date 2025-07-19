# ######################################################################################################################
#  MSO Copyright (c) 2025 by Charles L Beyor and Beyotek Inc.                                                          #
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

from mso import utils
from decimal import Decimal
from bson import ObjectId
from datetime import datetime


# --------------------------------------------------------------------------------------------------
# NullDocument acts as a fallback object when accessing missing fields in safe_mode.
# Any attribute or item access returns None without raising an error.
# --------------------------------------------------------------------------------------------------
class NullDocument:
    def __getattr__(self, item): return None
    def __getitem__(self, item): return None
    def __repr__(self): return "null"
    def to_dict(self, output_json=False): return None


# --------------------------------------------------------------------------------------------------
# Main factory function that returns a read-only model class for a MongoDB view collection.
# Supports deeply nested documents, attribute access, and safe fallback behavior.
# --------------------------------------------------------------------------------------------------
def create_readonly_model(collection_name, db):

    # --------------------------------------------------------------------------------------------------
    # ReadOnlyDocument wraps an individual MongoDB document.
    # Recursively converts nested dicts/lists into wrapped objects with attribute access.
    # --------------------------------------------------------------------------------------------------
    class ReadOnlyDocument:
        def __init__(self, data, safe_mode=True):
            self._safe_mode = safe_mode  # Controls whether to suppress missing attribute errors
            self._data = self._wrap(data)  # Recursively wrap nested structures

        def _wrap(self, value):
            # Recursively process values for attribute access
            if isinstance(value, dict):
                return {k: self._wrap(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [self._wrap(v) for v in value]
            elif isinstance(value, ObjectId):
                return value
            elif isinstance(value, datetime):
                return value
            elif isinstance(value, Decimal):
                return float(value)
            else:
                return value

        def __getattr__(self, item):
            # Safe nested attribute access
            if item in self._data:
                val = self._data[item]
                if isinstance(val, dict):
                    return ReadOnlyDocument(val, safe_mode=self._safe_mode)
                elif isinstance(val, list):
                    return [ReadOnlyDocument(v, safe_mode=self._safe_mode) if isinstance(v, dict) else v for v in val]
                return val
            if self._safe_mode:
                return NullDocument()
            raise AttributeError(f"{item} not found in ReadOnlyDocument")

        def __getitem__(self, item):
            # Support dict-style access
            return self.__getattr__(item)

        def __repr__(self):
            # Developer-friendly output
            return repr(self.to_dict())

        def to_dict(self, output_json=False):
            # Deep recursive conversion to plain dict
            def serialize(value):
                if isinstance(value, ReadOnlyDocument):
                    return value.to_dict(output_json)
                elif isinstance(value, dict):
                    return {k: serialize(v) for k, v in value.items()}
                elif isinstance(value, list):
                    return [serialize(v) for v in value]
                elif output_json:
                    if isinstance(value, ObjectId):
                        return str(value)
                    elif isinstance(value, datetime):
                        return value.isoformat()
                    elif isinstance(value, Decimal):
                        return float(value)
                return value

            return serialize(self._data)  # Deep serialization

        def save(self):
            # Read-only document, can't save
            raise TypeError(f"Cannot save document from read-only view '{collection_name}'.")

        def delete(self):
            # Read-only document, can't delete
            raise TypeError(f"Cannot delete document from read-only view '{collection_name}'.")

    # --------------------------------------------------------------------------------------------------
    # ReadOnlyModel is a static class that wraps query access for a view collection.
    # Returns ReadOnlyDocument instances for read-only inspection.
    # --------------------------------------------------------------------------------------------------
    class ReadOnlyModel:
        __collection__ = collection_name
        __db__ = db
        _collection = db[collection_name]
        __is_view__ = True  # Mark this as a view
        _safe_mode = True   # Default behavior is safe nested access

        @classmethod
        def set_safe_mode(cls, enabled: bool):
            # Toggle safe mode on/off
            cls._safe_mode = enabled

        @classmethod
        def find(cls, *args, **kwargs):
            # Generator for matching documents
            for doc in cls._collection.find(*args, **kwargs):
                yield ReadOnlyDocument(doc, safe_mode=cls._safe_mode)

        @classmethod
        def find_one(cls, *args, **kwargs):
            # Return one matching document (or None)
            doc = cls._collection.find_one(*args, **kwargs)
            return ReadOnlyDocument(doc, safe_mode=cls._safe_mode) if doc else None

        @classmethod
        def find_many(cls, *args, **kwargs):
            # Return all matching documents as a list
            return [ReadOnlyDocument(doc, safe_mode=cls._safe_mode) for doc in cls._collection.find(*args, **kwargs)]

        @classmethod
        def aggregate(cls, *args, **kwargs):
            # Support aggregation pipeline
            return cls._collection.aggregate(*args, **kwargs)

        @classmethod
        def count_documents(cls, *args, **kwargs):
            # Support counting matching documents
            return cls._collection.count_documents(*args, **kwargs)

        @classmethod
        def get(cls, _id):
            # Get a document by its _id
            return cls.find_one({"_id": _id})

        def __init__(self, *args, **kwargs):
            # Prevent instantiating this model directly
            raise TypeError(f"'{collection_name}' is a view and cannot be instantiated.")

    # Dynamically name the class based on the collection name
    ReadOnlyModel.__name__ = utils.normalize_class_name(collection_name)

    return ReadOnlyModel
