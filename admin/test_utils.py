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


def get_group_from_id(group_id: str, groups: list) -> dict:
    for group in groups:
        if group["id"] == group_id:
            return group
    raise ValueError(f"Group with id {group_id} not found")


def get_group_from_test_id(test_id: str, groups: list) -> dict:
    for group in groups:
        if group["test_id"] == test_id:
            return group
    raise ValueError(f"Group with test_id {test_id} not found")


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

def group_exists(query_group, group_list) -> bool:
    for g in group_list:
        if 'test_id' in query_group and 'test_id' in g and query_group['test_id'] == g['test_id']:
            return True
        if 'id' in query_group and 'id' in g and query_group['id'] == g['id']:
            return True
    return False

def item_exists(query_item, item_list) -> bool:
    for item in item_list:
        if 'test_id' in query_item and 'test_id' in item and query_item['test_id'] == item['test_id']:
            return True
        if 'id' in query_item and 'id' in item and query_item['id'] == item['id']:
            return True
    return False

def get_item_from_test_id(test_id: str, items: list) -> dict:
    for item in items:
        if item["test_id"] == test_id:
            return item
    raise ValueError(f"Item with test_id {test_id} not found")

def get_item_from_id(item_id: str, items: list) -> dict:
    for item in items:
        if item["id"] == item_id:
            return item
    raise ValueError(f"Item with id {item_id} not found")

def get_user_that_owns_item_with_test_id(
    item_test_id: str, items: list, users: list
    ) -> dict:
    item = get_item_from_test_id(item_test_id, items)

    if "owner" not in item:
        raise ValueError(f"Item with test_id {item_test_id} does not have an owner field")

    owner_object = item["owner"]
    if "id" not in owner_object:
        raise ValueError(f"Owner object of item with test_id {item_test_id} does not have an id field")

    owner_id = owner_object["id"]
    for user in users:
        if user["id"] == owner_id:
            return user
    raise ValueError(f"User with id {owner_id} not found in users list")
