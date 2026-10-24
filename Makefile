.PHONY: help install dev-backend dev-frontend test ingest docker-up docker-down lint format

help:
	@echo "Available commands:"
	@echo "  make install        Install backend and frontend dependencies"
	@echo "  make dev-backend    Run FastAPI development server"
	@echo "  make dev-frontend   Run Vite React development server"
	@echo "  make ingest         Ingest PDFs from data/pdfs into ChromaDB"
	@echo "  make test           Run test suite with pytest"
	@echo "  make docker-up      Start full stack with Docker Compose"
	@echo "  make docker-down    Stop Docker Compose services"
	@echo "  make lint           Check code quality with ruff"
	@echo "  make format         Auto-format code with black and ruff"

install:
	pip install -r requirements.txt
	cd frontend && npm install

dev-backend:
	uvicorn backend.app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

ingest:
	python -m backend.app.core.ingestion --path data/pdfs

test:
	pytest backend/tests -v

docker-up:
	docker compose up --build

docker-down:
	docker compose down

lint:
	ruff check backend/

format:
	black backend/
	ruff check --fix backend/
