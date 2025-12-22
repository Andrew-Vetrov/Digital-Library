from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from sentence_transformers import SentenceTransformer
import numpy as np
import time
import uuid
import math

ES_INDEX = "books"
EMBEDDING_DIMS = 384
MAX_CHUNKS = 2

def get_es():
    for _ in range(20):
        try:
            es = Elasticsearch("http://elasticsearch:9200")
            es.info()
            return es
        except Exception:
            time.sleep(2)
    raise RuntimeError("Elasticsearch did not start")

es = get_es()

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
    return _model

def embed(text: str):
    vec = get_model().encode(text)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()

def split_text(text: str, parts: int):
    words = text.split()
    if not words:
        return []
    size = math.ceil(len(words) / parts)
    return [
        " ".join(words[i:i + size])
        for i in range(0, len(words), size)
    ][:parts]

def create_index():
    if es.indices.exists(index=ES_INDEX):
        return

    es.indices.create(
        index=ES_INDEX,
        body={
            "settings": {
                "analysis": {
                    "analyzer": {
                        "ru_en_analyzer": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "lowercase",
                                "russian_stop",
                                "russian_stemmer"
                            ]
                        }
                    },
                    "filter": {
                        "russian_stop": {
                            "type": "stop",
                            "stopwords": "_russian_"
                        },
                        "russian_stemmer": {
                            "type": "stemmer",
                            "language": "russian"
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "id": {"type": "keyword"},
                    "type": {"type": "keyword"},
                    "title": {
                        "type": "text",
                        "analyzer": "ru_en_analyzer"
                    },
                    "author": {
                        "type": "text",
                        "analyzer": "ru_en_analyzer"
                    },
                    "content": {
                        "type": "text",
                        "analyzer": "ru_en_analyzer"
                    },
                    "embedding": {
                        "type": "dense_vector",
                        "dims": EMBEDDING_DIMS,
                        "index": True,
                        "similarity": "cosine"
                    }
                }
            }
        }
    )


def index_book(title: str, author: str, content: str, book_id=None):
    if not book_id:
        book_id = str(uuid.uuid4())

    es.index(
        index=ES_INDEX,
        id=str(uuid.uuid4()),
        document={
            "doc_id": str(uuid.uuid4()),
            "id": book_id,
            "type": "title",
            "title": title,
            "author": author,
            "content": "",
            "embedding": embed(title)
        }
    )

    chunks = split_text(content, MAX_CHUNKS)
    for chunk in chunks:
        es.index(
            index=ES_INDEX,
            id=str(uuid.uuid4()),
            document={
                "doc_id": str(uuid.uuid4()),
                "id": book_id,
                "type": "content",
                "title": title,
                "author": author,
                "content": chunk,
                "embedding": embed(chunk)
            }
        )

    return book_id

def semantic_search(query: str, size=10, min_score=1.4):
    query_vector = embed(query)

    body = {
        "size": size,
        "min_score": min_score,
        "query": {
            "script_score": {
                "query": {"match_all": {}},
                "script": {
                    "source": "cosineSimilarity(params.qv, 'embedding') + 1.0",
                    "params": {"qv": query_vector}
                }
            }
        }
    }

    res = es.search(index=ES_INDEX, body=body)

    seen = set()
    results = []

    for hit in res["hits"]["hits"]:
        book_id = hit["_source"]["id"]
        if book_id not in seen:
            seen.add(book_id)
            results.append(hit["_source"])

    return results

def search_books(query: str, size=20):
    try:
        body = {
            "size": size,
            "query": {
                "bool": {
                    "should": [
                        {
                            "bool": {
                                "must": [
                                    {"term": {"type": "content"}},
                                    {"match_phrase": {"content": {"query": query, "boost": 5}}}
                                ]
                            }
                        },
                        {
                            "bool": {
                                "must": [
                                    {"term": {"type": "title"}},
                                    {"match_phrase": {"title": {"query": query, "boost": 6}}}
                                ]
                            }
                        },
                        {
                            "match": {
                                "title": {
                                    "query": query,
                                    "boost": 3,
                                    "operator": "and"
                                }
                            }
                        },
                        {
                            "match": {
                                "author": {
                                    "query": query,
                                    "boost": 2
                                }
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            }
        }

        res = es.search(index=ES_INDEX, body=body)

        seen = set()
        results = []

        for hit in res["hits"]["hits"]:
            book_id = hit["_source"]["id"]
            if book_id not in seen:
                seen.add(book_id)
                results.append(hit["_source"])

        return results

    except NotFoundError:
        return []
