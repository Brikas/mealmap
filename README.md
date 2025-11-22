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

## Recommendation Feed (Food TikTok)

The meal recommendation system combines user swipes with high-rated reviews to build a personalized queue.  
Key pieces you might need:

- Seed local data (10 users × 5 reviews each + likes):

    ```bash
    poetry run python admin/seed_recommendation_data.py
    ```

- Notebook demo: `admin/recommendation_test.ipynb` (run all cells to see top picks for a sample user).
- API: `GET /users/me/feed?limit=20` returns the pre-ranked queue for the authenticated user.
- Queue regeneration: if a user’s `user_feed_item` table is empty, the backend automatically recomputes their feed using the latest reviews/ratings.

Use this section as the canonical reference when hooking up the frontend swipe/scroll experience.

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
