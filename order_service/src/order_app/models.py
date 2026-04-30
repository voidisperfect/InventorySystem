from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from .database import Base

class Order(Base):
    __tablename__ = "orders"
    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(String, nullable=False)
    status = Column(String, default="PENDING")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"))
    # FIXED: Changed from Integer to UUID to match Django's Product ID
    product_id = Column(UUID(as_uuid=True), nullable=False) 
    quantity = Column(Integer, nullable=False)