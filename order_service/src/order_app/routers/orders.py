import uuid
import os
from decimal import Decimal
from loguru import logger
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..auth import get_current_user
from ..schemas import OrderRequest, OrderResponse, OrderStatus, OrderEvent
from ..database import get_db
from ..models import Order, OrderItem

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])

@router.post("/", status_code=status.HTTP_202_ACCEPTED, response_model=OrderResponse)
async def create_order(
    order_data: OrderRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user) 
):
    # Debug & Validate User Payload
    logger.debug(f"User dictionary content: {user}")
    
    # Extract ID
    user_id = user.get("user_id") or user.get("sub")
    if user_id is None:
        logger.error("Could not find 'user_id' or 'sub' in token payload")
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
            logger.error(f"Error fetching prices from inventory service: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not retrieve product prices. Please try again later."
            )
            
    # 3. Calculate total_price
    calculated_total_price = Decimal("0.00")
    for item in order_data.items:
        price_str = prices.get(str(item.product_id))
        if price_str is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {item.product_id} not found or price not available."
            )
        try:
            calculated_total_price += Decimal(str(price_str)) * item.quantity
        except Exception:
            logger.critical(f"❌ DATABASE INTEGRITY CORRUPTION: Invalid price '{price_str}' received for product {item.product_id}!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Price parsing error from internal provider."
            )

    # Create Order Record
    new_order = Order(
        id=order_id,
        user_id=str(user_id),
        status=OrderStatus.PENDING.value,
        total_price=calculated_total_price
    )
    
    # Add Order Items
    for item in order_data.items:
        order_item = OrderItem(
            order_id=order_id,
            product_id=item.product_id,
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
        logger.error(f"DB ERROR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Database save failed."
        )

    # 5. Kafka Event Construction for Inventory Service
    event_model = OrderEvent(
        order_id=order_id,
        user_id=str(user_id),
        customer_email=user.get("email", f"{user_id}@example.com"),
        items=order_data.items,
        total_price=calculated_total_price,
        status=OrderStatus.PENDING,
        created_at=new_order.created_at
    )
    event = event_model.model_dump(mode='json')

    # 6. Kafka Publish
    try:
        # Retrieve publisher from FastAPI app state
        publisher = getattr(request.app.state, "publisher", None)
        if publisher is None:
            raise RuntimeError("Kafka publisher is not initialized in app state")
            
        await publisher.publish(
            event, 
            key=str(order_id).encode('utf-8'), 
            topic="order_events"
        )
    except Exception as e:
        logger.warning(f"KAFKA ERROR: {str(e)}. Updating order status to FAILED.")
        new_order.status = OrderStatus.FAILED.value
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Order saved but message queue unavailable."
        )
        
    return {"order_id": order_id, "status": OrderStatus.PENDING.value, "total_price": new_order.total_price, "created_at": new_order.created_at}

@router.get("/{order_id}/", response_model=OrderResponse)
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
