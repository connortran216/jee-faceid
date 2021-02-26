import os
from pymongo import MongoClient
from milvus import Milvus, MetricType, IndexType


if __name__ == '__main__':
    search_client = Milvus(**{
        'host': os.environ.get('MILVUS_HOST', '34.87.149.106'),
        'port': int(os.environ.get('MILVUS_PORT', 19530))
    })

    _search_client = Milvus(**{
        'host': os.environ.get('MILVUS_HOST', '202.143.110.156'),
        'port': int(os.environ.get('MILVUS_PORT', 9090))
    })

    connector = MongoClient('mongodb://{}:{}@{}:{}'.format(
        os.environ.get('MONGODB_USER', 'dps'),
        os.environ.get('MONGODB_PASSWORD', 'dps123'),
        os.environ.get('MONGODB_HOST', '34.87.149.106'),  # TODO: why can not get env
        os.environ.get('MONGODB_PORT', '27017')
    ))
    database = connector[os.environ.get('MONGODB_DATABASE', 'JFA')]

    _connector = MongoClient('mongodb://{}:{}@{}:{}'.format(
        'dps', 'dps123', '202.143.110.156', '9092'
    ))
    _connector.drop_database('JFA')
    _database = _connector['JFA']
    _companies = _database['JFA_Companies']

    companies = database['JFA_Companies']
    for company in companies.find():
        company_id = company['_id']
        print(f'Loaded into company {company_id}')

        if not _search_client.has_collection(f'JFA_Company_{company_id}')[1]:
            _search_client.create_collection({
                'collection_name': f'JFA_Company_{company_id}',
                'dimension': 512,
                'index_file_size': 2048,
                'metric_type': MetricType.IP
            })

        _search_client.create_index(
            'JFA',
            IndexType.IVFLAT,
            {
                'nlist': 2048
            }
        )

        register_pool = database[f'JFA_Company_{company_id}_register_buffer_pool']
        registered = database[f'{company_id}_registered']
        position_id = database[f'{company_id}']

        _register_pool = _database[f'JFA_Company_{company_id}_register_buffer_pool']
        _registered = _database[f'{company_id}_registered']
        _position_id = _database[f'{company_id}']

        _companies.insert_one(company)
        for iter in position_id.find():
            employee_id = iter['employee_id']
            if _registered.find_one({'_id': employee_id}) is None:
                _registered.insert_one({
                    '_id': employee_id,
                    'registered': 1
                })

            pos = iter['_id']

            status, vectors = search_client.get_entity_by_id(f'JFA_Company_{company_id}', [pos])
            status, id = _search_client.insert(f'JFA_Company_{company_id}', records=vectors)

            _position_id.insert_one({
                '_id': id[0],
                'employee_id': employee_id
            })

            pool = register_pool.find({
                'company_id': company_id,
                'employee_id': employee_id,
                'pos': pos
            })

            if pool is None:
                print(company_id, employee_id)
                continue

            for record in pool:
                record['pos'] = id[0]
                _register_pool.insert_one(record)
