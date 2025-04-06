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

from typing import Any, Dict, List


class MongoHelpersMixin:
    @classmethod
    def _get_collection(cls):
        db = getattr(cls, "__db__", None)
        collection = getattr(cls, "__collection__", None)
        if db is None or collection is None:
            raise RuntimeError("Model class missing __db__ or __collection__.")
        return db[collection]

    @classmethod
    def query(cls, filter: Dict = None, projection: Dict = None, sort=None, limit: int = 0, skip: int = 0) -> List[Any]:
        collection = cls._get_collection()
        cursor = collection.find(filter or {}, projection)
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return [cls.from_dict(doc) for doc in cursor]

    @classmethod
    def find_by_id(cls, _id):
        return cls._get_collection().find_one({"_id": _id})

    @classmethod
    def count(cls, filter: Dict = None) -> int:
        return cls._get_collection().count_documents(filter or {})

    @classmethod
    def distinct(cls, field: str, filter: Dict = None):
        return cls._get_collection().distinct(field, filter or {})

    @classmethod
    def aggregate(cls, pipeline: List[Dict]) -> List[Any]:
        return list(cls._get_collection().aggregate(pipeline))

    @classmethod
    def regex_query(cls, field: str, pattern: str, options: str = "i", **kwargs):
        collection = cls._get_collection()
        results = collection.find({field: {"$regex": pattern, "$options": options}}, **kwargs)
        return [cls.from_dict(doc) for doc in results]

    @classmethod
    def text_search(cls, search: str, projection: Dict = None, **kwargs):
        collection = cls._get_collection()
        results = collection.find({"$text": {"$search": search}}, projection, **kwargs)
        return [cls.from_dict(doc) for doc in results]

    @classmethod
    def update_one(cls, filter: Dict, update: Dict, upsert: bool = False):
        return cls._get_collection().update_one(filter, update, upsert=upsert)

    @classmethod
    def update_many(cls, filter: Dict, update: Dict, upsert: bool = False):
        return cls._get_collection().update_many(filter, update, upsert=upsert)

    @classmethod
    def delete_many(cls, filter: Dict):
        return cls._get_collection().delete_many(filter)

    @classmethod
    def replace_one(cls, filter: Dict, replacement: Dict, upsert: bool = False):
        return cls._get_collection().replace_one(filter, replacement, upsert=upsert)

    @classmethod
    def delete_by_id(cls, _id):
        return cls._get_collection().delete_one({"_id": _id})

    @classmethod
    def exists(cls, filter: dict) -> bool:
        return cls._get_collection().count_documents(filter, limit=1) > 0

    @classmethod
    def get_one(cls, filter: dict) -> Any:
        doc = cls._get_collection().find_one(filter)
        if doc is None:
            return None
        return cls.from_dict(doc)

    @classmethod
    def bulk_save(cls, docs: list):
        collection = cls._get_collection()
        models = [doc.to_dict() if hasattr(doc, "to_dict") else doc for doc in docs]
        return collection.insert_many(models)

    @classmethod
    def paginate(cls, filter: dict = None, page: int = 1, page_size: int = 10):
        skip = (page - 1) * page_size
        return cls.query(filter or {}, skip=skip, limit=page_size)

    @staticmethod
    def build_projection(include: list = None, exclude: list = None):
        if include:
            return {field: 1 for field in include}
        if exclude:
            return {field: 0 for field in exclude}
        return None

    @classmethod
    def clone(cls, _id):
        original = cls._get_collection().find_one({"_id": _id})
        if original:
            del original["_id"]  # Remove the _id to insert as a new document
            return cls.from_dict(original)
        raise ValueError(f"No document found with _id {str(_id)}")

    @classmethod
    def update_from_dict(cls, filter: dict, data: dict):
        return cls._get_collection().update_one(filter, {"$set": data})

    @classmethod
    def find_and_modify(cls, filter: dict, update: dict, upsert: bool = False):
        return cls._get_collection().find_one_and_update(filter, update, upsert=upsert)

    @classmethod
    def soft_delete(cls, filter: dict):
        return cls._get_collection().update_many(filter, {"$set": {"is_deleted": True}})

    @classmethod
    def restore_deleted(cls, filter: dict):
        return cls._get_collection().update_many(filter, {"$set": {"is_deleted": False}})
