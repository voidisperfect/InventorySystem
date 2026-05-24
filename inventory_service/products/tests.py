from unittest.mock import AsyncMock, patch
import uuid
from django.test import TestCase
from products.models import Product, Reservation
from products.management.commands.consume_orders import process_order_sync, handle_order, ProcessOrderResult

class ConsumeOrdersTests(TestCase):
    def setUp(self):
        # Create a test product
        self.product = Product.objects.create(
            name="Super Fast SSD",
            price="99.99",
            stock_quantity=10
        )

    def test_process_order_sync_success(self):
        """Verify successful order processing reserves stock and updates quantity."""
        order_id = uuid.uuid4()
        payload = {
            "order_id": str(order_id),
            "items": [
                {"product_id": str(self.product.id), "quantity": 2}
            ]
        }

        # Run process_order_sync
        result = process_order_sync(payload)

        # Assertions
        assert isinstance(result, ProcessOrderResult)
        self.assertTrue(result.success)
        self.assertEqual(result.detail, "All items reserved successfully")

        # Verify database state
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 8)  # 10 - 2

        reservation = Reservation.objects.get(order_id=order_id, product=self.product)
        self.assertEqual(reservation.quantity, 2)
        self.assertEqual(reservation.status, Reservation.ReservationStatus.COMPLETED)

    def test_process_order_sync_idempotency(self):
        """Verify that processing the same order_id twice is idempotent and does not deduct stock again."""
        order_id = uuid.uuid4()
        payload = {
            "order_id": str(order_id),
            "items": [
                {"product_id": str(self.product.id), "quantity": 3}
            ]
        }

        # First run (Success)
        result1 = process_order_sync(payload)
        self.assertTrue(result1.success)

        # Second run (Should skip and return success)
        result2 = process_order_sync(payload)
        self.assertTrue(result2.success)
        self.assertEqual(result2.detail, "Already processed")

        # Verify stock was only deducted once
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 7)  # 10 - 3 (only once!)

    def test_process_order_sync_insufficient_stock(self):
        """Verify that process_order_sync fails when requesting more stock than available."""
        order_id = uuid.uuid4()
        payload = {
            "order_id": str(order_id),
            "items": [
                {"product_id": str(self.product.id), "quantity": 15}  # Only 10 available
            ]
        }

        result = process_order_sync(payload)
        self.assertFalse(result.success)
        self.assertIn("Insufficient stock", result.detail)

        # Verify stock was NOT deducted
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

    def test_process_order_sync_product_not_found(self):
        """Verify that process_order_sync fails gracefully when product does not exist."""
        order_id = uuid.uuid4()
        fake_product_id = uuid.uuid4()
        payload = {
            "order_id": str(order_id),
            "items": [
                {"product_id": str(fake_product_id), "quantity": 1}
            ]
        }

        result = process_order_sync(payload)
        self.assertFalse(result.success)
        self.assertIn("not found", result.detail)

    @patch("products.management.commands.consume_orders.publisher.publish", new_callable=AsyncMock)
    async def test_handle_order_success(self, mock_publish):
        """Verify handle_order async handler publishes a SUCCESS payload to Kafka."""
        order_id = uuid.uuid4()
        payload = {
            "order_id": str(order_id),
            "items": [
                {"product_id": str(self.product.id), "quantity": 1}
            ]
        }

        await handle_order(payload)

        # Verify publisher.publish was called with success status
        mock_publish.assert_awaited_once()
        published_payload = mock_publish.call_args[0][0]
        self.assertEqual(published_payload["order_id"], str(order_id))
        self.assertEqual(published_payload["status"], "SUCCESS")
        self.assertEqual(published_payload["reason"], "All items reserved successfully")

    @patch("products.management.commands.consume_orders.publisher.publish", new_callable=AsyncMock)
    async def test_handle_order_failure(self, mock_publish):
        """Verify handle_order async handler publishes a FAILED payload to Kafka when out of stock."""
        order_id = uuid.uuid4()
        payload = {
            "order_id": str(order_id),
            "items": [
                {"product_id": str(self.product.id), "quantity": 50}  # Over limits
            ]
        }

        await handle_order(payload)

        mock_publish.assert_awaited_once()
        published_payload = mock_publish.call_args[0][0]
        self.assertEqual(published_payload["order_id"], str(order_id))
        self.assertEqual(published_payload["status"], "FAILED")
        self.assertIn("Insufficient stock", published_payload["reason"])
