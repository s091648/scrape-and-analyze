from typing import List


def to_pgvector_literal(embedding: List[float]) -> str:
    """Format a float vector as a pgvector literal string, e.g. '[0.1,0.2,0.3]'.

    Shared across any repo that CASTs an embedding into a `vector` column via
    raw SQL (tag/tag-group similarity search today).
    """
    return "[" + ",".join(str(x) for x in embedding) + "]"
