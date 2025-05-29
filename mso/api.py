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

from fastapi import FastAPI, APIRouter, HTTPException, Request, Query, Depends, status, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Any, Dict, List, Union, Callable, Annotated, Tuple
from pymongo.database import Database
from mso import utils
from mso.generator import get_model
import uvicorn
import traceback
import re
from datetime import datetime
from typing import Any, Union, Mapping
from dateutil.parser import parse as parse_datetime
from bson import ObjectId
from bson.errors import InvalidId

class QueryRequest(BaseModel):
    filter: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Filter criteria as a JSON object. Example: {'age': {'$gt': 30}}",
        examples=[{"last_modified": {"$gte": "2024-01-01T00:00:00Z"}}]
    )
    sort: Optional[List[List[Union[str, int]]]] = Field(
        default=None,
        description='Sort order as a list of lists. Example: [["age", -1], ["name", 1]]',
        examples=[[["last_modified", "asc"]]]
    )


def format_validation_error(e: Exception, debug: bool = False):
    if isinstance(e, dict):
        return e
    try:
        if hasattr(e, "args") and isinstance(e.args[0], dict):
            return e.args[0]
    except Exception:
        pass
    if debug:
        return {"error": str(e), "trace": traceback.format_exc(limit=5)}
    return {"error": str(e)}


def get_auth_dependency(auth_func: Callable[[Request], None]):
    async def dependency(request: Request):
        if auth_func:
            await auth_func(request)
    return Depends(dependency)

def convert_dates_in_filter(obj: Union[dict, list]) -> Any:
    """
    Recursively convert ISO date strings in MongoDB-style filters into datetime objects.
    """
    if isinstance(obj, dict):
        return {
            key: convert_dates_in_filter(value)
            for key, value in obj.items()
        }
    elif isinstance(obj, list):
        return [convert_dates_in_filter(item) for item in obj]
    elif isinstance(obj, str):
        try:
            # Only convert if string is ISO-like
            if "T" in obj and obj.endswith("Z"):
                return parse_datetime(obj)
        except Exception:
            return obj  # return original if not a date
    return obj


def parse_objectid(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid document ID format")


def sanitize_filter(filter: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validates and sanitizes filter input for MongoDB.
    Converts ISO date strings to datetime objects.
    Raises HTTPException on invalid input.
    """
    if not filter:
        return {}

    if not isinstance(filter, dict):
        raise HTTPException(
            status_code=400,
            detail="Filter must be a JSON object"
        )

    sanitized_filter = convert_dates_in_filter(filter)

    # Additional validation can be added here if needed

    return sanitized_filter

def sanitize_sort(sort: Union[List[List[Union[str, int]]], None]) -> List[Tuple[str, int]]:
    """
    Validates and sanitizes sort input for MongoDB.
    Converts input to a list of (field, direction) tuples.
    Raises HTTPException on invalid input.
    """
    if not sort:
        return []

    valid_sort = []
    for item in sort:
        if isinstance(item, list) and len(item) == 2:
            field, direction = item

            if isinstance(direction, str):
                direction = direction.lower()
                if direction == "asc":
                    direction = 1
                elif direction == "desc":
                    direction = -1
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid sort string for field '{field}': use 'asc' or 'desc'"
                    )

            if isinstance(direction, int) and direction in (1, -1):
                valid_sort.append((field, direction))
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid sort direction for field '{field}': must be 1, -1, 'asc', or 'desc'"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Each sort item must be a list of [field, direction]"
            )
    return valid_sort


def add_api_routes(app, name: str, Model, auth_func=None, debug=False, read_only=False, limit_default=20, limit_max=1000):
    auth_dep = get_auth_dependency(auth_func) if auth_func else None
    router = APIRouter(dependencies=[auth_dep] if auth_dep else [])

    # ---------------------------------------------- Read Only Routes ------------------------------------------------
    @router.get("/get/{id}", status_code=200, summary=f"Get Document from {name} by ID")
    def get_doc(id: str):
        try:
            object_id = parse_objectid(id)

            doc = Model.find_one({"_id": object_id})
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")

            return doc.to_dict(output_json=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=format_validation_error(e, debug))

    @router.get("/distinct/{field}", summary=f"Get Distinct Values from {name}", tags=[name])
    def distinct_field(field: str):
        try:
            values = Model.distinct(field)
            return {"field": field, "values": values}
        except Exception as e:
            raise HTTPException(status_code=400, detail=format_validation_error(e, debug))

    @router.post("/count", status_code=200, summary=f"Count Documents in {name}")
    def count_docs(params: QueryRequest = Body(default=None)):
        try:
            filter = sanitize_filter(params.filter) if params else {}
            count = Model.count_documents(filter)
            return {"count": count}
        except Exception as e:
            raise HTTPException(status_code=400, detail=format_validation_error(e, debug))

    @router.post("/query", status_code=200, summary=f"Query Documents in {name}",)
    def query_docs(
            params: QueryRequest = Body(default=None),
            page: int = Query(1, ge=1, description="Page number"),
            limit: int = Query(limit_default, ge=1, le=limit_max, description="Documents per page"),
    ):

        if params is None:
            filter = {}
            sort = None
        else:
            filter = sanitize_filter(params.filter)
            sort = sanitize_sort(params.sort)

        skip = (page - 1) * limit

        docs = Model.find_many(filter=filter, sort=sort, limit=limit, skip=skip)
        total = Model.count_documents(filter=filter)

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "results": [doc.to_dict(output_json=True) if doc else None for doc in docs]
        }



    # ---------------------------------------------- Destructive Routes ------------------------------------------------
    if not read_only:

        @router.post("/insert", status_code=201, summary=f"Insert Document into {name}")
        def insert_doc(payload: dict = Body(...)):
            try:
                doc = Model.from_dict(payload)
                doc.save()
                return {"inserted_id": str(doc._id)}
            except Exception as e:
                raise HTTPException(status_code=400, detail=format_validation_error(e, debug))

        @router.post("/bulk-insert", status_code=201, summary=f"Bulk Insert Documents into {name}")
        def bulk_insert(docs: List[dict] = Body(...)):
            try:
                inserted_ids = []
                for doc_data in docs:
                    doc = Model.from_dict(doc_data)
                    doc.save()
                    inserted_ids.append(str(doc._id))
                return {"inserted_ids": inserted_ids}
            except Exception as e:
                raise HTTPException(status_code=400, detail=format_validation_error(e, debug))

        @router.put("/update/{id}", status_code=200, summary=f"Update Document in {name} by ID")
        def update_doc(id: str, payload: dict = Body(...)):
            try:
                object_id = parse_objectid(id)

                if not any(key.startswith("$") for key in payload):
                    payload = {"$set": payload}

                result = Model.update_one({"_id": object_id}, payload)

                if result.modified_count == 0:
                    raise HTTPException(status_code=404, detail="Document not found or no changes made")

                return {"updated_id": id}
            except Exception as e:
                raise HTTPException(status_code=400, detail=format_validation_error(e, debug))

        @router.put("/replace/{id}", status_code=200, summary=f"Replace Document in {name} by ID")
        def replace_doc(id: str, payload: dict = Body(...)):
            try:
                object_id = parse_objectid(id)
                payload["_id"] = object_id  # ensure _id is preserved
                result = Model.replace_one({"_id": object_id}, payload)
                if result.modified_count == 0:
                    raise HTTPException(status_code=404, detail="Document not found or not replaced")
                return {"replaced_id": id}
            except Exception as e:
                raise HTTPException(status_code=400, detail=format_validation_error(e, debug))

        @router.delete("/delete/{id}", status_code=200, summary=f"Delete Document from {name} by ID")
        def delete_doc(id: str):
            try:
                object_id = parse_objectid(id)

                deleted = Model.delete_one({"_id": object_id})
                if deleted.deleted_count == 0:
                    raise HTTPException(status_code=404, detail="Document not found")

                return {"deleted_id": id}

            except Exception as e:
                raise HTTPException(status_code=400, detail=format_validation_error(e, debug))

    app.include_router(router, prefix=f"/{name}", tags=[name])


def start_api(
    db: Database,
    collections=None,
    exclude_collections: list = [],
    host: str = "127.0.0.1",
    port: int = 8000,
    title: str = "MSO Auto-Generated API",
    description: str = "Automatically generated REST API for MongoDB collections",
    version: str = "1.0.0",
    docs_url: str = "/docs",
    redoc_url: str = "/redoc",
    openapi_url: str = "/openapi.json",
    enable_cors: bool = True,
    cors_origins: list = ["*"],
    cors_methods: list = ["*"],
    cors_headers: list = ["*"],
    cors_credentials: bool = True,
    auth_func: callable = None,
    debug: bool = False,
    exclude_system_collections: bool = True,
    limit_default=20,
    limit_max=1000,
    **uvicorn_kwargs
):



    app = FastAPI(
        title=title,
        description=description,
        version=version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    if enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=cors_credentials,
            allow_methods=cors_methods,
            allow_headers=cors_headers,
        )

    all_collections = db.list_collection_names()

    if collections is None or collections == ["*"]:
        included = all_collections
    else:
        def matches_inclusion(name):
            return any(pattern == name or re.fullmatch(pattern, name) for pattern in collections)
        included = [name for name in all_collections if matches_inclusion(name)]

    if exclude_collections:
        def matches_exclusion(name):
            return any(pattern == name or re.fullmatch(pattern, name) for pattern in exclude_collections)
        included = [name for name in included if not matches_exclusion(name)]

    collections = included

    if exclude_system_collections:
        collections = [name for name in collections if not name.startswith("system.")]

    for name in collections:
        try:
            Model = get_model(db, name)
        except ValueError as e:
            print(f"Skipping collection '{name}': {e}")
            continue

        if utils.is_view(db, name):
            print(f"Detected view: {name}. Registering read-only routes.")
            add_api_routes(app, name, Model, auth_func=auth_func, debug=debug, read_only=True, limit_default=limit_default, limit_max=limit_max)
        else:
            add_api_routes(app, name, Model, auth_func=auth_func, debug=debug, read_only=False, limit_default=limit_default, limit_max=limit_max)

    uvicorn.run(app, host=host, port=port, **uvicorn_kwargs)
