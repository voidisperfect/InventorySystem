import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from faststream.kafka import TestKafkaBroker
from order_app.subscribers import router, OrderStatus

@pytest.mark.asyncio
async def test_handle_inventory_response_success():
    """Verify that subscriber updates order status to COMPLETED on SUCCESS response."""
    order_id = uuid.uuid4()
    
    mock_order = MagicMock()
    mock_order.id = order_id
    mock_order.status = "PENDING"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_order

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Patch AsyncSessionLocal to return our mock session as context manager
    with patch("order_app.subscribers.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session
        
        async with TestKafkaBroker(router.broker) as test_broker:
            payload = {
                "order_id": str(order_id),
                "status": "SUCCESS",
                "reason": "All stock allocated successfully"
            }
            await test_broker.publish(payload, "inventory_responses")
            
        # Assertions to ensure database updates took place correctly
        assert mock_order.status == OrderStatus.COMPLETED.value
        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()

@pytest.mark.asyncio
async def test_handle_inventory_response_failed():
    """Verify that subscriber updates order status to FAILED on FAILED response."""
    order_id = uuid.uuid4()
    
    mock_order = MagicMock()
    mock_order.id = order_id
    mock_order.status = "PENDING"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_order

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("order_app.subscribers.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session
        
        async with TestKafkaBroker(router.broker) as test_broker:
            payload = {
                "order_id": str(order_id),
                "status": "FAILED",
                "reason": "Out of stock for Product X"
            }
            await test_broker.publish(payload, "inventory_responses")
            
        assert mock_order.status == OrderStatus.FAILED.value
        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()

@pytest.mark.asyncio
async def test_handle_inventory_response_order_not_found():
    """Verify that subscriber exits gracefully and doesn't commit if order is not in db."""
    order_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # Not found

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("order_app.subscribers.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session
        
        async with TestKafkaBroker(router.broker) as test_broker:
            payload = {
                "order_id": str(order_id),
                "status": "SUCCESS",
                "reason": "allocated"
            }
            await test_broker.publish(payload, "inventory_responses")
            
        mock_session.commit.assert_not_awaited()
