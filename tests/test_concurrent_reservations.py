
from concurrent.futures import ThreadPoolExecutor

from app.reservations import reserve_stock, release_stock


PRODUCT_ID = 2
REQUESTS = 10
QUANTITY_PER_REQUEST = 5


def attempt_reservation(_):
    return reserve_stock(PRODUCT_ID, QUANTITY_PER_REQUEST)


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=REQUESTS) as executor:
        tokens = list(executor.map(attempt_reservation, range(REQUESTS)))

    successful = [token for token in tokens if token is not None]

    print("Successful reservations:", len(successful))
    print("Units reserved:", len(successful) * QUANTITY_PER_REQUEST)
    print("Available stock:", 46)
    print("Overselling prevented:", len(successful) * QUANTITY_PER_REQUEST <= 46)

    for token in successful:
        release_stock(PRODUCT_ID, token)

