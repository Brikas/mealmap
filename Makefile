all: help

##	By Airidas
.PHONY: db-dump
db-dump:  ## Backup the database to gitignore/db-dumps
	@python3 scripts/db_manage.py dump

.PHONY: db-restore
db-restore: ## Restore the database from gitignore/db-dumps
	@python3 scripts/db_manage.py restore

.PHONY: db-restore-local
db-restore-local: ## Restore the database from a dump inside docker container
	docker exec postgres pg_restore -U postgres -d postgres -c /var/lib/postgresql/data/db_backup.pg_dump

.PHONY: db-reset
db-reset: ## Reset the database (drop public schema and run migrations)
	@python3 scripts/db_manage.py reset

.PHONY: migrate-test
migrate-test: ## Dump the database, apply migrations, and optionally restore
	@python3 scripts/db_manage.py migrate-test

## FROM TEMPLATE

.PHONY: help
help:  ## Show this help
	@echo ""
	@echo "\033[1mFeatured Commands:\033[0m"
	@printf "  \033[36m%-30s\033[0m %s\n" "run" "Run the project"
	@printf "  \033[36m%-30s\033[0m %s\n" "stop" "Stop all running containers"
	@printf "  \033[36m%-30s\033[0m %s\n" "test-local" "Run tests locally"
	@printf "  \033[36m%-30s\033[0m %s\n" "db-reset" "Reset the database"
	@printf "  \033[36m%-30s\033[0m %s\n" "db-dump" "Backup the database to gitignore/db-dumps"
	@printf "  \033[36m%-30s\033[0m %s\n" "db-restore" "Restore the database from gitignore/db-dumps"
	@printf "  \033[36m%-30s\033[0m %s\n" "db-restore-local" "Restore the database from a dump inside docker container"
	@printf "  \033[36m%-30s\033[0m %s\n" "migrate-test" "Dump the database, apply migrations, and optionally restore"
	@echo ""
	@echo "\033[1mAll Commands:\033[0m"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: replace-env
replace-env:  ## Use to update existing .env with .env.example
	cp .env.example .env

.env:  ## Copy .env.example to .env
	cp .env.example .env

install: .env  ## Install dependencies
	poetry install

setup:

clean:

build: .env
	docker compose -f deploy/docker/docker-compose.yml --project-directory . build

stop:  ## Stop all running containers
	docker compose -f deploy/docker/docker-compose.yml --project-directory . stop

full-reset:
	@echo "Stopping all containers..."
	-docker stop $$(docker ps -q)
	@echo "Removing all containers..."
	-docker rm -f $$(docker ps -aq)
	@echo "Removing all volumes..."
	-docker volume rm -f $$(docker volume ls -q)
	@echo "Removing all images..."
	-docker rmi -f $$(docker images -q)
	@echo "Removing all networks (except default)..."
	-docker network prune -f
	@echo "Pruning system..."
	-docker system prune -af --volumes
	@echo "Docker reset complete."


full-stop: ## Stop all running containers
	docker stop $$(docker ps -a -q)

kill: stop  ## Kill all running containers
	docker kill $$(docker ps -a -q)

lint:  ## Run linters
	set -e
	set -x
	poetry run autoflake -i -r --exclude dependencies.py --ignore-init-module-imports --expand-star-imports --remove-unused-variables --remove-all-unused-imports src
	poetry run isort src
	poetry run black src
	git diff --name-only "$$( [[ "$$(git diff --name-only HEAD | wc -l)" == 0 ]] && echo 'HEAD~1' || echo 'HEAD' )" | grep ".py$$" | xargs poetry run yesqa
	poetry run mypy src
	poetry run ruff check . --fix --unsafe-fixes

run: build   ## Run the project
	docker compose -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.local.yml --project-directory . up

run-detached: build   ## Run the project in detached mode
	docker compose -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.local.yml --project-directory . up -d

reboot: kill run  ## Kill all running containers and run the project

.PHONY: remove
remove: # Remove all containers and volumes
	docker compose -f deploy/docker/docker-compose.yml --project-directory . rm -f
	docker volume rm fast-python-db-data

migration-generate:  ## Generate a new migration file
	docker container exec $$(docker ps | grep fast-python-api | awk '{print $$1}') alembic revision --autogenerate

run-pg:  ## Run only PG
	docker compose -f deploy/docker/docker-compose.yml --project-directory . up -d db

setup-local: run-pg  ## Setup to run `python -m src` locally
	poetry run alembic upgrade head
	poetry shell


test-seq: test-all-seq  ## Run all tests

test-all-seq:	## Also run all tests
	docker container exec $$(docker ps | grep fast-python-api | awk '{print $$1}') pytest ./tests/unit

test-coverage-seq:  ## Generate a coverage report
	docker container exec $$(docker ps | grep fast-python-api | awk '{print $$1}') pytest --cov=./src ./tests/pytest

test-filter-seq:  ## Run specific tests. Example: 'make test-filter-seq filter="aspect_member"' to test all AspectMember related tests
	docker container exec $$(docker ps | grep fast-python-api | awk '{print $$1}') pytest ./tests/unit -s -v -k $(filter)

test-local:  ## Run tests locally
	poetry run pytest -vv
