# Deployment

-   [Deployment](#deployment)
    -   [First time](#first-time)
    -   [Deploy local](#deploy-local)
    -   [Deploy with different environment](#deploy-with-different-environment)
    -   [Kubernetes](#kubernetes)
    -   [Reset API](#reset-api)

## Setup

### [MacOS](local_setup_macos)

### Windows

Install Python 3.11
Install `make`
You can use [Chocolatey](https://chocolatey.org/install)
Run PowerShell as administrator ->

```bash
choco install make
```

Install `poetry`

```bash
pip install poetry
```

Initialize `peotry`

```bash
poetry install
```

`alembic` is automatically installed by poetry

## First time

Build:

```bash
make build
```

## Deploy local

Start a project with:

```bash
make run
```

Build and Deploy (sudo):

```bash
sudo docker-compose -f deploy/docker-compose.yml --project-directory . build && sudo docker-compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --project-directory . up
```

## Deploy with different environment

Use the different environments when running the api on a hosted server. This will also run the api with monitoring.

```bash
make run-dev
```

The environments are `dev`, `qa`, `prod`, etc.

## Kubernetes

To run your app in kubernetes
just run:

```bash
kubectl apply -f deploy/kube
```

It will create needed components.

If you haven't pushed to docker registry yet, you can build image locally.

```bash
docker-compose -f deploy/docker-compose.yml --project-directory . build
docker save --output fast-python.tar fast-python:latest
```

## Reset API

Stop api:

```bash
make kill
```

Reset api (`warning`: This removes all containers (also non-fast-python containers) and fast-python image):

```bash
make reset
```

Reset database

```bash
make reset-db
```

Reset api + database

```bash
make reset-full
```
