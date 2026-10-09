
import time
import uuid

from app.database import SessionLocal
from app.models import Product
from app.redis_client import redis_client

RESERVATION_TTL = 60

RESERVE_SCRIPT = """
local now = tonumber(ARGV[1])
local quantity = tonumber(ARGV[2])
local stock = tonumber(ARGV[3])
local token = ARGV[4]
local ttl = tonumber(ARGV[5])

local expired = redis.call(
    'ZRANGEBYSCORE', KEYS[1], '-inf', now
)

for _, id in ipairs(expired) do
    redis.call('HDEL', KEYS[2], id)
end

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)

local quantities = redis.call('HVALS', KEYS[2])
local reserved = 0

for _, q in ipairs(quantities) do
    reserved = reserved + tonumber(q)
end

if reserved + quantity > stock then
    return 0
end

redis.call('ZADD', KEYS[1], now + ttl, token)
redis.call('HSET', KEYS[2], token, quantity)
redis.call('EXPIRE', KEYS[1], ttl + 5)
redis.call('EXPIRE', KEYS[2], ttl + 5)

return 1
"""

RELEASE_SCRIPT = """
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('HDEL', KEYS[2], ARGV[1])
return 1
"""


def reserve_stock(product_id: int, quantity: int) -> str | None:
    if quantity <= 0:
        return None

    db = SessionLocal()
    try:
        product = db.get(Product, product_id)
        if product is None:
            return None

        stock = product.stock
    finally:
        db.close()

    token = str(uuid.uuid4())
    now = int(time.time())

    result = redis_client.eval(
        RESERVE_SCRIPT,
        2,
        f"reservations:{product_id}",
        f"reservation_quantities:{product_id}",
        now,
        quantity,
        stock,
        token,
        RESERVATION_TTL,
    )

    return token if result == 1 else None


def release_stock(product_id: int, token: str) -> None:
    redis_client.eval(
        RELEASE_SCRIPT,
        2,
        f"reservations:{product_id}",
        f"reservation_quantities:{product_id}",
        token,
    )
