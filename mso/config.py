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

from datetime import datetime
from decimal import Decimal
from bson import ObjectId

# ----------------------------------------------------------------------------------
# BSON Type Mapping (used to validate types from MongoDB schema)
# ----------------------------------------------------------------------------------
BSON_TYPE_MAP = {
    "string": str,
    "int": int,
    "bool": bool,
    "double": float,
    "float": float,
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