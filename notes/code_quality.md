# Linters + formatters

We follow mostly pep8.

Line width is 88 (standard black).

For exceptions see [.flake8](../.flake8)

## Run lint

Run linting:

```bash
make lint
```

Check linting:

```bash
bash scripts/lint-check.sh
```


## Setup pre-commit

```bash
poetry run pre-commit install
```


## Black

Formats code

```bash
poetry run black .
```


## Isort

Sorts imports

```bash
poetry run isort .
```


## Autoflake

Removes unused imports and unused variables.

```bash
poetry run autoflake --in-place --recursive --ignore-init-module-imports --expand-star-imports --remove-unused-variables .
```


## Flake8

Used for enforcing style guide. This will not format anything.

```bash
poetry run flake8 .
```


## Mypy

Static type checking. Doesn't format anything.

```bash
poetry run mypy .
```


## Run all

```bash
poetry run black . && poetry run isort . && poetry run autoflake -i -r --ignore-init-module-imports --expand-star-imports --remove-unused-variables . && poetry run flake8 . && poetry run mypy .
```

