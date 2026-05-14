import uuid
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from faststream.kafka.fastapi import KafkaRouter
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .auth import get_current_user, create_access_token
from .schemas import OrderRequest, OrderResponse
from .database import get_db, init_db
from .models import Order, OrderItem 
from .subscribers import router as subscriber_router

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "redpanda:9092")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Booting up: Initializing Order Database...")
    await init_db()
    yield
    print("🛑 Shutting down: Cleaning up resources...")

app = FastAPI(lifespan=lifespan)

router = KafkaRouter(KAFKA_BROKERS, request_timeout_ms=10000)
app.include_router(router)
publisher = router.publisher("order_events")

app.include_router(subscriber_router)

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Generates a token with both 'sub' and 'user_id' to avoid key mismatch
    access_token = create_access_token(
        data={"sub": form_data.username,  "user_id": form_data.username, "email": f"{form_data.username}@example.com"}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/v1/orders/", 
          status_code=status.HTTP_202_ACCEPTED, 
          response_model=OrderResponse)
async def create_order(
    order_data: OrderRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user) 
):
    # Debug & Validate User Payload
    print(f"DEBUG: User dictionary content: {user}")
    
    # Extract ID - Looking for 'user_id' first as seen in your logs
    user_id = user.get("user_id") or user.get("sub")
    
    if user_id is None:
        print("❌ ERROR: Could not find 'user_id' or 'sub' in token payload")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identifier missing from token"
        )

    order_id = uuid.uuid4()
    
    # 1. Collect product IDs to fetch prices
    product_ids = [str(item.product_id) for item in order_data.items]
    
    # 2. Fetch prices from inventory_service
    INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-api:8000")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{INVENTORY_SERVICE_URL}/api/v1/products/prices/",
                json={"product_ids": product_ids},
                timeout=5.0
            )
            response.raise_for_status()
            prices = response.json()
        except Exception as e:
            print(f"❌ Error fetching prices from inventory service: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not retrieve product prices. Please try again later."
            )
            
    # 3. Calculate total_price
    calculated_total_price = 0.0
    for item in order_data.items:
        price_str = prices.get(str(item.product_id))
        if price_str is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {item.product_id} not found or price not available."
            )
        calculated_total_price += float(price_str) * item.quantity

    # Create Order Record
    new_order = Order(
        id=order_id,
        user_id=str(user_id), # Using the validated user_id variable
        status="PENDING",
        total_price=calculated_total_price
    )
    
    # Add Order Items
    for item in order_data.items:
        order_item = OrderItem(
            order_id=order_id,
            product_id=item.product_id, # Requires product_id as UUID in models.py
            quantity=item.quantity
        )
        db.add(order_item)
    
    db.add(new_order)
    
    # Transactional Commit
    try:
        await db.commit()
        await db.refresh(new_order) 
    except Exception as e:
        await db.rollback()
        print(f"❌ DB ERROR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Database save failed."
        )

    # 5. Kafka Event Construction for Inventory Service
    event = {
        "order_id": str(order_id),
        "user_id": str(user_id),
        "customer_email": user.get("email", f"{user_id}@example.com"),
        "items": [item.model_dump() for item in order_data.items],
        "total_price": float(calculated_total_price),
        "status": "PENDING",
        "created_at": new_order.created_at.isoformat() if new_order.created_at else None
    }

    # 6. Kafka Publish
    try:
        await publisher.publish(
            event, 
            key=str(order_id).encode('utf-8'), 
            topic="order_events"
        )
    except Exception as e:
        print(f"⚠️ KAFKA ERROR: {str(e)}. Updating order status to FAILED.")
        new_order.status = "FAILED"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Order saved but message queue unavailable."
        )
        
    return {"order_id": order_id, "status": "PENDING", "total_price": new_order.total_price, "created_at": new_order.created_at}

@app.get("/api/v1/orders/{order_id}/", response_model=OrderResponse)
async def get_order_status(
    order_id: uuid.UUID, 
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    return OrderResponse(order_id=order.id, status=order.status, total_price=order.total_price, created_at=order.created_at)