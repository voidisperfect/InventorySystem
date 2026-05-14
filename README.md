# Inventory and Order Management System

This project is a microservices-based application for managing products and processing orders. It consists of two primary services communicating synchronously via HTTP and asynchronously via Kafka.

## Architecture

* **Order Service**: A FastAPI application responsible for authenticating users via JWT and receiving order requests. Upon receiving an order, it queries the inventory service to calculate the total price, saves the pending order to its database, and publishes an event to Kafka.
* **Inventory Service**: A Django application that manages the product catalog and handles inventory reservations. It exposes an HTTP API for the order service to fetch prices and runs a background consumer to process incoming orders from Kafka. Based on stock availability, it reserves items and publishes the final order status back to Kafka.
* **Infrastructure**: 
    * Postgres databases (isolated for each service)
    * Redpanda (Kafka-compatible event streaming platform)

## Prerequisites

* Docker
* Docker Compose

## Getting Started

1. Start the services using Docker Compose:
   ```bash
   docker-compose up -d --build
   ```

2. The services will be available at:
   * Order Service API: http://localhost:8001
   * Inventory Service API: http://localhost:8000
   * Django Admin Interface: http://localhost:8000/admin

3. To access the Django admin panel and manage products, create a superuser account:
   ```bash
   docker-compose exec inventory_service python manage.py createsuperuser
   ```

## Testing

An integration test script is provided to verify the end-to-end order flow, including product creation, authentication, price calculation, and Kafka event processing. Run it using:
```bash
uv run --with httpx python test_order_process.py
```

## Development

* The order service relies on FastAPI, SQLAlchemy, asyncpg, and FastStream.
* The inventory service uses Django, Django REST Framework, and psycopg.
