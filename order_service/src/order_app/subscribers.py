# subscribers.py
from faststream.kafka.fastapi import KafkaRouter

router = KafkaRouter("redpanda:9092")

@router.subscriber("inventory_responses")
async def handle_inventory_response(data: dict):
    order_id = data.get("order_id")
    status_response = data.get("status") # This will be "SUCCESS" or "FAILED"

    if status_response == "SUCCESS":
        # In the future: await db.orders.update(order_id, status=OrderStatus.COMPLETED)
        print(f"✔️ Order {order_id} is now COMPLETED")
    else:
        # In the future: await db.orders.update(order_id, status=OrderStatus.FAILED)
        print(f"❌ Order {order_id} is now FAILED")