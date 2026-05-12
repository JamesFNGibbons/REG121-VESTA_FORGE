"""Qdrant Cloud helpers: hybrid collection, payload indexes, upsert, hybrid search."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Sequence

from qdrant_client import QdrantClient, models
from tenacity import Retrying, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
# Default dense width for Qwen3-Embedding-4B (full MRL output); override with DENSE_VECTOR_SIZE / QdrantWrapper(dense_size=...).
DENSE_SIZE = 2560

POINT_NAMESPACE = uuid.UUID("018f3f24-7b3e-7f3a-8b0c-001122334455")

KEYWORD_INDEX_FIELDS: tuple[str, ...] = (
    "category",
    "forge_handler",
    "js_type",
    "js_complexity",
    "price_point_signal",
    "conversion_role",
    "layout_pattern",
)
FLOAT_INDEX_FIELDS: tuple[str, ...] = (
    "emotional_trust",
    "emotional_authority",
    "emotional_warmth",
    "usage_count",
    "acceptance_rate",
)


def point_id_for_catalogue_key(catalogue_id: str) -> str:
    return str(uuid.uuid5(POINT_NAMESPACE, catalogue_id))


class QdrantWrapper:
    def __init__(
        self,
        url: str,
        api_key: str,
        collection_name: str,
        *,
        max_retries: int = 3,
        dense_size: int | None = None,
    ) -> None:
        self._client = QdrantClient(url=url, api_key=api_key or None)
        self.collection_name = collection_name
        self._max_retries = max(1, max_retries)
        self.dense_size = int(dense_size) if dense_size is not None else DENSE_SIZE

    @property
    def client(self) -> QdrantClient:
        return self._client

    def ensure_collection(self) -> None:
        if self._client.collection_exists(self.collection_name):
            return
        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                DENSE_VECTOR_NAME: models.VectorParams(size=self.dense_size, distance=models.Distance.COSINE),
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: models.SparseVectorParams(on_disk=False),
            },
        )
        logger.info("Created Qdrant collection %s", self.collection_name)

    def ensure_payload_indexes(self) -> None:
        info = self._client.get_collection(self.collection_name)
        existing: set[str] = set()
        if info.payload_schema:
            existing = set(info.payload_schema.keys())

        for field in KEYWORD_INDEX_FIELDS:
            if field in existing:
                continue
            self._client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            logger.info("Created keyword payload index on %s", field)

        for field in FLOAT_INDEX_FIELDS:
            if field in existing:
                continue
            self._client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field,
                field_schema=models.PayloadSchemaType.FLOAT,
            )
            logger.info("Created float payload index on %s", field)

    def point_exists(self, catalogue_id: str) -> bool:
        pid = point_id_for_catalogue_key(catalogue_id)
        res = self._client.retrieve(
            collection_name=self.collection_name,
            ids=[pid],
            with_payload=False,
            with_vectors=False,
        )
        return len(res) > 0

    def upsert_component(
        self,
        *,
        catalogue_id: str,
        dense: Sequence[float],
        sparse_indices: Sequence[int],
        sparse_values: Sequence[float],
        payload: dict[str, Any],
    ) -> None:
        pid = point_id_for_catalogue_key(catalogue_id)
        if len(dense) != self.dense_size:
            raise ValueError(f"Dense vector must have length {self.dense_size}, got {len(dense)}")
        point = models.PointStruct(
            id=pid,
            vector={
                DENSE_VECTOR_NAME: list(dense),
                SPARSE_VECTOR_NAME: models.SparseVector(
                    indices=list(map(int, sparse_indices)),
                    values=list(map(float, sparse_values)),
                ),
            },
            payload=payload,
        )

        def _upsert() -> None:
            self._client.upsert(collection_name=self.collection_name, points=[point], wait=True)

        retrying = Retrying(
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
            stop=stop_after_attempt(self._max_retries),
            reraise=True,
        )
        retrying(_upsert)

    def collection_stats(self) -> dict[str, Any]:
        info = self._client.get_collection(self.collection_name)
        count = self._client.count(self.collection_name, exact=True).count
        vectors = info.config.params.vectors
        sparse_vectors = getattr(info.config.params, "sparse_vectors", None)
        return {
            "name": self.collection_name,
            "points_count": count,
            "dense_config": vectors,
            "sparse_vectors_config": sparse_vectors,
            "payload_schema": info.payload_schema,
        }

    def hybrid_search(
        self,
        *,
        dense_query: Sequence[float],
        sparse_indices: Sequence[int],
        sparse_values: Sequence[float],
        limit: int = 10,
        category: str | None = None,
    ) -> list[models.ScoredPoint]:
        q_filter: models.Filter | None = None
        if category:
            q_filter = models.Filter(
                must=[models.FieldCondition(key="category", match=models.MatchValue(value=category))]
            )

        sparse_vec = models.SparseVector(
            indices=list(map(int, sparse_indices)),
            values=list(map(float, sparse_values)),
        )
        prefetch = [
            models.Prefetch(
                query=models.NearestQuery(nearest=list(map(float, dense_query))),
                using=DENSE_VECTOR_NAME,
                limit=50,
            ),
            models.Prefetch(
                query=sparse_vec,
                using=SPARSE_VECTOR_NAME,
                limit=50,
            ),
        ]

        res = self._client.query_points(
            collection_name=self.collection_name,
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            query_filter=q_filter,
            with_payload=True,
        )
        return list(res.points)

    def scroll_sample(self, *, limit: int = 1) -> list[models.Record]:
        records, _ = self._client.scroll(
            collection_name=self.collection_name,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return list(records)

    def count_points_by_forge_handler(self) -> dict[str, int]:
        """Aggregate ingested points by payload forge_handler (full scroll)."""
        from collections import Counter

        counts: Counter[str] = Counter()
        offset = None
        while True:
            records, offset = self._client.scroll(
                collection_name=self.collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for r in records:
                pl = r.payload or {}
                h = str(pl.get("forge_handler") or "(none)")
                counts[h] += 1
            if offset is None:
                break
        return dict(counts)
