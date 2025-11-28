.PHONY: install migrate run worker test lint clean init shell

# Setup and Installation
install:
	uv sync

# Database operations
migrate:
	uv run python manage.py migrate

init: migrate
	uv run python manage.py init_currencies
	uv run python manage.py init_periodic_tasks

superuser:
	uv run python manage.py createsuperuser

# Running the application
run:
	uv run python manage.py runserver

worker:
	uv run celery -A mycurrency worker -l info

beat:
	uv run celery -A mycurrency beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

shell:

worker-monitor:
	uv run celery -A mycurrency.celery flower

shell:
	uv run python manage.py shell_plus --ipython || uv run python manage.py shell

# Testing and Quality
test:
	uv run python manage.py test

lint:
	uv run ruff check .
	uv run black --check .

format:
	uv run black .
	uv run ruff check . --fix

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
