import uuid
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from faststream.kafka.fastapi import KafkaRouter

from .auth import get_current_user, create_access_token
from .schemas import OrderRequest, OrderResponse, OrderStatus
from .services import process_create_order
from .subscribers import router as subscriber_router

app = FastAPI()


router = KafkaRouter(
    "redpanda:9092",
    request_timeout_ms=10000  # This is a valid argument to handle network lag
)
app.include_router(router)
publisher = router.publisher("order_events")


app.include_router(subscriber_router)


@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    access_token = create_access_token(
        data={"sub": form_data.username, "email": f"{form_data.username}@example.com"}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/v1/orders/", 
          status_code=status.HTTP_202_ACCEPTED, 
          response_model=OrderResponse)
async def create_order(
    order_data: OrderRequest, 
    user: dict = Depends(get_current_user) 
):
    order_id = str(uuid.uuid4())
    
    # Prepare the payload
    event = {
        "order_id": order_id,
        "user_id": user.get("sub"), # Use 'sub' or 'id' based on your JWT payload
        "items": [item.model_dump() for item in order_data.items],
        "status": "PENDING"
    }

    try:
        # FIX: The key MUST be bytes, so we add .encode()
        await publisher.publish(
            event, 
            key=order_id.encode('utf-8'), 
            topic="order_events"
        )
        
        return {
            "order_id": order_id,
            "status": "PENDING"
        }

    except Exception as e:
        print(f"❌ KAFKA PUBLISH ERROR: {type(e).__name__} - {str(e)}")
        # This will now work because HTTPException is imported
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Kafka Error: {type(e).__name__}"
        )



@app.get("/api/v1/orders/{order_id}/", 
         response_model=OrderResponse,
         dependencies=[Depends(get_current_user)])
async def get_order_status(order_id: uuid.UUID):
    return OrderResponse(order_id=order_id, status=OrderStatus.PENDING)