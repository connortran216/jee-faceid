import pymongo
import datetime
from bson import ObjectId
from pprint import pprint

client = pymongo.MongoClient("mongodb://dps:dps123@localhost:27017")
database = client['test_database']

post = {
    '_id': '001',
    'author': 'Mike',
    'text': 'My first blog post!',
    'tags': ['mongodb', 'python', 'pymongo'],
    'date': datetime.datetime.utcnow()
}

posts = database.posts_2
post_id = posts.insert_one(post).inserted_id
# pprint(posts.find_one({'author': 'Mike'}))
pprint(posts.find_one({'_id': '001'})['author'])


