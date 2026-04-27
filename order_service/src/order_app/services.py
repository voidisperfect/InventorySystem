import uuid
from decimal import Decimal
from fastapi import HTTPException, status
from .schemas import OrderRequest, OrderEvent, OrderStatus, OrderResponse

async def process_create_order(order_data: OrderRequest, user: dict, publisher) -> OrderResponse:
    order_id = uuid.uuid4()
    
    event = OrderEvent(
        order_id=order_id,
        user_id=user["user_id"],
        customer_email=user["email"],
        items=order_data.items,
        total_price=Decimal("0.00"), 
        status=OrderStatus.PENDING
    )

    try:
        await publisher.publish(event.model_dump(mode='json'), key=str(order_id))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Kafka is down, order could not be processed"
        )

    return OrderResponse(order_id=order_id, status=OrderStatus.PENDING)