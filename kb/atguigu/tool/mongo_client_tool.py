import time

from pymongo import MongoClient

from atguigu.config.config import MongoConfig
from atguigu.tool.logger import logger

# 获取MongoClient
mongo_client = None
def get_mongo_client():
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(MongoConfig.mongo_url)
    return mongo_client

# collection
collection = None
db = None
def get_mongo_collection():
    global collection
    global db
    try:
        mongo_client = get_mongo_client()
        if db is None:
            db = mongo_client[MongoConfig.mongo_db_name]
        if collection is None:
            #创建索引
            collection = db["chat_history"]
            # 复合索引：_id 升序 + ts 降序 + session_id 升序，
            # 用于支持按 session_id 过滤、按 ts 倒序取最近 N 条历史记录的查询
            collection.create_index([("_id", 1),("ts",-1),("session_id",1)])
        return collection
    except Exception as e:
        logger.error(f"获取 Mongo 集合失败: {e}")
        raise e

#创建历史记录的crud方法

# 获取最近的历史记录列表 limit限定条数 目的是后期在意图识别的时候需要获取历史记录来识别
def get_recent_history_list(session_id,limit=10):
    try:
        collection = get_mongo_collection()
        result = collection.find({"session_id": session_id}).sort("ts", -1).limit(limit)
        return list(result)  #result是游标对象，用list（）强转
    except Exception as e:
        logger.error(f"获取历史记录失败 session_id={session_id}: {e}")
        raise e


# C & U
def add_or_update_history(session_id,role,text,rewritten_query=None,item_names=None,ts=None,_id=None):
    # 全量更新，增量更新
    # c and u 封装为一个函数，是因为他们传参的时候唯一不同就是id
    #若 u ，则id一定存在，若 c ，则id一定不存在
    try:
        collection = get_mongo_collection()
        if _id:
            #update
            data = {
                "_id": _id,
                "session_id": session_id,
                "role": role,
                "text": text,
                "rewritten_query": rewritten_query,
                "item_names": item_names,
                "ts": ts or time.time(),
            }
            collection.updateOne({"_id": _id}, {"$set": data})
            return _id
        else:# create
            data = {
                "session_id": session_id,
                "role": role,
                "text": text,
                "rewritten_query": rewritten_query,
                "item_names": item_names,
                "ts": ts or time.time(),
            }
            result = collection.insert_one(data)
            print(result.inserted_id)
            return result.inserted_id
    except Exception as e:
        logger.error(f"写入历史记录失败 session_id={session_id}: {e}")
        raise e

# D
def delete_history(session_id):
    try:
        collection = get_mongo_collection()
        collection.delete_one({"session_id": session_id})
    except Exception as e:
        logger.error(f"删除历史记录失败 session_id={session_id}: {e}")
        raise e


def update_item_names_and_query(session_id, item_names=None, rewritten_query=None):
    try:
        collection = get_mongo_collection()
        data = {
            "session_id":session_id,
            "item_names": item_names,
            "rewritten_query": rewritten_query,
        }
        collection.updateOne({"session_id": session_id},{"$set":data})
    except Exception as e:
        logger.error(f"更新历史记录意图失败 session_id={session_id}: {e}")
        raise e


if __name__ == '__main__':
    add_or_update_history("01", "user", "问下烫金机。")
    add_or_update_history("01", "assistant", "请问是哪个型号")
    result = add_or_update_history("01", "user", "hak180")
    print(result,type(result))
    add_or_update_history("01", "assistant", "具体有什么问题呢？")


    result = get_recent_history_list("01")
    print(result)


    delete_history("01")
