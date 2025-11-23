import math
from collections import Counter
from typing import List

from fastapi import Form

from src.db.models import MealReview, TriState


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates using Haversine formula (in meters)."""
    R = 6371000  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def form_body(cls: type) -> type:
    """
    Decorator to enable Pydantic models to be used as form bodies in FastAPI endpoints.

    Purpose: Making multipart/form-data endpoints work with Pydantic models with images
    AND work with Swagger UI.

    Explanation/Problem:
    The default official way to do that is using request form models:
    https://fastapi.tiangolo.com/tutorial/request-form-models/
    However, when an Image is included inside the model, Swagger UI wrongly displays
    application/x-www-form-urlencoded as the content-type, even though the endpoint
    accepts multipart/form-data.

    Example:
        @form_body
        class MyForm(BaseModel):
            name: str
            age: int
            tags: Optional[List[str]] = []

        @app.post('/endpoint')
        async def endpoint(my_data: MyForm = Depends(MyForm)):
            return my_data

    References:
    - https://github.com/fastapi/fastapi/discussions/8406
    - https://github.com/fastapi/fastapi/discussions/7268
    - https://fastapi.tiangolo.com/tutorial/request-form-models/

    """
    params = []
    for arg in cls.__signature__.parameters.values():
        arg_type = str(arg).split(":")[1]
        new_arg = arg.replace(default=Form(...))
        if "Optional" in arg_type:
            new_arg = arg.replace(default=Form(None))
        params.append(new_arg)

    cls.__signature__ = cls.__signature__.replace(parameters=params)

    return cls


def calculate_majority_tag(reviews: List[MealReview], attr_name: str) -> str:
    values = [
        getattr(r, attr_name).value
        for r in reviews
        if getattr(r, attr_name) != TriState.unspecified
    ]
    if not values:
        return "unspecified"
    counts = Counter(values)
    yes_count = counts.get("yes", 0)
    no_count = counts.get("no", 0)
    if yes_count > no_count:
        return "yes"
    elif no_count > yes_count:
        return "no"
    return "unspecified"
