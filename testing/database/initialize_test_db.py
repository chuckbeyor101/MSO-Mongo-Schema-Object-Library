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
from pathlib import Path

from testing.database import db_config
from pymongo import MongoClient
from pymongo.errors import CollectionInvalid
import os
import json


def main():
    client = get_db_client()
    delete_previous_db_data(client)
    db = initialize_db_collection(client, db_config.test_db_name, "people", "people_schema.json")
    return db


def initialize_db_collection(client, db_name, collection_name, schema_file_path):
    # Load JSON schema
    schema_path = Path(__file__).parent / schema_file_path
    with open(schema_path, "r") as f:
        schema = json.load(f)

    db = client[db_config.test_db_name]
    db.drop_collection(collection_name)

    try:
        db.create_collection(
            collection_name,
            validator={"$jsonSchema": schema["$jsonSchema"]}
        )
        print(f"Created collection '{collection_name}' in DB '{db_name}' with validation.")

    except CollectionInvalid:
        print(f"Collection '{collection_name}' already exists.")

    return db


def get_db_client():
    # Connect to MongoDB
    MONGO_URI = os.getenv("MSO_TESTING_URI", "mongodb://localhost:27017")

    client = MongoClient(MONGO_URI)

    # Check if the connection was successful
    if client is None:
        raise ConnectionError("Failed to connect to MongoDB. Please check your connection settings.")

    # Return the MongoDB client
    return client


def delete_previous_db_data(client):
    """
    Deletes all databases except 'admin' and 'local' from the MongoDB client.
    """
    # Get a list of all database names
    db_names = client.list_database_names()

    # Remove admin and local databases from deletion
    db_names = [db_name for db_name in db_names if db_name not in ['admin', 'local']]

    if not db_names:
        print("No databases found to delete.")
        return

    # Iterate through the database names and drop each one
    print(f"Found {len(db_names)} databases to delete: {db_names}")
    for db_name in db_names:
        client.drop_database(db_name)
        print(f"Deleted database: {db_name}")


if __name__ == "__main__":
    main()