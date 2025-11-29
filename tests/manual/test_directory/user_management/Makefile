.PHONY: help install start test clean

help:
	@echo "Available commands:"
	@echo "  make install    - Install all dependencies"
	@echo "  make start      - Start the development servers"
	@echo "  make test       - Run all tests"
	@echo "  make clean      - Clean build artifacts"
	@echo "  make migrate    - Run database migrations"
	@echo "  make seed       - Seed the database"

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

start:
	docker-compose up -d

stop:
	docker-compose down

test:
	cd backend && pytest
	cd frontend && npm test

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "node_modules" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

migrate:
	psql -U postgres -d app_db -f database/migrations/001_create_users_table.sql
	psql -U postgres -d app_db -f database/migrations/002_create_posts_table.sql

seed:
	psql -U postgres -d app_db -f database/seeds/users_seed.sql
