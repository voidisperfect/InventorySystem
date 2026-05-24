import os
from loguru import logger
from contextlib import asynccontextmanager
from fastapi import FastAPI
from faststream.kafka.fastapi import KafkaRouter

from .database import init_db
from .subscribers import router as subscriber_router
from .routers import orders_router, auth_router

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "redpanda:9092")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Booting up: Initializing Order Database...")
    await init_db()
    # Expose Kafka publisher to subrouters via app state
    app.state.publisher = publisher
    yield
    logger.info("🛑 Shutting down: Cleaning up resources...")


app = FastAPI(lifespan=lifespan)

router = KafkaRouter(KAFKA_BROKERS, request_timeout_ms=10000)
app.include_router(router)
publisher = router.publisher("order_events")

# Include Subrouters
app.include_router(subscriber_router)
app.include_router(auth_router)
app.include_router(orders_router)
