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
from pymongo.database import Database
from typing import Union, List, Type
from mso import config


def parse_schema(schema: dict, name: str = 'Root'):
    """
    Recursively extracts all nested object schemas from a MongoDB JSON Schema.

    This function traverses the given schema and collects all sub-schemas
    for fields of type "object", assigning each a unique name based on its
    nesting path. The result is a flat dictionary mapping generated class
    names to their respective sub-schemas.

    Args:
        schema (dict): The root MongoDB JSON schema to parse.
        name (str): The base name to use for class naming during traversal.

    Returns:
        dict: A dictionary where keys are class-like names (e.g., "Root_Address_City")
              and values are their corresponding schema fragments.
    """
    classes = {}
    properties = schema.get('properties', {})
    for prop_name, prop_info in properties.items():
        if prop_info.get('type') == 'object':
            nested_class_name = f"{name}_{prop_name.capitalize()}"
            nested_classes = parse_schema(prop_info, nested_class_name)
            classes.update(nested_classes)
    classes[name] = schema
    return classes


def normalize_class_name(name: str) -> str:
    """
    Normalizes a class name by replacing spaces and hyphens with underscores.
    This is useful for generating valid Python class names from MongoDB schema field names.

    :param name: The original name to normalize.
    :return: A normalized name suitable for use as a Python class name.
    """
    return name.replace(' ', '_').replace('-', '_')


def map_bson_to_python_type(bson_type: Union[str, List[str], None]) -> Union[Type, List[Type]]:
    """
    Map a BSON type or list of BSON types to corresponding Python type(s).

    Args:
        bson_type (str | List[str] | None): A BSON type or list of types from a MongoDB schema.

    Returns:
        type | List[type]: Corresponding Python type(s). Defaults to 'object' if input is None or unknown.
    """
    def resolve(t: str) -> Type:
        return config.BSON_TYPE_MAP.get(t, object)

    if bson_type is None:
        return object

    if isinstance(bson_type, list):
        return [resolve(t) for t in bson_type]

    return resolve(bson_type)


def get_primary_bson_type(bson_type):
    """
    Returns the first non-null bsonType from a list of bsonTypes.

    param bson_type: A single bsonType or a list of bsonTypes.
    return: The first non-null bsonType from the list, or None if all are 'null'.

    Example usage: Take a list of bsonTypes from MongoDB schema and return the first valid type. This could be used in a pythonic model. This is needed because MongoDB schema can have multiple bsonTypes for a single field, and we want to use the first valid type for our model.
    """
    if isinstance(bson_type, list):
        for t in bson_type:
            if t != 'null':
                return t
    return bson_type


def is_view(db: Database, collection_name: str) -> bool:
    """
    Checks if a collection in MongoDB is a view.
    A view in MongoDB is a read-only collection that is defined by an aggregation pipeline.

    :param db: The MongoDB database instance.
    :param collection_name: The name of the collection to check.
    :return: True if the collection is a view, False otherwise.
    """
    return db["system.views"].find_one({"_id": f"{db.name}.{collection_name}"}) is not None
