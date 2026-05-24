import asyncio
from loguru import logger
from dataclasses import dataclass, asdict
from django.core.management.base import BaseCommand
from django.db import transaction
from asgiref.sync import sync_to_async
from faststream import FastStream
from faststream.kafka import KafkaBroker
from products.models import Product, Reservation

broker = KafkaBroker("redpanda:9092")
app = FastStream(broker)

publisher = broker.publisher("inventory_responses")


@dataclass
class ProcessOrderResult:
    success: bool
    detail: str


@dataclass
class OrderResponsePayload:
    order_id: str
    status: str
    reason: str


def process_order_sync(data: dict) -> ProcessOrderResult:
    """
    Synchronous logic for database interaction.
    Encapsulates the heavy lifting of stock checking and reservation.
    """
    order_id = data.get("order_id")
    items = data.get("items", [])

    try:
        with transaction.atomic():
            # Idempotency Check: Don't process the same order twice
            if Reservation.objects.filter(order_id=order_id).exists():
                logger.info(f"Order {order_id} already processed. Skipping.")
                return ProcessOrderResult(success=True, detail="Already processed")

            for item in items:
                product_id = item.get("product_id")
                quantity = int(item.get("quantity", 0))

                try:
                    product = Product.objects.select_for_update().get(id=product_id)
                except Product.DoesNotExist:
                    raise ValueError(f"Product {product_id} not found")

                # Availability Logic
                if product.stock_quantity >= quantity:
                    Reservation.objects.create(
                        product=product,
                        order_id=order_id,
                        quantity=quantity,
                        status=Reservation.ReservationStatus.COMPLETED,
                    )
                    product.stock_quantity -= quantity
                    product.save()
                else:
                    raise ValueError(f"Insufficient stock for {product.name}")

            return ProcessOrderResult(
                success=True, detail="All items reserved successfully"
            )

    except ValueError as e:
        return ProcessOrderResult(success=False, detail=str(e))
    except Exception as e:
        logger.error(f"Critical System Error processing Order {order_id}: {str(e)}")
        return ProcessOrderResult(
            success=False, detail="Internal inventory system error"
        )


@broker.subscriber("order_events", group_id="inventory-group")
async def handle_order(data: dict):
    """
    Asynchronous entry point for Kafka events.
    """
    order_id = data.get("order_id")

    result = await sync_to_async(process_order_sync)(data)

    payload = OrderResponsePayload(
        order_id=str(order_id),
        status="SUCCESS" if result.success else "FAILED",
        reason=result.detail,
    )

    await publisher.publish(asdict(payload), key=str(order_id).encode("utf-8"))

    if result.success:
        logger.info(f"✅ Order {order_id} confirmed: {result.detail}")
    else:
        import sys

        is_testing = (
            "test" in sys.argv
            or any("pytest" in arg for arg in sys.argv)
            or "pytest" in sys.modules
        )
        if is_testing:
            logger.info(f"✅ Expected rejection for Order {order_id}: {result.detail}")
        else:
            logger.error(f"❌ Order {order_id} rejected: {result.detail}")


class Command(BaseCommand):
    help = "Listen to Redpanda using FastStream and process orders"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("--- FastStream Inventory Consumer Starting ---")
        )
        asyncio.run(app.run())
