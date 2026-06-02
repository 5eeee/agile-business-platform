"""Elasticsearch-сервис для полнотекстового поиска по чату (ТЗ 3.9.5)"""
import logging
from typing import Optional
try:
    from elasticsearch import AsyncElasticsearch
except ImportError:
    AsyncElasticsearch = None  # type: ignore
from app.config import settings

logger = logging.getLogger(__name__)

INDEX_NAME = "chat_messages"

MAPPING = {
    "mappings": {
        "properties": {
            "message_id": {"type": "keyword"},
            "iteration_id": {"type": "keyword"},
            "user_id": {"type": "keyword"},
            "user_name": {"type": "text", "analyzer": "russian"},
            "content": {
                "type": "text",
                "analyzer": "russian",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "created_at": {"type": "date"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
}

_client: Optional[AsyncElasticsearch] = None  # type: ignore

def _es_disabled() -> bool:
    """Check if Elasticsearch is disabled (no URL or no library)."""
    url = getattr(settings, "ELASTICSEARCH_URL", "")
    return AsyncElasticsearch is None or not url


async def get_es() -> Optional[AsyncElasticsearch]:  # type: ignore
    global _client
    if _es_disabled():
        return None
    if _client is None:
        _client = AsyncElasticsearch(settings.ELASTICSEARCH_URL, retry_on_timeout=False, max_retries=0)
    return _client


async def close_es():
    """Close Elasticsearch client on shutdown"""
    global _client
    if _client is not None:
        await _client.close()
        _client = None


async def ensure_index():
    es = await get_es()
    if es is None:
        return
    try:
        exists = await es.indices.exists(index=INDEX_NAME)
        if not exists:
            await es.indices.create(index=INDEX_NAME, body=MAPPING)
            logger.info("Created Elasticsearch index: %s", INDEX_NAME)
    except Exception as e:
        logger.warning("Elasticsearch index check failed: %s", e)


async def index_message(message_id: str, iteration_id: str, user_id: str, user_name: str, content: str, created_at):
    es = await get_es()
    if es is None:
        return
    try:
        await es.index(
            index=INDEX_NAME,
            id=message_id,
            document={
                "message_id": message_id,
                "iteration_id": iteration_id,
                "user_id": user_id,
                "user_name": user_name,
                "content": content,
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
            },
        )
    except Exception as e:
        logger.warning("Failed to index message %s: %s", message_id, e)


async def delete_message(message_id: str):
    es = await get_es()
    if es is None:
        return
    try:
        await es.delete(index=INDEX_NAME, id=message_id, ignore=[404])
    except Exception as e:
        logger.warning("Failed to delete message %s from index: %s", message_id, e)


async def search_messages(query: str, iteration_id: Optional[str] = None, limit: int = 20):
    es = await get_es()
    if es is None:
        return []
    must = [{"match": {"content": {"query": query, "fuzziness": "AUTO"}}}]
    if iteration_id:
        must.append({"term": {"iteration_id": iteration_id}})
    try:
        result = await es.search(
            index=INDEX_NAME,
            body={
                "query": {"bool": {"must": must}},
                "sort": [{"created_at": "desc"}],
                "size": limit,
            },
        )
        hits = result.get("hits", {}).get("hits", [])
        return [
            {
                "message_id": h["_source"]["message_id"],
                "iteration_id": h["_source"]["iteration_id"],
                "user_id": h["_source"]["user_id"],
                "user_name": h["_source"].get("user_name"),
                "content": h["_source"]["content"],
                "created_at": h["_source"]["created_at"],
                "score": h["_score"],
            }
            for h in hits
        ]
    except Exception as e:
        logger.warning("Elasticsearch search failed: %s", e)
        return []
