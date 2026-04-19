import uuid
from django.db import models


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} ({self.stock_quantity} in stock)"


class Reservation(models.Model):
    """Tracks stock that is 'held' while an order is being processed"""
    class ReservationStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reservations"
    )
    order_id = models.UUIDField(
        unique=True
    )  # ensure one reservation per order_id
    quantity = models.PositiveIntegerField()
    
    status = models.CharField(
        max_length=20, 
        choices=ReservationStatus.choices,
        default=ReservationStatus.PENDING
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reservation {self.id} for Order {self.order_id} ({self.status})"
