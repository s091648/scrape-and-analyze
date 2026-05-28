from typing import NamedTuple


class TagGroup(NamedTuple):
    display_name: str
    description: str
    name: str = ""  # DB key (snake_case), used in fixed mode prompt rendering
