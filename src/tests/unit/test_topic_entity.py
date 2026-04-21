def test_topic_entity_defaults():
    from src.domain.entities.topic import TopicEntity
    t = TopicEntity(name="digital-twins", display_name="Digital Twins")
    assert t.id is None
    assert t.is_active is True
    assert t.prompt_override is None
    assert t.color_hex is None
