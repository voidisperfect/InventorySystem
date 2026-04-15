import json
from django.core.management.base import BaseCommand
from confluent_kafka import Consumer
from products.models import Product, Reservation


class Command(BaseCommand):
    help = "Listen to Redpanda for new orders"

    def handle(self, *args, **options):
        conf = {
            "bootstrap.servers": "redpanda:9092",
            "group.id": "inventory-group",
            "auto.offset.reset": "earliest",
        }
        consumer = Consumer(conf)
        consumer.subscribe(["order_events"])  # This creates the topic!

        self.stdout.write(self.style.SUCCESS("--- Inventory Consumer Started ---"))

        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                continue

            data = json.loads(msg.value().decode("utf-8"))
            product_id = data.get("product_id")
            quantity = data.get("quantity")
            order_id = data.get("order_id")

            try:
                product = Product.objects.get(id=product_id)
                # Logic: Create a reservation and update stock
                Reservation.objects.create(
                    product=product,
                    order_id=order_id,
                    quantity=quantity,
                    status="SUCCESS",
                )
                product.stock_quantity -= quantity
                product.save()
                self.stdout.write(
                    self.style.SUCCESS(f"Reserved {quantity} for {product.name}")
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error: {e}"))
