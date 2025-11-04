from fastapi import Form


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
