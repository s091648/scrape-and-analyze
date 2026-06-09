from typing import List, NamedTuple


class AnalysisTagGroup(NamedTuple):
    """Value object pairing a tag group name with its list of tag strings."""
    group_name: str
    tags: List[str]
