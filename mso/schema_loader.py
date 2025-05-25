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

def load_schema(db, collection_name):
    collection_info = db.command("listCollections", filter={"name": collection_name})
    collections = collection_info.get("cursor", {}).get("firstBatch", [])

    if not collections:
        raise ValueError(f"Collection '{collection_name}' does not exist or has no $jsonSchema validator.")

    options = collections[0].get("options", {})
    schema = options.get("validator", {}).get("$jsonSchema")

    if not schema:
        raise ValueError(f"Collection '{collection_name}' does not define a $jsonSchema validator.")

    return schema