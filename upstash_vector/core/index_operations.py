# Define vector operations here:
# Upsert and query functions and signatures

from typing import Sequence, Union, List, Dict, Optional
from upstash_vector.errors import ClientError
from upstash_vector.types import (
    Data,
    DeleteResult,
    RangeResult,
    InfoResult,
    SupportsToList,
    FetchResult,
    QueryResult,
    Vector,
)

from upstash_vector.utils import convert_to_list, convert_to_vectors, convert_to_payload

UPSERT_PATH = "/upsert"
UPSERT_DATA_PATH = "/upsert-data"
QUERY_PATH = "/query"
QUERY_DATA_PATH = "/query-data"
DELETE_PATH = "/delete"
RESET_PATH = "/reset"
RANGE_PATH = "/range"
FETCH_PATH = "/fetch"
INFO_PATH = "/info"


class IndexOperations:
    def _execute_request(self, payload, path):
        raise NotImplementedError("execute_request")

    def upsert(
        self,
        vectors: Sequence[Union[Dict, tuple, Vector, Data]],
    ) -> str:
        """
        Upserts(update or insert) vectors. There are 3 ways to upsert vectors.

        Example usages:

        ```python
        res = index.upsert(
            vectors=[
                ("id1", [0.1, 0.2], {"metadata_field": "metadata_value"}),
                ("id2", [0.3,0.4])
            ]
        )

        # OR

        res = index.upsert(
            vectors=[
                {"id": "id3", "vector": [0.1, 0.2], "metadata": {"metadata_f": "metadata_v"}},
                {"id": "id4", "vector": [0.5, 0.6]},
            ]
        )

        # OR

        from upstash_vector import Vector
        res = index.upsert(
            vectors=[
                Vector(id="id5", vector=[1, 2], metadata={"metadata_f": "metadata_v"}),
                Vector(id="id6", vector=[6, 7]),
            ]
        )
        ```

        #OR

        ```python
        from upstash_vector import Data
        res = index.upsert(
            vectors=[
                Data(id="id5", data="Goodbye-World", metadata={"metadata_f": "metadata_v"}),
                Data(id="id6", data="Hello-World"),
            ]
        )
        ```
        """

        vectors = convert_to_vectors(vectors)
        payload, is_vector = convert_to_payload(vectors)
        path = UPSERT_PATH if is_vector else UPSERT_DATA_PATH

        return self._execute_request(payload=payload, path=path)

    def query(
        self,
        vector: Optional[Union[List[float], SupportsToList]] = None,
        top_k: int = 10,
        include_vectors: bool = False,
        include_metadata: bool = False,
        filter: str = "",
        data: Optional[str] = None,
    ) -> List[QueryResult]:
        """
        Query `top_k` many similar vectors. Requires either `data` or `vector` fields. Raises exception if `data` and `vector` fields are both used.

        :param vector: list of floats for the values of vector.
        :param top_k: number that indicates how many vectors will be returned as the query result.
        :param include_vectors: bool value that indicates whether the resulting top_k vectors will have their vector values shown.
        :param include_metadata: bool value that indicates whether the resulting top_k vectors will have their metadata shown.
        :param filter: filter expression to narrow down the query results.
        :param data: string (to be embedded) to query for

        Example usage:

        ```python
        query_res = index.query(
            vector=[0.6, 0.9],
            top_k=3,
            include_vectors=True,
            include_metadata=True,
        )
        ```

        ```python
        query_res = index.query(
            data="hello"
            top_k=3,
            include_vectors=True,
            include_metadata=True,
        )
        ```
        """
        payload = {
            "topK": top_k,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
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
            for obj in self._execute_request(payload=payload, path=path)
        ]

    def delete(self, ids: Union[str, List[str]]) -> DeleteResult:
        """
        Deletes the given vector(s) with given ids.

        Response contains deleted vector count.

        :param ids: Singular or list of ids of vector(s) to be deleted.

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
            self._execute_request(payload=ids, path=DELETE_PATH)
        )

    def reset(self) -> str:
        """
        Resets the index. All vectors are removed.

        Example usage:

        ```python
        index.reset()
        ```
        """
        return self._execute_request(path=RESET_PATH, payload=None)

    def range(
        self,
        cursor: str = "",
        limit: int = 1,
        include_vectors: bool = False,
        include_metadata: bool = False,
    ) -> RangeResult:
        """
        Scans the vectors starting from `cursor`, returns at most `limit` many vectors.

        :param cursor: marker that indicates where the scanning was left off when running through all existing vectors.
        :param limit: limits how many vectors will be fetched with the request.
        :param include_vectors: bool value that indicates whether the resulting top_k vectors will have their vector values shown.
        :param include_metadata: bool value that indicates whether the resulting top_k vectors will have their metadata shown.

        Example usage:

        ```python
        res = index.range(cursor="cursor", limit=4, include_vectors=True, include_metadata=True)
        ```
        """
        if limit <= 0:
            raise ClientError("limit must be greater than 0")

        payload = {
            "cursor": cursor,
            "limit": limit,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
        }
        return RangeResult._from_json(
            self._execute_request(payload=payload, path=RANGE_PATH)
        )

    def fetch(
        self,
        ids: Union[str, List[str]],
        include_vectors: bool = False,
        include_metadata: bool = False,
    ) -> List[Optional[FetchResult]]:
        """
        Fetches details of a set of vectors.

        :param ids: List of vector ids to fetch details of.
        :param include_vectors: bool value that indicates whether the resulting top_k vectors will have their vector values shown.
        :param include_metadata: bool value that indicates whether the resulting top_k vectors will have their metadata shown.

        Example usage:

        ```python
        res = index.fetch(["id1", "id2"], include_vectors=True, include_metadata=True)
        ```
        """
        if not isinstance(ids, list):
            ids = [ids]

        payload = {
            "ids": ids,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
        }
        return [
            FetchResult._from_json(vector) if vector else None
            for vector in self._execute_request(payload=payload, path=FETCH_PATH)
        ]

    def info(self) -> InfoResult:
        """
        Returns the index info, including:

        * total number of vectors
        * total number of vectors waiting to be indexed
        * total size of the index on disk in bytes
        * dimension count for the index
        * similarity function selected for the index
        """
        return InfoResult._from_json(
            self._execute_request(payload=None, path=INFO_PATH)
        )


class AsyncIndexOperations:
    async def _execute_request_async(self, payload, path):
        raise NotImplementedError("execute_request")

    async def upsert(
        self,
        vectors: Sequence[Union[Dict, tuple, Vector, Data]],
    ) -> str:
        """
        Upserts(update or insert) vectors asynchronously. There are 3 ways to upsert vectors.

        Example usages:

        ```python
        res = await index.upsert(
            vectors=[
                ("id1", [0.1, 0.2], {"metadata_field": "metadata_value"}),
                ("id2", [0.3,0.4])
            ]
        )

        # OR

        res = await index.upsert(
            vectors=[
                {"id": "id3", "vector": [0.1, 0.2], "metadata": {"metadata_f": "metadata_v"}},
                {"id": "id4", "vector": [0.5, 0.6]},
            ]
        )

        # OR

        ```python
        from upstash_vector import Vector
        res = await index.upsert(
            vectors=[
                Vector(id="id5", vector=[1, 2], metadata={"metadata_f": "metadata_v"}),
                Vector(id="id6", vector=[6, 7]),
            ]
        )
        ```

        # OR

        ```python
        from upstash_vector import Data
        res = await index.upsert(
            vectors=[
                Data(id="id5", data="Goodbye-World", metadata={"metadata_f": "metadata_v"}),
                Data(id="id6", data="Hello-World"),
            ]
        )
        ```
        """
        vectors = convert_to_vectors(vectors)
        payload, is_vector = convert_to_payload(vectors)
        path = UPSERT_PATH if is_vector else UPSERT_DATA_PATH

        return await self._execute_request_async(payload=payload, path=path)

    async def query(
        self,
        vector: Optional[Union[List[float], SupportsToList]] = None,
        top_k: int = 10,
        include_vectors: bool = False,
        include_metadata: bool = False,
        filter: str = "",
        data: Optional[str] = None,
    ) -> List[QueryResult]:
        """
        Query `top_k` many similar vectors. Requires either `data` or `vector` fields. Raises exception if `data` and `vector` fields are both used.

        :param vector: list of floats for the values of vector.
        :param top_k: number that indicates how many vectors will be returned as the query result.
        :param include_vectors: bool value that indicates whether the resulting top_k vectors will have their vector values shown.
        :param include_metadata: bool value that indicates whether the resulting top_k vectors will have their metadata shown.
        :param filter: filter expression to narrow down the query results.
        :param data: string (to be embedded) to query for

        Example usage:

        ```python
        query_res = await index.query(
            vector=[0.6, 0.9],
            top_k=3,
            include_vectors=True,
            include_metadata=True,
        )
        ```

        ```python
        query_res = await index.query(
            data="hello"
            top_k=3,
            include_vectors=True,
            include_metadata=True,
        )
        ```
        """
        payload = {
            "topK": top_k,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
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
            for obj in await self._execute_request_async(payload=payload, path=path)
        ]

    async def delete(self, ids: Union[str, List[str]]) -> DeleteResult:
        """
        Deletes the given vector(s) with given ids asynchronously.

        Response contains deleted vector count.

        :param ids: Singular or list of ids of vector(s) to be deleted.

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
            await self._execute_request_async(payload=ids, path=DELETE_PATH)
        )

    async def reset(self) -> str:
        """
        Resets the index asynchronously. All vectors are removed.

        Example usage:

        ```python
        await index.reset()
        ```
        """
        return await self._execute_request_async(path=RESET_PATH, payload=None)

    async def range(
        self,
        cursor: str = "",
        limit: int = 1,
        include_vectors: bool = False,
        include_metadata: bool = False,
    ) -> RangeResult:
        """
        Scans the vectors asynchronously starting from `cursor`, returns at most `limit` many vectors.

        :param cursor: marker that indicates where the scanning was left off when running through all existing vectors.
        :param limit: limits how many vectors will be fetched with the request.
        :param include_vectors: bool value that indicates whether the resulting top_k vectors will have their vector values shown.
        :param include_metadata: bool value that indicates whether the resulting top_k vectors will have their metadata shown.

        Example usage:

        ```python
        res = await index.range(cursor="cursor", limit=4, include_vectors=True, include_metadata=True)
        ```
        """
        if limit <= 0:
            raise ClientError("limit must be greater than 0")

        payload = {
            "cursor": cursor,
            "limit": limit,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
        }
        return RangeResult._from_json(
            await self._execute_request_async(payload=payload, path=RANGE_PATH)
        )

    async def fetch(
        self,
        ids: Union[str, List[str]],
        include_vectors: bool = False,
        include_metadata: bool = False,
    ) -> List[Optional[FetchResult]]:
        """
        Fetches details of a set of vectors asynchronously.

        :param ids: List of vector ids to fetch details of.
        :param include_vectors: bool value that indicates whether the resulting top_k vectors will have their vector values shown.
        :param include_metadata: bool value that indicates whether the resulting top_k vectors will have their metadata shown.

        Example usage:

        ```python
        res = await index.fetch(["id1", "id2"], include_vectors=True, include_metadata=True)
        ```
        """
        if not isinstance(ids, list):
            ids = [ids]

        payload = {
            "ids": ids,
            "includeVectors": include_vectors,
            "includeMetadata": include_metadata,
        }
        return [
            FetchResult._from_json(vector) if vector else None
            for vector in await self._execute_request_async(
                payload=payload, path=FETCH_PATH
            )
        ]

    async def info(self) -> InfoResult:
        """
        Returns the index info asynchronously, including:

        * total number of vectors
        * total number of vectors waiting to be indexed
        * total size of the index on disk in bytes
        * dimension count for the index
        * similarity function selected for the index
        """
        return InfoResult._from_json(
            await self._execute_request_async(payload=None, path=INFO_PATH)
        )
