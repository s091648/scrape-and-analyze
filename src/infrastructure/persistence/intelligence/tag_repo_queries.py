from typing import List, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from src.infrastructure.persistence.shared.pgvector import to_pgvector_literal


def find_similar_tags_stmt(
    embedding: List[float], group_name: str, topic_id: UUID, threshold: float
) -> Tuple[TextClause, dict]:
    """Build the pgvector nearest-neighbor SQL + params for finding similar tags
    within a group/topic. Shared by SqlAlchemyTagRepository and
    AsyncSqlAlchemyTagRepository — execution (sync vs `await`) stays with the caller."""
    stmt = text("""
        SELECT t.id, t.name, tgd.name AS group_name,
               1 - (t.embedding <=> CAST(:vec AS vector)) AS similarity
        FROM tags t
        JOIN tag_group_definitions tgd ON tgd.id = t.tag_group_id
        WHERE tgd.name = :group_name
          AND tgd.topic_id = :topic_id
          AND t.embedding IS NOT NULL
          AND (1 - (t.embedding <=> CAST(:vec AS vector))) >= :threshold
        ORDER BY t.embedding <=> CAST(:vec AS vector)
        LIMIT 5
    """)
    params = {
        "vec": to_pgvector_literal(embedding),
        "group_name": group_name,
        "topic_id": str(topic_id),
        "threshold": threshold,
    }
    return stmt, params


def update_tag_embedding_stmt(tag_id: UUID, embedding: List[float]) -> Tuple[TextClause, dict]:
    """Build the SQL + params for CASTing an embedding into a tag's `embedding` column."""
    stmt = text("UPDATE tags SET embedding = CAST(:vec AS vector) WHERE id = :id")
    params = {"vec": to_pgvector_literal(embedding), "id": str(tag_id)}
    return stmt, params
