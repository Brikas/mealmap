import base64
from pathlib import Path
from typing import Dict


def auth_json_headers(token: str) -> dict:
    return {"Content-Type": "application/json", "Authorization": "Bearer " + token}


def emailOrPhone(user: dict) -> str:
    """
    Returns the email or phone number of the user.
    If both are present, returns email.
    If neither is present, raises ValueError.
    """
    if "email" in user and user["email"]:
        return user["email"]
    elif "phone_number" in user and user["phone_number"]:
        return user["phone_number"]
    else:
        raise ValueError("User must have either an email or a phone number")

def lookup_idToken_from_email(email: str, users: list) -> str:
    for user in users:
        if user["email"] == email:
            return user["idToken"]
    raise ValueError(f"User with email {email} not found")


def get_user_from_email(email: str, users: list) -> dict:
    for user in users:
        if "email" not in user:
            continue
        if user["email"] == email:
            return user
    raise ValueError(f"User with email {email} not found")

def get_user_from_phone_number(phone_number: str, users: list) -> dict:
    for user in users:
        if "phone_number" not in user:
            continue  # Skip users without a phone number
        if user["phone_number"] == phone_number:
            return user
    raise ValueError(f"User with phone number {phone_number} not found")

def get_user_from_id(user_id: str, users: list) -> dict:
    for user in users:
        if user["id"] == user_id:
            return user
    raise ValueError(f"User with id {user_id} not found")




def encode_base64_image_or_none(image_path: str | None) -> str | None:
    """Encodes an image to a base64 string."""
    if image_path is None:
        return None

    with Path(image_path).open("rb") as image_file:
        image_data = image_file.read()
        return base64.b64encode(image_data).decode("utf-8")

def get_user_from_action_caller(
    action_caller: Dict[str, str], users: list
) -> dict:
    """
    Returns the user from the action caller.
    If the action caller is an email, returns the user with that email.
    If the action caller is a phone number, returns the user with that phone number.
    """
    if "email" in action_caller:
        return get_user_from_email(action_caller["email"], users)
    elif "phone_number" in action_caller:
        return get_user_from_phone_number(action_caller["phone_number"], users)
    else:
        raise ValueError("Action caller must have either email or phone_number")


def find_object_by_identifier(obj_data: dict, obj_list: list, identifier_key: str = 'test_id') -> dict | None:
    """
    Finds an existing object in obj_list by identifier.

    Tries primary identifier first, then falls back to 'id'.

    Args:
        obj_data: The object data to search for
        obj_list: The list of objects to search in
        identifier_key: Primary identifier to search by ('test_id' or 'id')

    Returns:
        The matched object reference or None if not found
    """
    # Try to find by primary identifier
    if identifier_key in obj_data:
        for obj in obj_list:
            if identifier_key in obj and obj[identifier_key] == obj_data[identifier_key]:
                return obj

    # If not found by primary identifier, try by 'id' as fallback
    if identifier_key != 'id' and 'id' in obj_data:
        for obj in obj_list:
            if 'id' in obj and obj['id'] == obj_data['id']:
                return obj

    return None


def update_or_add_object(obj_data: dict, obj_list: list, identifier_key: str = 'test_id') -> tuple[dict, bool]:
    """
    Updates an existing object in obj_list or adds it if not found.

    Uses 'id' as a fallback identifier if the primary identifier is not found.

    Args:
        obj_data: The object data to update or add
        obj_list: The list of objects to search in
        identifier_key: Primary identifier to search by ('test_id' or 'id')

    Returns:
        tuple: (updated/added object reference, was_added: bool)
    """
    existing_obj = find_object_by_identifier(obj_data, obj_list, identifier_key)

    if existing_obj:
        # Update existing object
        existing_obj.update(obj_data)
        return existing_obj, False
    else:
        # Not found, add new object
        obj_list.append(obj_data)
        return obj_data, True


def get_user_that_owns_review_with_test_id(review_test_id: str, reviews: list, users: list) -> dict:
    """Get the user who created/owns a specific review by test_id."""
    review = get_review_from_test_id(review_test_id, reviews)

    # Try to get user from the 'user' object first (from API response)
    if "user" in review and "id" in review["user"]:
        return get_user_from_id(review["user"]["id"], users)

    # Fallback to action_caller if user object not present (initial setup)
    if "action_caller" in review:
        action_caller = review["action_caller"]
        if "email" in action_caller:
            return get_user_from_email(action_caller["email"], users)

    raise ValueError(f"Review with test_id {review_test_id} does not have user information")

def get_review_from_id(review_id: str, reviews: list) -> dict:
    """Get a review by its id."""
    for review in reviews:
        if review.get("id") == review_id:
            return review
    raise ValueError(f"Review with id {review_id} not found")

def get_review_from_test_id(test_id: str, reviews: list) -> dict:
    """Get a review by its test_id."""
    for review in reviews:
        if review.get("test_id") == test_id:
            return review
    raise ValueError(f"Review with test_id {test_id} not found")
