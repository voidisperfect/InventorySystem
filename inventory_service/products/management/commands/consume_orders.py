import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from confluent_kafka import Consumer, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic
from products.models import Product, Reservation

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Listen to Redpanda and auto-create topics if missing"

    def ensure_topic_exists(self, admin_client, topic_name):
        """Checks if topic exists, if not, creates it via AdminClient."""
        try:
            metadata = admin_client.list_topics(timeout=10)
            if topic_name not in metadata.topics:
                self.stdout.write(self.style.WARNING(f"Topic '{topic_name}' not found. Creating..."))
                new_topic = NewTopic(topic_name, num_partitions=1, replication_factor=1)
                # create_topics returns a dict of futures
                fs = admin_client.create_topics([new_topic])
                # Wait for operation to finish
                for topic, f in fs.items():
                    try:
                        f.result()
                        self.stdout.write(self.style.SUCCESS(f"Topic '{topic}' created."))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Failed to create topic {topic}: {e}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"AdminClient error: {e}"))

    def handle(self, *args, **options):
        bootstrap_servers = "redpanda:9092"
        topic_name = "order_events"

        # 1. Infrastructure Check (AdminClient)
        admin_client = AdminClient({"bootstrap.servers": bootstrap_servers})
        self.ensure_topic_exists(admin_client, topic_name)

        # Consumer Setup
        conf = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": "inventory-group",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
        consumer = Consumer(conf)
        consumer.subscribe([topic_name])

        self.stdout.write(self.style.SUCCESS("--- Inventory Consumer Started and Listening ---"))

        try:
            while True:
                msg = consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        self.stdout.write(self.style.ERROR(f"Kafka error: {msg.error()}"))
                        continue

                # Message Processing logic
                try:
                    data = json.loads(msg.value().decode("utf-8"))
                    order_id = data.get("order_id")
                    product_id = data.get("product_id")
                    # Ensure quantity is an integer
                    try:
                        quantity = int(data.get("quantity", 0))
                    except (ValueError, TypeError):
                        self.stdout.write(self.style.ERROR(f"Invalid quantity in message: {data}"))
                        continue

                    if not order_id or not product_id or quantity <= 0:
                        self.stdout.write(self.style.WARNING(f"Skipping incomplete message: {data}"))
                        continue

                    # Atomic Database Transaction
                    with transaction.atomic():
                        # Idempotency: Prevent duplicate processing
                        if Reservation.objects.filter(order_id=order_id).exists():
                            self.stdout.write(self.style.WARNING(f"Order {order_id} already processed. Skipping."))
                            continue

                        # Fetch and lock product row
                        try:
                            product = Product.objects.select_for_update().get(id=product_id)
                        except Product.DoesNotExist:
                            self.stdout.write(self.style.ERROR(f"Product {product_id} not found."))
                            continue

                        # Check availability
                        if product.stock_quantity >= quantity:
                            # Create record
                            Reservation.objects.create(
                                product=product,
                                order_id=order_id,
                                quantity=quantity,
                                status=Reservation.ReservationStatus.PENDING,
                            )
                            # Update inventory
                            product.stock_quantity -= quantity
                            product.save()
                            
                            self.stdout.write(
                                self.style.SUCCESS(f"SUCCESS: Reserved {quantity}x {product.name} for Order {order_id}")
                            )
                        else:
                            self.stdout.write(
                                self.style.ERROR(f"FAILED: Insufficient stock for {product.name} (Order {order_id})")
                            )

                except json.JSONDecodeError:
                    self.stdout.write(self.style.ERROR("Received invalid JSON message."))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Runtime error: {e}"))

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Shutting down..."))
        finally:
            consumer.close()