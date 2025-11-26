make run

http://localhost:8000/docs

postgres:5432/

(python run)
alembic revision --autogenerate -m "your migration message"
alembic upgrade head

make db-dump
make db-restore

poetry add "pydantic[email]"

detached logs:
docker compose -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.local.yml --project-directory . logs -f

stop gracefully:
docker compose stop
