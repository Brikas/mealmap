The back-end API for ITEMS marketplace app.

# Quick Notes

## [Useful Commands](quick.md)

# Stack

-   [Python FastAPI]('notes/fast-python.md')
-   PostrgreSQL
-   Poetry
-   Alembic (SQLAlchemy)
-   Docker (or Kuberneter)
-   pydantic
-   S3 storage
-   MessageBird (SMS)

# First time setup

...among many things

-   Install `nbstripout` for jupyter notebook commit output stripping.
-   Copy `.env.example` to `.env` and fill out values.

## [Run](notes/deployment.md)

Build and Run:

```bash
make run
```

Visit: <http://localhost:8000/docs>

Database: localhost:5432

## [Tests](notes/tests.md)

### Unit tests

Run all tests while the api is running:

```bash
make test
```

## [Poetry guide](notes/poetry_guide.md)

Add package:

```bash
poetry add <name>
```

Install from pyproject.toml or poetry.lock:

```bash
poetry install
```

## [Code quality](notes/code_quality.md)

A collection of general rules and guidelines for code style and linting.
