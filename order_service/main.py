import json
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from fastapi import FastAPI, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field
from confluent_kafka import Producer
import socket

app = FastAPI()

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

class OrderRequest(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(gt=0)
    customer_email: EmailStr
    total_price: Decimal = Field(gt=0, decimal_places=2)

producer = Producer({
    'bootstrap.servers': 'redpanda:9092',
    'client.id': socket.gethostname(),
    'acks': 'all'
})

# --- 3. MOCK AUTHENTICATION (JWT Placeholder) ---
async def get_current_user_id():
    # Placeholder: In reality, extract this from the 'Authorization' header
    return uuid.uuid4() 

# --- 4. ENDPOINTS ---

@app.post("/orders/", status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderRequest, 
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    order_id = uuid.uuid4()
    
    # Create the full Event Payload
    event_payload = {
        "order_id": str(order_id), # ensure everything matches the consume_orders.py schema expectations
        "user_id": str(user_id),
        "customer_email": order_data.customer_email,
        "product_id": str(order_data.product_id),
        "quantity": order_data.quantity,
        "total_price": float(order_data.total_price),
        "status": "PENDING",
        "created_at": datetime.utcnow().isoformat()
    }

    try:
        # Note: In a real app, you should SAVE this to a DB here before sending to Kafka
        producer.produce(
            "order_events",
            key=str(order_id),
            value=json.dumps(event_payload)
        )
        producer.poll(0)

        return event_payload
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to publish order")

@app.get("/orders/{order_id}")
async def get_order_status(order_id: uuid.UUID):
    # ANGRY TESTER NOTE: This will fail until you add a Database (Postgres)
    # to the Order Service to actually store and retrieve order records.
    return {"order_id": order_id, "status": "PENDING (Mock Response)"}