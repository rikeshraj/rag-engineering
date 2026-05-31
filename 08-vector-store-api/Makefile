.PHONY: up down build logs shell ps clean test health

up:
	docker-compose up --build -d

down:
	docker-compose down

build:
	docker-compose build

logs:
	docker-compose logs -f api

logs-all:
	docker-compose logs -f

shell:
	docker-compose exec api bash

ps:
	docker-compose ps

clean:
	docker-compose down -v

test:
	python -m pytest tests/ -v

health:
	curl -s http://localhost:8000/health | python3 -m json.tool

stats:
	curl -s http://localhost:8000/stats \
	  -H "X-API-Key: $$(grep API_KEY .env | cut -d= -f2)" \
	  | python3 -m json.tool
