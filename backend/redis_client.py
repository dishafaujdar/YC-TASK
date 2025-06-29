import os
import redis.asyncio as redis
from kombu.utils.url import safequote

# redis_host = safequote(os.environ.get('REDIS_HOST', 'localhost'))
redis_client = redis.Redis(host='localhost', port=6379, db=0)

try:
    redis_client.ping()
    print("redis is up and running")
except:
    print("try running redis again")

redis_client.set("message","hey you're all good to go with redis server.")

value = redis_client.get("message")
print(value)

async def add_key_value_redis(key, value, expire=None):
    await redis_client.set(key, value)
    if expire:
        await redis_client.expire(key, expire)

async def get_value_redis(key):
    return await redis_client.get(key)

async def delete_key_redis(key):
    await redis_client.delete(key)

