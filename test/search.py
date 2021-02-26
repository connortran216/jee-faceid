from core.search_client import SearchClient
from milvus import IndexType


if __name__ == '__main__':
    search_client = SearchClient()
    status= search_client.cursor.create_index('JFA_TEST', IndexType.IVF_FLAT, { 'nlist': 2048 })
    print(status.code)