# Makefile — shortcuts for common Docker commands
# Usage: make <target>
# e.g.:  make up, make down, make logs

.PHONY: up down build logs shell ps clean test

# Build and start all services in the background
up:
	docker-compose up --build -d

# Stop and remove containers (keeps volumes)
down:
	docker-compose down

# Build images without starting
build:
	docker-compose build

# Tail logs from the API service
logs:
	docker-compose logs -f api

# Tail logs from all services
logs-all:
	docker-compose logs -f

# Open a shell inside the running API container
shell:
	docker-compose exec api bash

# Show running containers
ps:
	docker-compose ps

# Stop containers AND remove volumes (wipes database)
clean:
	docker-compose down -v

# Run tests inside the container
test:
	docker-compose exec api python -m pytest tests/ -v

# Check API health
health:
	curl -s http://localhost:8000/health | python3 -m json.tool
