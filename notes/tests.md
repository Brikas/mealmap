# Tests

- [Tests](#tests)
  - [Recommended method](#recommended-method)
    - [Run with coverage](#run-with-coverage)
  - [Template method](#template-method)
  - [Alternative way to run the tests](#alternative-way-to-run-the-tests)


## Recommended method

Build the application with docker.
Then run with pytest:

```bash
docker container exec $(docker ps | grep fast-python:latest | awk '{print $1}') pytest ./fast-python/tests
```

You can use flags `-vv` to print more details and `-s` for printing standard output.


### Run with coverage

```bash
docker container exec <container_id> coverage run -m pytest .
```


## Template method

If you want to run it in docker, simply run:

```bash
docker-compose -f deploy/docker-compose.yml --project-directory . run --rm api pytest -vv .
docker-compose -f deploy/docker-compose.yml --project-directory . down
```

For running tests on your local machine.

1. you need to start a database.

I prefer doing it with docker:

```bash
docker run -p "5432:5432" -e "POSTGRES_PASSWORD=fast-python" -e "POSTGRES_USER=fast-python" -e "POSTGRES_DB=fast-python" postgres:13.4-buster
```

2. Run the pytest.

```bash
pytest -vv .
```


## Alternative way to run the tests

This will create the api and run tests. However, you need to delete and run the container again to apply changes.

Run with pytest

```bash
docker-compose -f deploy/docker-compose.yml --project-directory . run --rm api pytest -vv .
```

Run tests with coverage:

```bash
docker-compose -f deploy/docker-compose.yml --project-directory . run --rm api coverage run -m pytest -vv .
```

To see coverage, use:

```bash
coverage report
```
