from typing import NamedTuple


class TagGroup(NamedTuple):
    """Value object representing a tag group with display name, description, and optional DB key."""
    display_name: str
    description: str
    name: str = ""  # DB key (snake_case), used in fixed mode prompt rendering
