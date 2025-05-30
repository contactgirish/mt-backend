from typing import Set

blocked_user_ids: Set[int] = set()

def set_blocked_users(user_ids: list[int]):
    global blocked_user_ids
    blocked_user_ids = set(user_ids)

def is_user_blocked(user_id: int) -> bool:
    return user_id in blocked_user_ids