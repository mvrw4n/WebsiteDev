# Create a test file: test_redis.py
import redis

r = redis.Redis(host='localhost', port=6379, db=0)
try:
    r.ping()
    print("Successfully connected to Redis!")
except redis.ConnectionError:
    print("Failed to connect to Redis")