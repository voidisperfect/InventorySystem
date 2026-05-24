import httpx
import time
import subprocess

INVENTORY_URL = "http://localhost:8000"
ORDER_URL = "http://localhost:8001"


def run_test():
    print("1. Creating product in inventory_service...")
    cmd = """
import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup()
from products.models import Product
Product.objects.filter(name='Test Product').delete()
p = Product.objects.create(name='Test Product', price=15.50, stock_quantity=100)
print(str(p.id))
"""
    result = subprocess.run(
        ["docker", "exec", "inventory_service", "python", "-c", cmd],
        capture_output=True,
        text=True,
        check=True,
    )
    product_id = result.stdout.strip().split("\n")[-1]
    print(f"Product ID created: {product_id}")

    print("2. Getting JWT token from order_service...")
    response = httpx.post(
        f"{ORDER_URL}/token", data={"username": "testuser", "password": "password"}
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("3. Placing order...")
    order_data = {"items": [{"product_id": product_id, "quantity": 2}]}
    response = httpx.post(
        f"{ORDER_URL}/api/v1/orders/", json=order_data, headers=headers
    )
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")

    if response.status_code >= 400:
        print("Failure. Exiting.")
        return

    order_info = response.json()
    order_id = order_info["order_id"]

    # Verify total_price
    expected_price = 15.50 * 2
    actual_price = order_info.get("total_price")
    assert float(actual_price) == expected_price, (
        f"Expected {expected_price}, got {actual_price}"
    )
    print(f"Total price calculated correctly: {actual_price}")

    print("4. Waiting for order to be processed via Kafka...")
    time.sleep(3)  # wait for inventory_consumer and order subscriber

    print("5. Checking order status...")
    response = httpx.get(f"{ORDER_URL}/api/v1/orders/{order_id}/", headers=headers)
    response.raise_for_status()
    final_status = response.json()["status"]
    print(f"Final order status: {final_status}")
    assert final_status == "COMPLETED", f"Expected COMPLETED, got {final_status}"

    print("All tests passed successfully!")


if __name__ == "__main__":
    run_test()
