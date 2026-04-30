from faststream.kafka.fastapi import KafkaRouter
from sqlalchemy import select
from .database import AsyncSessionLocal 
from .models import Order

router = KafkaRouter("redpanda:9092")

@router.subscriber("inventory_responses")
async def handle_inventory_response(data: dict):
    """
    Subscriber that listens for stock reservation results from the Inventory service.
    """
    order_id = data.get("order_id")
    # consume_orders.py sends "SUCCESS" or "FAILED"
    status_response = data.get("status") 
    reason = data.get("reason")

    if not order_id:
        print("⚠️ Received response without order_id")
        return

    # Use a manual session since this runs as a background task outside a request
    async with AsyncSessionLocal() as db:
        try:
            # Fetch the order from the database
            result = await db.execute(select(Order).where(Order.id == order_id))
            order = result.scalar_one_or_none()

            if not order:
                print(f"❌ Order {order_id} not found in database")
                return

            # Update status based on the payload from consume_orders.py
            if status_response == "SUCCESS":
                order.status = "COMPLETED"
                print(f"✅ Order {order_id} is now COMPLETED: {reason}")
            else:
                order.status = "FAILED"
                print(f"❌ Order {order_id} is now FAILED: {reason}")

            # Commit the transaction to Postgres
            await db.commit()
            
        except Exception as e:
            await db.rollback()
            print(f"🔥 Database Error in subscriber: {str(e)}")