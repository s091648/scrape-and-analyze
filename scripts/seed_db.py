#!/usr/bin/env python3
"""
Seed the database with fake data for development/testing.

Usage:
    DATABASE_URL=postgresql://... python scripts/seed_db.py
"""
import os
import sys
import uuid
import hashlib
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def seed():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        from models.topic import Topic
        from models.article import Article
        from models.analysis import Analysis
        from models.analyses_translation import AnalysesTranslation
        from models.tag_group import TagGroupDefinition
        from models.tag import Tag, article_tags
        from models.scraper_keyword import ScraperKeyword

        # ── Topic ──
        topic = db.query(Topic).filter(Topic.name == "digital-twins").first()
        if not topic:
            topic = Topic(
                id=uuid.uuid4(),
                name="digital-twins",
                display_name="Digital Twins",
                description="Digital twin and cyber-physical systems research",
                color_hex="#3B82F6",
                sort_order=1,
                is_active=True,
            )
            db.add(topic)
            db.flush()
            print("  Created topic: digital-twins")
        else:
            print(f"  Topic already exists: {topic.name}")

        # ── Tag Group Definitions ──
        tag_group_defs = [
            {"name": "technology", "display_name": "Technology", "description": "Core technology categories", "color_hex": "#10B981", "sort_order": 1},
            {"name": "industry", "display_name": "Industry", "description": "Industry verticals", "color_hex": "#F59E0B", "sort_order": 2},
            {"name": "methodology", "display_name": "Methodology", "description": "Research methodologies", "color_hex": "#8B5CF6", "sort_order": 3},
        ]
        tag_groups = {}
        for tgd in tag_group_defs:
            existing = db.query(TagGroupDefinition).filter(
                TagGroupDefinition.name == tgd["name"],
                TagGroupDefinition.topic_id == topic.id,
            ).first()
            if existing:
                tag_groups[tgd["name"]] = existing
            else:
                tg = TagGroupDefinition(
                    id=uuid.uuid4(),
                    topic_id=topic.id,
                    **tgd,
                )
                db.add(tg)
                tag_groups[tgd["name"]] = tg
        db.flush()
        print(f"  Tag groups: {len(tag_groups)} ready")

        # ── Tags ──
        tag_defs = [
            ("IoT Sensors", "technology"),
            ("Machine Learning", "technology"),
            ("Simulation", "technology"),
            ("Manufacturing", "industry"),
            ("Healthcare", "industry"),
            ("Predictive Maintenance", "methodology"),
        ]
        tags = {}
        for tag_name, group_name in tag_defs:
            group_def = tag_groups[group_name]
            existing = db.query(Tag).filter(
                Tag.name == tag_name,
                Tag.tag_group_id == group_def.id,
            ).first()
            if existing:
                tags[tag_name] = existing
            else:
                t = Tag(
                    id=uuid.uuid4(),
                    name=tag_name,
                    tag_group_id=group_def.id,
                )
                db.add(t)
                tags[tag_name] = t
        db.flush()
        print(f"  Tags: {len(tags)} ready")

        # ── Articles ──
        now = datetime.now(timezone.utc)
        articles_data = [
            {
                "title": "Digital Twin Framework for Smart Manufacturing",
                "url": "https://example.com/dt-manufacturing-2026",
                "source": "rss",
                "content": "This paper presents a comprehensive digital twin framework for smart manufacturing environments. The framework integrates real-time sensor data with physics-based models to enable predictive maintenance and process optimization.",
            },
            {
                "title": "Healthcare Digital Twins: A Systematic Review",
                "url": "https://example.com/dt-healthcare-review-2026",
                "source": "arxiv",
                "content": "We present a systematic review of digital twin applications in healthcare, covering patient-specific models, hospital operations, and epidemiological simulation.",
            },
            {
                "title": "IoT-Enabled Predictive Maintenance Using Digital Twins",
                "url": "https://example.com/dt-iot-predictive-2026",
                "source": "rss",
                "content": "This study demonstrates how IoT sensor networks can be integrated with digital twin models to predict equipment failures before they occur, reducing downtime by up to 40%.",
            },
            {
                "title": "Simulation-Based Digital Twin for Urban Planning",
                "url": "https://example.com/dt-urban-2026",
                "source": "blog",
                "content": "Urban planners are increasingly using digital twin technology to simulate traffic patterns, energy consumption, and environmental impact before implementing changes.",
            },
            {
                "title": "Machine Learning Enhanced Digital Twin Accuracy",
                "url": "https://example.com/dt-ml-accuracy-2026",
                "source": "arxiv",
                "content": "We propose a hybrid approach combining physics-based simulation with machine learning to improve digital twin prediction accuracy while reducing computational cost.",
            },
        ]
        articles = []
        for i, ad in enumerate(articles_data):
            url_hash = hashlib.sha256(ad["url"].encode()).hexdigest()
            existing = db.query(Article).filter(Article.url == ad["url"]).first()
            if existing:
                articles.append(existing)
            else:
                a = Article(
                    id=uuid.uuid4(),
                    url=ad["url"],
                    url_hash=url_hash,
                    source=ad["source"],
                    title=ad["title"],
                    content=ad["content"],
                    published_at=now - timedelta(days=i),
                    scraped_at=now - timedelta(days=i, hours=1),
                    correlation_id=uuid.uuid4(),
                    topic_id=topic.id,
                )
                db.add(a)
                articles.append(a)
        db.flush()
        print(f"  Articles: {len(articles)} ready")

        # ── Article-Tag Associations ──
        tag_list = list(tags.values())
        tag_assignments = [
            [0, 2, 3],   # Digital Twin Framework -> IoT Sensors, Simulation, Manufacturing
            [1, 4],      # Healthcare Review -> Machine Learning, Healthcare
            [0, 5],      # IoT Predictive -> IoT Sensors, Predictive Maintenance
            [2],         # Urban Planning -> Simulation
            [1, 2],      # ML Accuracy -> Machine Learning, Simulation
        ]
        for art_idx, tag_indices in enumerate(tag_assignments):
            for ti in tag_indices:
                tag = tag_list[ti]
                art = articles[art_idx]
                exists = db.execute(
                    article_tags.select().where(
                        article_tags.c.article_id == art.id,
                        article_tags.c.tag_id == tag.id,
                    )
                ).first()
                if not exists:
                    db.execute(
                        article_tags.insert().values(
                            article_id=art.id, tag_id=tag.id
                        )
                    )
        print("  Article-tag associations created")

        # ── Analyses + Translations ──
        for i, art in enumerate(articles):
            existing_analysis = db.query(Analysis).filter(
                Analysis.article_id == art.id
            ).first()
            if existing_analysis:
                continue
            analysis = Analysis(
                id=uuid.uuid4(),
                article_id=art.id,
                correlation_id=uuid.uuid4(),
                analyzed_at=now - timedelta(days=i, hours=1),
                model_used="gemini-3-flash-preview",
                input_tokens=500 + i * 100,
                output_tokens=200 + i * 50,
            )
            db.add(analysis)
            db.flush()

            translation = AnalysesTranslation(
                id=uuid.uuid4(),
                analysis_id=analysis.id,
                language="en",
                summary=f"Summary of '{art.title}': This research contributes to digital twin approaches with novel frameworks and methodologies.",
                pain_points="Current implementations struggle with real-time data synchronization, model fidelity, and scalability across large deployments.",
                insights="The integration of ML with physics-based models shows promise for reducing computational overhead while maintaining prediction accuracy.",
                innovations="Novel approaches include hybrid simulation-ML pipelines and edge computing architectures for near-real-time twin updates.",
            )
            db.add(translation)
        db.flush()
        print("  Analyses + translations created")

        # ── Scraper Keywords ──
        keyword_defs = [
            ("rss", "digital twin"),
            ("rss", "digital twins"),
            ("rss", "cyber-physical"),
            ("arxiv_keyword", "digital twin"),
        ]
        for kw_type, kw in keyword_defs:
            existing = db.query(ScraperKeyword).filter(
                ScraperKeyword.topic_id == topic.id,
                ScraperKeyword.keyword_type == kw_type,
                ScraperKeyword.keyword == kw,
            ).first()
            if not existing:
                db.add(ScraperKeyword(
                    id=uuid.uuid4(),
                    topic_id=topic.id,
                    keyword_type=kw_type,
                    keyword=kw,
                ))
        print("  Scraper keywords created")

        db.commit()
        print("\nSeed complete. Database is ready for development.")

    except Exception as e:
        db.rollback()
        print(f"ERROR seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
