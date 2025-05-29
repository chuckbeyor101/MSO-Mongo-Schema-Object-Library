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

from mso import generator, utils
from decimal import Decimal
from bson import ObjectId
from datetime import datetime


def create_readonly_model(collection_name, db):
    class ReadOnlyDocument:
        def __init__(self, data):
            self._data = data

        def __getattr__(self, item):
            return self._data.get(item)

        def __getitem__(self, item):
            return self._data[item]

        def __repr__(self):
            return repr(self._data)

        def to_dict(self, output_json=False):
            model_dict = self._data.copy()
            if output_json:
                # Convert ObjectId and datetime to string
                for key, value in model_dict.items():
                    if isinstance(value, ObjectId):
                        model_dict[key] = str(value)
                    elif isinstance(value, datetime):
                        model_dict[key] = value.isoformat()
                    elif isinstance(value, Decimal):
                        model_dict[key] = float(value)
            return model_dict

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
            for doc in cls._collection.find(*args, **kwargs):
                yield ReadOnlyDocument(doc)

        @classmethod
        def find_one(cls, *args, **kwargs):
            doc = cls._collection.find_one(*args, **kwargs)
            return ReadOnlyDocument(doc) if doc else None

        @classmethod
        def find_many(cls, *args, **kwargs):
            return [ReadOnlyDocument(doc) for doc in cls._collection.find(*args, **kwargs)]

        @classmethod
        def aggregate(cls, *args, **kwargs):
            return cls._collection.aggregate(*args, **kwargs)

        @classmethod
        def count_documents(cls, *args, **kwargs):
            return cls._collection.count_documents(*args, **kwargs)

        @classmethod
        def get(cls, _id):
            return cls.find_one({"_id": _id})

        def __init__(self, *args, **kwargs):
            raise TypeError(f"'{collection_name}' is a view and cannot be instantiated.")

    ReadOnlyModel.__name__ = utils.normalize_class_name(collection_name)

    return ReadOnlyModel
