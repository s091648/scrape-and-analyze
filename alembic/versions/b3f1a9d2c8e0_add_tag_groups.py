# alembic/versions/b3f1a9d2c8e0_add_tag_groups.py
"""add_tag_groups

Revision ID: b3f1a9d2c8e0
Revises: f9a54cc49040
Create Date: 2026-03-02
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

revision: str = 'b3f1a9d2c8e0'
down_revision: Union[str, Sequence[str], None] = 'da18741c2135'
branch_labels = None
depends_on = None

_TAG_GROUPS = [
    ('digital_twin',              'Digital Twin',                '#6366f1',
     'Virtual replicas, real-time synchronization, twin lifecycle, model fidelity, twin platforms', 1),
    ('ai_ml',                     'AI & Machine Learning',       '#f59e0b',
     'Predictive analytics, deep learning, anomaly detection, generative AI, inference', 2),
    ('iot_sensing',               'IoT & Sensing',               '#10b981',
     'Sensors, edge computing, telemetry, MQTT/OPC-UA, real-time data collection', 3),
    ('simulation_modeling',       'Simulation & Modeling',       '#3b82f6',
     'Physics simulation, FEA, CFD, 3D modeling, game engines, digital mockups', 4),
    ('manufacturing_industry',    'Manufacturing & Industry 4.0','#ef4444',
     'Factories, industrial automation, supply chain, process optimization, robotics', 5),
    ('construction_smart_cities', 'Construction & Smart Cities', '#8b5cf6',
     'BIM, civil engineering, urban planning, smart infrastructure, building management', 6),
    ('software_devops',           'Software & DevOps',           '#06b6d4',
     'APIs, cloud architecture, cybersecurity, data pipelines, deployment, QA', 7),
    ('other_applications',        'Other Applications',          '#6b7280',
     'Healthcare, energy, transportation, aerospace, agriculture — any domain not above', 8),
]


def upgrade() -> None:
    op.create_table(
        'tag_group_definitions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('color_hex', sa.String(7)),
        sa.Column('description', sa.Text()),
        sa.Column('sort_order', sa.Integer()),
    )

    tgd = sa.table(
        'tag_group_definitions',
        sa.column('id', postgresql.UUID(as_uuid=True)),
        sa.column('name', sa.String),
        sa.column('display_name', sa.String),
        sa.column('color_hex', sa.String),
        sa.column('description', sa.Text),
        sa.column('sort_order', sa.Integer),
    )
    op.bulk_insert(tgd, [
        {
            'id': uuid.uuid4(),
            'name': name,
            'display_name': display_name,
            'color_hex': color_hex,
            'description': description,
            'sort_order': sort_order,
        }
        for name, display_name, color_hex, description, sort_order in _TAG_GROUPS
    ])

    op.add_column('analyses', sa.Column('tag_groups', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('analyses', 'tag_groups')
    op.drop_table('tag_group_definitions')
