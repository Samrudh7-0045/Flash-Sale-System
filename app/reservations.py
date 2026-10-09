
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

local expired = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', now)
for _, id in ipairs(expired) do
    redis.call('HDEL', KEYS[2], id)
end
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)

local reserved = 0
local quantities = redis.call('HVALS', KEYS[2])
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

CLAIM_SCRIPT = """
local expiry = redis.call('ZSCORE', KEYS[1], ARGV[1])
local quantity = redis.call('HGET', KEYS[2], ARGV[1])

if not expiry or tonumber(expiry) <= tonumber(ARGV[3]) then
    return 0
end

if not quantity or tonumber(quantity) ~= tonumber(ARGV[2]) then
    return 0
end

return redis.call('SET', KEYS[3], '1', 'NX', 'EX', 65) and 1 or 0
"""

RELEASE_SCRIPT = """
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('HDEL', KEYS[2], ARGV[1])
redis.call('DEL', KEYS[3])
return 1
"""


def _keys(product_id: int, token: str):
    return (
        f"reservations:{product_id}",
        f"reservation_quantities:{product_id}",
        f"reservation_claim:{token}",
    )


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
    zkey, hkey, _ = _keys(product_id, token)

    result = redis_client.eval(
        RESERVE_SCRIPT, 2, zkey, hkey,
        now, quantity, stock, token, RESERVATION_TTL,
    )
    return token if result == 1 else None


def claim_reservation(product_id: int, quantity: int, token: str) -> bool:
    zkey, hkey, claim_key = _keys(product_id, token)
    result = redis_client.eval(
        CLAIM_SCRIPT, 3, zkey, hkey, claim_key,
        token, quantity, int(time.time()),
    )
    return result == 1


def release_stock(product_id: int, token: str) -> None:
    zkey, hkey, claim_key = _keys(product_id, token)
    redis_client.eval(
        RELEASE_SCRIPT, 3, zkey, hkey, claim_key, token
    )


def unclaim_reservation(product_id: int, token: str) -> None:
    _, _, claim_key = _keys(product_id, token)
    redis_client.delete(claim_key)
