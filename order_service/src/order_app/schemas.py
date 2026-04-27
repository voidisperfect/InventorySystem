# schemas.py
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED" 
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    
class OrderItem(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(gt=0, le=1000)

class OrderRequest(BaseModel):
    items: List[OrderItem] = Field(min_length=1) 

class OrderResponse(BaseModel):
    order_id: uuid.UUID
    status: OrderStatus

class OrderEvent(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=False) 
    
    order_id: uuid.UUID
    user_id: str
    customer_email: EmailStr
    items: List[OrderItem]
    total_price: Decimal = Field(decimal_places=2) 
    status: OrderStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))