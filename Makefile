.PHONY: install dev down migrate test lint format clean

install:
	pip install poetry
	poetry install --with dev

dev:
	docker-compose up -d

down:
	docker-compose down

migrate:
	cd backend && poetry run alembic upgrade head

migrate-create:
	@read -p "Migration message: " msg; \
	cd backend && poetry run alembic revision --autogenerate -m "$$msg"

test:
	cd backend && poetry run pytest -v

lint:
	cd backend && poetry run flake8 src
	cd backend && poetry run mypy src

format:
	cd backend && poetry run black src
	cd backend && poetry run isort src

clean:
	docker-compose down -v
	docker system prune -f

init: install
	cp .env.example .env
	docker-compose up -d postgres redis
	sleep 5
	$(MAKE) migrate
