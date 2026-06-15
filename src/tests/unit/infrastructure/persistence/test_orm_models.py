def test_topic_model_columns():
    from models.topic import Topic
    cols = {c.name for c in Topic.__table__.columns}
    assert cols >= {"id", "name", "display_name", "prompt_override", "is_active"}


def test_article_model_has_topic_id():
    from models.article import Article
    assert "topic_id" in {c.name for c in Article.__table__.columns}


def test_tag_group_model_has_topic_id():
    from models.tag_group import TagGroupDefinition
    assert "topic_id" in {c.name for c in TagGroupDefinition.__table__.columns}


def test_scraper_setting_model_has_topic_id():
    from models.scraper_setting import ScraperSetting
    assert "topic_id" in {c.name for c in ScraperSetting.__table__.columns}
