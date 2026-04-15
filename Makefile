# Variables - These MUST match the service names in your docker-compose.yml
COMPOSE = docker-compose
#ORDER_SERVICE = order_service
INVENTORY_SERVICE = inventory_service
RUFF = uv run ruff

.PHONY: help build up down restart logs migrate makemigrations shell test clean

help: ## Show this help menu
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Docker Control ---

build: ## Build or rebuild all service images
	$(COMPOSE) build

up: ## Start all services (Databases, Kafka, FastAPI, Django)
	$(COMPOSE) up -d

down: ## Stop and remove all containers
	$(COMPOSE) down

restart: down up ## Full restart of the system

logs: ## View live output from all services
	$(COMPOSE) logs -f

# --- Service Specific Logic ---

migrate: ## Run migrations for both FastAPI (Alembic) and Django
#	@echo "Updating Order Service Schema..."
#	$(COMPOSE) exec $(ORDER_SERVICE) alembic upgrade head
	@echo "Updating Inventory Service Schema..."
	$(COMPOSE) exec $(INVENTORY_SERVICE) python manage.py migrate

makemigrations: ## Generate new migration files for Django models
	$(COMPOSE) exec $(INVENTORY_SERVICE) python manage.py makemigrations

django-shell: ## Drop into the Django interactive Python shell
	$(COMPOSE) exec $(INVENTORY_SERVICE) python manage.py shell

createsuperuser: ## Create an admin user for the Django dashboard
	$(COMPOSE) exec $(INVENTORY_SERVICE) python manage.py createsuperuser

consume: ## Consume orders from Kafka and update inventory accordingly
	docker-compose exec inventory_service python manage.py consume_orders
# --- Maintenance & Quality ---

## lint: Check code style and quality with ruff
lint:
	$(RUFF) check .

## format: Format code with ruff
format:
	$(RUFF) format .
	
test: ## Run pytest suites for both services
#	@echo "Running Order Service Tests..."
#	$(COMPOSE) exec $(ORDER_SERVICE) pytest
	@echo "Running Inventory Service Tests..."
	$(COMPOSE) exec $(INVENTORY_SERVICE) pytest

clean: ## Deep clean: removes containers, volumes, and python cache files
	$(COMPOSE) down -v
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +