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

from fastapi import FastAPI, APIRouter, HTTPException, Request, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, create_model
from typing import Optional, Any, Dict, List, Union, Callable
from pymongo.database import Database
from bson import ObjectId
import uvicorn
import traceback
import re

# Swagger-friendly request models
class QueryParams(BaseModel):
    filter: Dict[str, Any] = Field(default_factory=dict, description="MongoDB filter query")
    projection: Optional[Dict[str, int]] = Field(default=None, description="Fields to include/exclude")
    sort: Optional[List[List[Union[str, int]]]] = Field(default=None, description='List of sort pairs: [["field", 1]]')
    page: Optional[int] = Field(default=1, ge=1)
    limit: Optional[int] = Field(default=20, ge=1)


class AggregateParams(BaseModel):
    pipeline: List[Dict[str, Any]] = Field(..., description="MongoDB aggregation pipeline")


class DistinctParams(BaseModel):
    field: str = Field(..., description="Field name to get distinct values for")


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


def is_view(db: Database, collection_name: str) -> bool:
    return db["system.views"].find_one({"_id": f"{db.name}.{collection_name}"}) is not None


def build_request_model(model_cls):
    schema = getattr(model_cls, "__mso_schema__", {}).get("properties", {})
    fields = {}
    for key, spec in schema.items():
        field_type = Any
        description = spec.get("description", "")
        example = spec.get("examples", [None])[0] or spec.get("default", None)
        fields[key] = (field_type, Field(..., description=description, example=example))
    return create_model(f"{model_cls.__name__}Request", **fields)


def add_api_routes(app, name: str, Model, auth_func=None, debug=False, read_only=False):
    router = APIRouter()
    auth_dep = get_auth_dependency(auth_func) if auth_func else None
    RequestModel = build_request_model(Model)

    @router.get("/", status_code=200)
    def list_docs(
        page: int = Query(1, ge=1, description="Page number"),
        limit: int = Query(20, ge=1, le=100, description="Documents per page"),
        sort: Optional[str] = Query(None, description='Sort as JSON string, e.g. [["age", -1]]')
    ):
        skip = (page - 1) * limit
        cursor = Model.find({})
        if sort:
            import json
            sort_criteria = json.loads(sort)
            cursor = cursor.sort(sort_criteria)
        total = Model.count({})
        docs = cursor.skip(skip).limit(limit)
        return {
            "total": total,
            "page": page,
            "limit": limit,
            "results": [doc.to_dict() for doc in docs]
        }

    @router.get("/{id}", status_code=200)
    def get_doc(id: str):
        doc = Model.get(ObjectId(id))
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc.to_dict()

    if not read_only:
        @router.post("/", status_code=201, dependencies=[auth_dep] if auth_dep else [])
        def create_doc(data: RequestModel):
            try:
                doc = Model.from_dict(data.dict())
                doc.save()
                return doc.to_dict()
            except Exception as e:
                detail = format_validation_error(e, debug)
                raise HTTPException(status_code=422, detail=detail)

        @router.put("/{id}", status_code=200, dependencies=[auth_dep] if auth_dep else [])
        def replace_doc(id: str, data: RequestModel):
            try:
                doc = Model.from_dict(data.dict())
                doc._id = ObjectId(id)
                doc.save()
                return doc.to_dict()
            except Exception as e:
                detail = format_validation_error(e, debug)
                raise HTTPException(status_code=422, detail=detail)

        @router.patch("/{id}", status_code=200, dependencies=[auth_dep] if auth_dep else [])
        def update_doc(id: str, data: RequestModel):
            doc = Model.get(ObjectId(id))
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
            try:
                for k, v in data.dict().items():
                    setattr(doc, k, v)
                doc.save()
                return doc.to_dict()
            except Exception as e:
                detail = format_validation_error(e, debug)
                raise HTTPException(status_code=422, detail=detail)

        @router.delete("/{id}", status_code=200, dependencies=[auth_dep] if auth_dep else [])
        def delete_doc(id: str):
            doc = Model.get(ObjectId(id))
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
            doc.delete()
            return {"deleted": id}

    @router.post("/query", status_code=200)
    def query_docs(params: QueryParams):
        filter = params.filter
        projection = params.projection
        sort = params.sort
        page = params.page
        limit = params.limit
        skip = (page - 1) * limit

        cursor = Model.find(filter, projection=projection)
        if sort:
            cursor = cursor.sort(sort)
        docs = cursor.skip(skip).limit(limit)
        total = Model.count(filter)

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "results": [doc.to_dict() for doc in docs]
        }

    @router.post("/aggregate", status_code=200)
    def run_aggregate(params: AggregateParams):
        return list(Model._collection.aggregate(params.pipeline))

    @router.post("/distinct", status_code=200)
    def get_distinct(params: DistinctParams):
        return Model._collection.distinct(params.field)

    @router.get("/count", status_code=200)
    def count_docs(filter: Optional[str] = "{}"):
        import json
        parsed_filter = json.loads(filter)
        return {"count": Model.count(parsed_filter)}

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
    **uvicorn_kwargs
):
    from mso.generator import get_model

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

        if is_view(db, name):
            print(f"Detected view: {name}. Registering read-only routes.")
            add_api_routes(app, name, Model, auth_func=auth_func, debug=debug, read_only=True)
        else:
            add_api_routes(app, name, Model, auth_func=auth_func, debug=debug, read_only=False)

    uvicorn.run(app, host=host, port=port, **uvicorn_kwargs)
