# Define vector operations here:
# Upsert and query functions and signatures

from typing import Sequence, Union, List, Dict, Optional, Any, Tuple

from upstash_vector.errors import ClientError
from upstash_vector.types import (
    Data,
    DeleteResult,
    MetadataUpdateMode,
    QueryRequest,
    RangeResult,
    InfoResult,
    SupportsToList,
    FetchResult,
    QueryResult,
    Vector,
)
from upstash_vector.utils import (
    convert_query_requests_to_payload,
    convert_to_list,
    convert_to_vectors,
    convert_to_payload,
)
from upstash_vector.core.resumable_query import ResumableQuery

DEFAULT_NAMESPACE = ""

UPSERT_PATH = "/upsert"
UPSERT_DATA_PATH = "/upsert-data"
QUERY_PATH = "/query"
QUERY_DATA_PATH = "/query-data"
DELETE_PATH = "/delete"
RESET_PATH = "/reset"
RESET_ALL_PATH = "/reset?all"
RANGE_PATH = "/range"
FETCH_PATH = "/fetch"
INFO_PATH = "/info"
LIST_NAMESPACES_PATH = "/list-namespaces"
DELETE_NAMESPACE_PATH = "/delete-namespace"
UPDATE_PATH = "/update"


def _path_for(namespace: str, path: str) -> str:
    if namespace == DEFAULT_NAMESPACE:
        return path

    return f"{path}/{namespace}"


class IndexOperations:
    def _execute_request(self, payload, path):
        raise NotImplementedError("execute_request")

    def upsert(
        self,
        vectors: Sequence[Union[Dict, tuple, Vector, Data]],
        namespace: str = DEFAULT_NAMESPACE,
    ) -> str:
        """
        Upserts(update or insert) vectors.

        :param vectors: The list vectors to upsert.
        :param namespace: The namespace to use. When not specified, the default namespace is used.

        There are various ways to upsert vectors.

        Example usages:

        ```python
        res = index.upsert(
            vectors=[
                ("id1", [0.1, 0.2], {"metadata_field": "metadata_value"}, "data-value"),
                ("id2", [0.2, 0.2], {"metadata_field": "metadata_value"}),
                ("id3", [0.3,0.4]),
            ]
        )
        ```

        ```python
        res = index.upsert(
            vectors=[
                {"id": "id4", "vector": [0.1, 0.2], "metadata": {"field": "value"}, "data": "data-value"},
                {"id": "id5", "vector": [0.2, 0.2], "metadata": {"field": "value"}},
                {"id": "id6", "vector": [0.5, 0.6]},
            ]
        )
        ```

        ```python
        from upstash_vector import Vector
        res = index.upsert(
            vectors=[
                Vector(id="id7", vector=[0.1, 0.2], metadata={"field": "value"}, data="data-value"),
                Vector(id="id8", vector=[0.1, 0.2], metadata={"field": "value"}),
                Vector(id="id9", vector=[0.6, 0.7]),
            ]
        )
        ```

        ```python
        from upstash_vector import Data
        res = index.upsert(
            vectors=[
                Data(id="id5", data="Goodbye World", metadata={"field": "value"}),
                Data(id="id6", data="Hello World"),
            ]
        )
        ```

        Also, vectors or data can be upserted into particular namespaces of the index by
        providing a name for the `namespace` parameter. When no namespace is provided,
        the default namespace is used.

        ```python
        res = index.upsert(
            vectors=[
                ("id1", [0.1, 0.2]),
                ("id2", [0.3, 0.4]),
            ],
            namespace="ns",
        )
        ```
        """

        vectors = convert_to_vectors(vectors)
        payload, is_vector = convert_to_payload(vectors)
        path = UPSERT_PATH if is_vector else UPSERT_DATA_PATH

        return self._execute_request(payload=payload, path=_path_for(namespace, path))

    def query(
        self,
        vector: Optional[Union[List[float], SupportsToList]] = None,
        top_k: int = 10,
        include_vectors: bool = False,
        include_metadata: bool = False,
        filter: str = "",
        data: Optional[str] = None,
        namespace: str = DEFAULT_NAMESPACE,
        include_data: bool = False,
    ) -> List[QueryResult]:
        """
        Query `top_k` many similar vectors.
        Requires either `data` or `vector` paramter.
        Raises exception if both `data` and `vector` parameters are used.

        :param vector: The vector value to query.
        :param top_k: How many vectors will be returned as the query result.
        :param include_vectors: Whether the resulting `top_k` vectors will have their vector values or not.
        :param include_metadata: Whether the resulting `top_k` vectors will have their metadata or not.
        :param filter: Filter expression to narrow down the query results.
        :param data: Data to query for (after embedding it to a vector)
        :param namespace: The namespace to use. When not specified, the default namespace is used.
        :param include_data: Whether the resulting `top_k` vectors will have their unstructured data or not.

        Example usage:

        ```python
        res = index.query(
            vector=[0.6, 0.9],
            top_k=5,
            include_vectors=False,
            include_metadata=True,
        )
        ```

        ```python
        res = index.query(
            data="hello",
            top_k=5,
            include_vectors=False,
            include_metadata=True,
        )
        ```
        """
        payload = {
            "topK": top_k,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
            "includeData": include_data,
            "filter": filter,
        }

        if data is None and vector is None:
            raise ClientError("either `data` or `vector` values must be given")
        if data is not None and vector is not None:
            raise ClientError(
                "`data` and `vector` values cannot be given at the same time"
            )

        if data is not None:
            payload["data"] = data
            path = QUERY_DATA_PATH
        else:
            payload["vector"] = convert_to_list(vector)
            path = QUERY_PATH

        return [
            QueryResult._from_json(obj)
            for obj in self._execute_request(
                payload=payload, path=_path_for(namespace, path)
            )
        ]

    def query_many(
        self,
        *,
        queries: List[QueryRequest],
        namespace: str = DEFAULT_NAMESPACE,
    ) -> List[List[QueryResult]]:
        """
        Makes a batch query request.

        The batch should only contain elements whose `data`
        or `vector` fields set.

        Example usage:

        ```python
        res = index.query_many(
            queries=[
                {
                    "vector": [0.5, 0.4],
                    "top_k": 2,
                },
                {
                    "vector": [0.3, 0.2],
                },
            ]
        )
        ```

        ```python
        res = index.query_many(
            queries=[
                {
                    "data": "hello",
                    "top_k": 2,
                },
                {
                    "data": "world",
                },
            ]
        )
        ```
        """
        if len(queries) == 1:
            # handle this case separately, as the server returns a single
            # response when the length of the array is 1.
            query = queries[0]
            single_result = self.query(**query, namespace=namespace)
            return [single_result]

        has_vector_query, payload = convert_query_requests_to_payload(queries)
        path = QUERY_PATH if has_vector_query else QUERY_DATA_PATH
        result = self._execute_request(payload=payload, path=_path_for(namespace, path))

        return [
            [QueryResult._from_json(obj) for obj in query_result]
            for query_result in result
        ]

    def resumable_query(
        self,
        vector: Optional[Union[List[float], SupportsToList]] = None,
        top_k: int = 10,
        include_vectors: bool = False,
        include_metadata: bool = False,
        filter: str = "",
        data: Optional[str] = None,
        namespace: str = DEFAULT_NAMESPACE,
        include_data: bool = False,
        max_idle: int = 3600,
    ) -> Tuple[ResumableQuery, List[QueryResult]]:
        """
        Creates a resumable query and returns the query object along with initial results.

        :param vector: The vector value to query.
        :param top_k: How many vectors will be returned as the query result.
        :param include_vectors: Whether the resulting vectors will have their vector values or not.
        :param include_metadata: Whether the resulting vectors will have their metadata or not.
        :param filter: Filter expression to narrow down the query results.
        :param data: Data to query for (after embedding it to a vector)
        :param namespace: The namespace to use. When not specified, the default namespace is used.
        :param include_data: Whether the resulting vectors will have their unstructured data or not.
        :param max_idle: Maximum idle time for the resumable query in seconds.

        :return: A tuple containing the ResumableQuery object and the initial query results.

        Example usage:

        ```python
        query, initial_results = index.resumable_query(
            vector=[0.6, 0.9],
            top_k=100,
            include_vectors=False,
            include_metadata=True,
            max_idle=7200
        )
        print(initial_results)
        # Fetch more results in batches
        batch1 = query.fetch_next(10)
        batch2 = query.fetch_next(20)
        query.stop()
        ```
        """
        payload = {
            "topK": top_k,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
            "includeData": include_data,
            "filter": filter,
            "maxIdle": max_idle,
        }

        if data is None and vector is None:
            raise ClientError("either `data` or `vector` values must be given")
        if data is not None and vector is not None:
            raise ClientError(
                "`data` and `vector` values cannot be given at the same time"
            )

        if data is not None:
            payload["data"] = data
        else:
            payload["vector"] = convert_to_list(vector)

        query = ResumableQuery(payload, self, namespace)
        initial_results = query._start()
        return query, initial_results

    def delete(
        self,
        ids: Union[str, List[str]],
        namespace: str = DEFAULT_NAMESPACE,
    ) -> DeleteResult:
        """
        Deletes the given vector(s) with given ids.

        Response contains deleted vector count.

        :param ids: Singular or list of ids of vector(s) to be deleted.
        :param namespace: The namespace to use. When not specified, the default namespace is used.

        Example usage:

        ```python
        # deletes vectors with ids "0", "1", "2"
        index.delete(["0", "1", "2"])

        # deletes single vector
        index.delete("0")
        ```
        """
        if not isinstance(ids, list):
            ids = [ids]

        return DeleteResult._from_json(
            self._execute_request(payload=ids, path=_path_for(namespace, DELETE_PATH))
        )

    def reset(self, namespace: str = DEFAULT_NAMESPACE, all: bool = False) -> str:
        """
        Resets a namespace of an index. All vectors are removed for that namespace.

        :param namespace: The namespace to use. When not specified, the default namespace is used.
        :param all: When set to `True`, resets all namespaces of an index.

        Example usage:

        ```python
        index.reset()
        ```
        """
        if all:
            path = RESET_ALL_PATH
        else:
            path = _path_for(namespace, RESET_PATH)

        return self._execute_request(path=path, payload=None)

    def range(
        self,
        cursor: str = "",
        limit: int = 1,
        include_vectors: bool = False,
        include_metadata: bool = False,
        namespace: str = DEFAULT_NAMESPACE,
        include_data: bool = False,
    ) -> RangeResult:
        """
        Scans the vectors starting from `cursor`, returns at most `limit` many vectors.

        :param cursor: Marker that indicates where the scanning was left off when running through all existing vectors.
        :param limit: Limits how many vectors will be fetched with the request.
        :param include_vectors: Whether the resulting `top_k` vectors will have their vector values or not.
        :param include_metadata: Whether the resulting `top_k` vectors will have their metadata or not.
        :param namespace: The namespace to use. When not specified, the default namespace is used.
        :param include_data: Whether the resulting `top_k` vectors will have their unstructured data or not.

        Example usage:

        ```python
        res = index.range(cursor="", limit=100, include_vectors=False, include_metadata=True)
        ```
        """
        if limit <= 0:
            raise ClientError("limit must be greater than 0")

        payload = {
            "cursor": cursor,
            "limit": limit,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
            "includeData": include_data,
        }
        return RangeResult._from_json(
            self._execute_request(
                payload=payload, path=_path_for(namespace, RANGE_PATH)
            )
        )

    def fetch(
        self,
        ids: Union[str, List[str]],
        include_vectors: bool = False,
        include_metadata: bool = False,
        namespace: str = DEFAULT_NAMESPACE,
        include_data: bool = False,
    ) -> List[Optional[FetchResult]]:
        """
        Fetches details of a set of vectors.

        :param ids: List of vector ids to fetch details of.
        :param include_vectors: Whether the resulting vectors will have their vector values or not.
        :param include_metadata: Whether the resulting vectors will have their metadata or not.
        :param namespace: The namespace to use. When not specified, the default namespace is used.
        :param include_data: Whether the resulting `top_k` vectors will have their unstructured data or not.

        Example usage:

        ```python
        res = index.fetch(["id1", "id2"], include_vectors=False, include_metadata=True)
        ```
        """
        if not isinstance(ids, list):
            ids = [ids]

        payload = {
            "ids": ids,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
            "includeData": include_data,
        }
        return [
            FetchResult._from_json(vector) if vector else None
            for vector in self._execute_request(
                payload=payload, path=_path_for(namespace, FETCH_PATH)
            )
        ]

    def update(
        self,
        id: str,
        vector: Optional[List[float]] = None,
        data: Optional[str] = None,
        metadata: Optional[Dict] = None,
        namespace: str = DEFAULT_NAMESPACE,
        metadata_update_mode: MetadataUpdateMode = MetadataUpdateMode.OVERWRITE,
    ) -> bool:
        """
        Updates a vector value, data, or metadata for the given id.

        :param id: The vector id to update.
        :param vector: The vector value to update to.
        :param data: The raw text data to embed into a vector and update to.
        :param metadata: The metadata to update to.
        :param namespace: The namespace to use. When not specified, the default namespace is used.
        :param metadata_update_mode: Whether to overwrite the whole
            it, or patch the metadata (insert new fields or update
            according to the `RFC 7396 JSON Merge Patch` algorithm.

        Example usage:

        ```python
        updated = index.update("id1", metadata={"new_field": "new_value"})
        ```
        """
        payload: Dict[str, Any] = {
            "id": id,
            "metadataUpdateMode": metadata_update_mode.value,
        }

        if vector is not None:
            payload["vector"] = vector

        if data is not None:
            payload["data"] = data

        if metadata is not None:
            payload["metadata"] = metadata

        result = self._execute_request(
            payload=payload, path=_path_for(namespace, UPDATE_PATH)
        )
        updated = result["updated"]
        return updated == 1

    def info(self) -> InfoResult:
        """
        Returns the index info, including:

        * Total number of vectors across all namespaces
        * Total number of vectors waiting to be indexed across all namespaces
        * Total size of the index on disk in bytes
        * Vector dimension
        * Similarity function used
        * Per-namespace vector and pending vector counts
        """
        return InfoResult._from_json(
            self._execute_request(payload=None, path=INFO_PATH)
        )

    def list_namespaces(self) -> List[str]:
        """
        Returns the list of names of namespaces.
        """
        return self._execute_request(payload=None, path=LIST_NAMESPACES_PATH)

    def delete_namespace(self, namespace: str) -> None:
        """
        Deletes the given namespace if it exists, or raises
        exception if no such namespace exists.
        """
        self._execute_request(
            payload=None, path=_path_for(namespace, DELETE_NAMESPACE_PATH)
        )


class AsyncIndexOperations:
    async def _execute_request_async(self, payload, path):
        raise NotImplementedError("execute_request")

    async def upsert(
        self,
        vectors: Sequence[Union[Dict, tuple, Vector, Data]],
        namespace: str = DEFAULT_NAMESPACE,
    ) -> str:
        """
        Upserts(update or insert) vectors.

        :param vectors: The list vectors to upsert.
        :param namespace: The namespace to use. When not specified, the default namespace is used.

        There are various ways to upsert vectors.

        Example usages:

        ```python
        res = await index.upsert(
            vectors=[
                ("id1", [0.1, 0.2], {"metadata_field": "metadata_value"}, "data-value"),
                ("id2", [0.2, 0.2], {"metadata_field": "metadata_value"}),
                ("id3", [0.3,0.4]),
            ]
        )
        ```

        ```python
        res = await index.upsert(
            vectors=[
                {"id": "id4", "vector": [0.1, 0.2], "metadata": {"field": "value"}, "data": "data-value"},
                {"id": "id5", "vector": [0.2, 0.2], "metadata": {"field": "value"}},
                {"id": "id6", "vector": [0.5, 0.6]},
            ]
        )
        ```

        ```python
        from upstash_vector import Vector
        res = await index.upsert(
            vectors=[
                Vector(id="id7", vector=[0.1, 0.2], metadata={"field": "value"}, data="data-value"),
                Vector(id="id8", vector=[0.1, 0.2], metadata={"field": "value"}),
                Vector(id="id9", vector=[0.6, 0.7]),
            ]
        )
        ```

        ```python
        from upstash_vector import Data
        res = await index.upsert(
            vectors=[
                Data(id="id5", data="Goodbye World", metadata={"field": "value"}),
                Data(id="id6", data="Hello World"),
            ]
        ```

        Also, vectors or data can be upserted into particular namespaces of the index by
        providing a name for the `namespace` parameter. When no namespace is provided,
        the default namespace is used.

        ```python
        res = index.upsert(
            vectors=[
                ("id1", [0.1, 0.2]),
                ("id2", [0.3, 0.4]),
            ],
            namespace="ns",
        )
        ```
        """
        vectors = convert_to_vectors(vectors)
        payload, is_vector = convert_to_payload(vectors)
        path = UPSERT_PATH if is_vector else UPSERT_DATA_PATH

        return await self._execute_request_async(
            payload=payload, path=_path_for(namespace, path)
        )

    async def query(
        self,
        vector: Optional[Union[List[float], SupportsToList]] = None,
        top_k: int = 10,
        include_vectors: bool = False,
        include_metadata: bool = False,
        filter: str = "",
        data: Optional[str] = None,
        namespace: str = DEFAULT_NAMESPACE,
        include_data: bool = False,
    ) -> List[QueryResult]:
        """
        Query `top_k` many similar vectors.
        Requires either `data` or `vector` parameter.
        Raises exception if both `data` and `vector` parameters are used.

        :param vector: The vector value to query.
        :param top_k: How many vectors will be returned as the query result.
        :param include_vectors: Whether the resulting `top_k` vectors will have their vector values or not.
        :param include_metadata: Whether the resulting `top_k` vectors will have their metadata or not.
        :param filter: Filter expression to narrow down the query results.
        :param data: Data to query for (after embedding it to a vector)
        :param namespace: The namespace to use. When not specified, the default namespace is used.
        :param include_data: Whether the resulting `top_k` vectors will have their unstructured data or not.

        Example usage:

        ```python
        res = await index.query(
            vector=[0.6, 0.9],
            top_k=5,
            include_vectors=False,
            include_metadata=True,
        )
        ```

        ```python
        res = await index.query(
            data="hello",
            top_k=5,
            include_vectors=False,
            include_metadata=True,
        )
        ```
        """
        payload = {
            "topK": top_k,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
            "includeData": include_data,
            "filter": filter,
        }

        if data is None and vector is None:
            raise ClientError("either `data` or `vector` values must be given")
        if data is not None and vector is not None:
            raise ClientError(
                "`data` and `vector` values cannot be given at the same time"
            )

        if data is not None:
            payload["data"] = data
            path = QUERY_DATA_PATH
        else:
            payload["vector"] = convert_to_list(vector)
            path = QUERY_PATH

        return [
            QueryResult._from_json(obj)
            for obj in await self._execute_request_async(
                payload=payload, path=_path_for(namespace, path)
            )
        ]

    async def query_many(
        self,
        *,
        queries: List[QueryRequest],
        namespace: str = DEFAULT_NAMESPACE,
    ) -> List[List[QueryResult]]:
        """
        Makes a batch query request.

        The batch should only contain elements whose `data`
        or `vector` fields set.

        Example usage:

        ```python
        res = await index.query_many(
            queries=[
                {
                    "vector": [0.5, 0.4],
                    "top_k": 2,
                },
                {
                    "vector": [0.3, 0.2],
                },
            ]
        )
        ```

        ```python
        res = await index.query_many(
            queries=[
                {
                    "data": "hello",
                    "top_k": 2,
                },
                {
                    "data": "world",
                },
            ]
        )
        ```
        """
        if len(queries) == 1:
            # handle this case separately, as the server returns a single
            # response when the length of the array is 1.
            query = queries[0]
            single_result = await self.query(**query, namespace=namespace)
            return [single_result]

        has_vector_query, payload = convert_query_requests_to_payload(queries)
        path = QUERY_PATH if has_vector_query else QUERY_DATA_PATH
        result = await self._execute_request_async(
            payload=payload, path=_path_for(namespace, path)
        )

        return [
            [QueryResult._from_json(obj) for obj in query_result]
            for query_result in result
        ]

    async def resumable_query(
        self,
        vector: Optional[Union[List[float], SupportsToList]] = None,
        top_k: int = 10,
        include_vectors: bool = False,
        include_metadata: bool = False,
        filter: str = "",
        data: Optional[str] = None,
        namespace: str = DEFAULT_NAMESPACE,
        include_data: bool = False,
        max_idle: int = 3600,
    ) -> Tuple[ResumableQuery, List[QueryResult]]:
        """
        Creates a resumable query and returns the query object along with initial results.

        :param vector: The vector value to query.
        :param top_k: How many vectors will be returned as the query result.
        :param include_vectors: Whether the resulting vectors will have their vector values or not.
        :param include_metadata: Whether the resulting vectors will have their metadata or not.
        :param filter: Filter expression to narrow down the query results.
        :param data: Data to query for (after embedding it to a vector)
        :param namespace: The namespace to use. When not specified, the default namespace is used.
        :param include_data: Whether the resulting vectors will have their unstructured data or not.
        :param max_idle: Maximum idle time for the resumable query in seconds.

        :return: A tuple containing the ResumableQuery object and the initial query results.

        Example usage:

        ```python
        query, initial_results = await index.resumable_query(
            vector=[0.6, 0.9],
            top_k=100,
            include_vectors=False,
            include_metadata=True,
            max_idle=7200
        )
        print(initial_results)
        # Fetch more results in batches
        batch1 = await query.fetch_next(10)
        batch2 = await query.fetch_next(20)
        await query.stop()
        ```
        """
        payload = {
            "topK": top_k,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
            "includeData": include_data,
            "filter": filter,
            "maxIdle": max_idle,
        }

        if data is None and vector is None:
            raise ClientError("either `data` or `vector` values must be given")
        if data is not None and vector is not None:
            raise ClientError(
                "`data` and `vector` values cannot be given at the same time"
            )

        if data is not None:
            payload["data"] = data
        else:
            payload["vector"] = convert_to_list(vector)

        query = ResumableQuery(payload, self, namespace)
        initial_results = await query._async_start()
        return query, initial_results

    async def delete(
        self,
        ids: Union[str, List[str]],
        namespace: str = DEFAULT_NAMESPACE,
    ) -> DeleteResult:
        """
        Deletes the given vector(s) with given ids asynchronously.

        Response contains deleted vector count.

        :param ids: Singular or list of ids of vector(s) to be deleted.
        :param namespace: The namespace to use. When not specified, the default namespace is used.

        Example usage:

        ```python
        # deletes vectors with ids "0", "1", "2"
        await index.delete(["0", "1", "2"])

        # deletes single vector
        await index.delete("0")
        ```
        """
        if not isinstance(ids, list):
            ids = [ids]

        return DeleteResult._from_json(
            await self._execute_request_async(
                payload=ids, path=_path_for(namespace, DELETE_PATH)
            )
        )

    async def reset(self, namespace: str = DEFAULT_NAMESPACE, all: bool = False) -> str:
        """
        Resets a namespace of an index. All vectors are removed for that namespace.

        :param namespace: The namespace to use. When not specified, the default namespace is used.
        :param all: When set to `True`, resets all namespaces of an index.

        Example usage:

        ```python
        await index.reset()
        ```
        """
        if all:
            path = RESET_ALL_PATH
        else:
            path = _path_for(namespace, RESET_PATH)

        return await self._execute_request_async(path=path, payload=None)

    async def range(
        self,
        cursor: str = "",
        limit: int = 1,
        include_vectors: bool = False,
        include_metadata: bool = False,
        namespace: str = DEFAULT_NAMESPACE,
        include_data: bool = False,
    ) -> RangeResult:
        """
        Scans the vectors asynchronously starting from `cursor`, returns at most `limit` many vectors.

        :param cursor: Marker that indicates where the scanning was left off when running through all existing vectors.
        :param limit: Limits how many vectors will be fetched with the request.
        :param include_vectors: Whether the resulting `top_k` vectors will have their vector values or not.
        :param include_metadata: Whether the resulting `top_k` vectors will have their metadata or not.
        :param namespace: The namespace to use. When not specified, the default namespace is used.
        :param include_data: Whether the resulting `top_k` vectors will have their unstructured data or not.

        Example usage:

        ```python
        res = await index.range(cursor="cursor", limit=4, include_vectors=False, include_metadata=True)
        ```
        """
        if limit <= 0:
            raise ClientError("limit must be greater than 0")

        payload = {
            "cursor": cursor,
            "limit": limit,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
            "includeData": include_data,
        }
        return RangeResult._from_json(
            await self._execute_request_async(
                payload=payload, path=_path_for(namespace, RANGE_PATH)
            )
        )

    async def fetch(
        self,
        ids: Union[str, List[str]],
        include_vectors: bool = False,
        include_metadata: bool = False,
        namespace: str = DEFAULT_NAMESPACE,
        include_data: bool = False,
    ) -> List[Optional[FetchResult]]:
        """
        Fetches details of a set of vectors asynchronously.

        :param ids: List of vector ids to fetch details of.
        :param include_vectors: Whether the resulting vectors will have their vector values or not.
        :param include_metadata: Whether the resulting vectors will have their metadata or not.
        :param namespace: The namespace to use. When not specified, the default namespace is used.
        :param include_data: Whether the resulting `top_k` vectors will have their unstructured data or not.

        Example usage:

        ```python
        res = await index.fetch(["id1", "id2"], include_vectors=False, include_metadata=True)
        ```
        """
        if not isinstance(ids, list):
            ids = [ids]

        payload = {
            "ids": ids,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
            "includeData": include_data,
        }
        return [
            FetchResult._from_json(vector) if vector else None
            for vector in await self._execute_request_async(
                payload=payload, path=_path_for(namespace, FETCH_PATH)
            )
        ]

    async def update(
        self,
        id: str,
        vector: Optional[List[float]] = None,
        data: Optional[str] = None,
        metadata: Optional[Dict] = None,
        namespace: str = DEFAULT_NAMESPACE,
        metadata_update_mode: MetadataUpdateMode = MetadataUpdateMode.OVERWRITE,
    ) -> bool:
        """
        Updates a vector value, data, or metadata for the given id.

        :param id: The vector id to update.
        :param vector: The vector value to update to.
        :param data: The raw text data to embed into a vector and update to.
        :param metadata: The metadata to update to.
        :param namespace: The namespace to use. When not specified, the default namespace is used.
        :param metadata_update_mode: Whether to overwrite the whole
            it, or patch the metadata (insert new fields or update
            according to the `RFC 7396 JSON Merge Patch` algorithm.

        Example usage:

        ```python
        updated = await index.update("id1", metadata={"new_field": "new_value"})
        ```
        """
        payload: Dict[str, Any] = {
            "id": id,
            "metadataUpdateMode": metadata_update_mode.value,
        }

        if vector is not None:
            payload["vector"] = vector

        if data is not None:
            payload["data"] = data

        if metadata is not None:
            payload["metadata"] = metadata

        result = await self._execute_request_async(
            payload=payload, path=_path_for(namespace, UPDATE_PATH)
        )
        updated = result["updated"]
        return updated == 1

    async def info(self) -> InfoResult:
        """
        Returns the index info asynchronously, including:

        * Total number of vectors across all namespaces
        * Total number of vectors waiting to be indexed across all namespaces
        * Total size of the index on disk in bytes
        * Vector dimension
        * Similarity function used
        * Per-namespace vector and pending vector counts
        """
        return InfoResult._from_json(
            await self._execute_request_async(payload=None, path=INFO_PATH)
        )

    async def list_namespaces(self) -> List[str]:
        """
        Returns the list of names of namespaces.
        """
        result = await self._execute_request_async(
            payload=None, path=LIST_NAMESPACES_PATH
        )
        return result

    async def delete_namespace(self, namespace: str) -> None:
        """
        Deletes the given namespace if it exists, or raises
        exception if no such namespace exists.
        """
        if namespace == DEFAULT_NAMESPACE:
            raise ClientError("Cannot delete the default namespace")

        await self._execute_request_async(
            payload=None, path=_path_for(namespace, DELETE_NAMESPACE_PATH)
        )
