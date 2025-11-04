# Poetry

-   [Poetry](#poetry)
    -   [Install](#install)
    -   [Create new project](#create-new-project)
    -   [Enter VE](#enter-ve)
    -   [Version of Python](#version-of-python)
    -   [Add Dependencies (Poetry)](#add-dependencies-poetry)
    -   [Install dependencies](#install-dependencies)

## Install

[github.com/python-poetry/poetry](https://github.com/python-poetry/poetry)

Install (after this: add to path as described in docs):

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

or use `pip install poetry`.

Add to path:

```bash
source $HOME/.poetry/env
```

## Create new project

Either:

```bash
poetry new [project]
```

or

```bash
poetry init
```

this creates the `pyproject.toml` file where dependencies can be specified (otherwise use `poetry add [package(s)]`).

## Enter VE

To enter virtual environment use

```bash
poetry shell
```

Or use

```bash
poetry env use python
poetry env activate
```

exit with `exit`

## Env location

```bash
poetry env info
```

## Version of Python

Specify which python to use:

```bash
poetry env use $(which python3.9)
```

## Add Dependencies (Poetry)

```bash
poetry add <lib>
```

Add to dev only:

```bash
poetry add <lib> --group dev
```

## Install dependencies

To install dependencies, use:

```bash
poetry install
```

It will use `poetry.lock` file if present, otherwise it will download as described in the `pyproject.toml` file and then create the lock file.

The `poetry.lock` file will specify exactly the dependencies used for install, thus making it consistent for everyone.
