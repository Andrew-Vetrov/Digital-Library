from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
import time
import uuid

ES_INDEX = "books"

def get_es():
    for i in range(20):
        try:
            es = Elasticsearch("http://elasticsearch:9200")
            es.info()
            return es
        except Exception as e:
            print("ES not ready, retry...", i)
            time.sleep(2)
    raise RuntimeError("Elasticsearch did not start")

es = get_es()


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
                            "filter": ["lowercase", "russian_stop", "russian_stemmer"]
                        }
                    },
                    "filter": {
                        "russian_stop": {"type": "stop", "stopwords": "_russian_"},
                        "russian_stemmer": {"type": "stemmer", "language": "russian"}
                    }
                }
            },
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "title": {"type": "text", "analyzer": "ru_en_analyzer"},
                    "author": {"type": "text", "analyzer": "ru_en_analyzer"},
                    "content": {"type": "text", "analyzer": "ru_en_analyzer"}
                }
            }
        }
    )


def index_book(title: str, author: str, content: str, book_id=None):
    if not book_id:
        book_id = str(uuid.uuid4())

    es.index(
        index=ES_INDEX,
        id=book_id,
        document={
            "id": book_id,
            "title": title,
            "author": author,
            "content": content
        }
    )
    return book_id


def search_books(query: str):
    try:
        body = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "match_phrase": {
                                "content": {
                                    "query": query,
                                    "boost": 5
                                }
                            }
                        },
                        {
                            "match_phrase": {
                                "title": {
                                    "query": query,
                                    "boost": 4
                                }
                            }
                        },
                        {
                            "match": {
                                "title": {
                                    "query": query,
                                    "boost": 3,
                                    "operator": "and",
                                    "fuzziness": 0
                                }
                            }
                        },
                        {
                            "match": {
                                "author": {
                                    "query": query,
                                    "boost": 2,
                                    "fuzziness": 0
                                }
                            }
                        },
                        {
                            "match": {
                                "content": {
                                    "query": query,
                                    "boost": 1,
                                    "operator": "and",
                                    "fuzziness": 0
                                }
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            }
        }

        res = es.search(index=ES_INDEX, body=body)
        return [hit["_source"] for hit in res["hits"]["hits"]]

    except NotFoundError:
        return []
