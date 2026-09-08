.PHONY: venv up down logs psql trino lint test

venv:
	python -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f airflow-scheduler

psql:
	docker compose exec postgres-oltp psql -U oltp -d oltp

trino:
	docker compose exec trino trino

lint:
	ruff check .
	sqlfluff lint sql/

test:
	pytest -q
