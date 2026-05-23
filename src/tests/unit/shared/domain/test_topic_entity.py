def test_topic_defaults():
    from src.shared.domain.entities import Topic
    t = Topic(name="digital-twins", display_name="Digital Twins")
    assert t.id is None
    assert t.is_active is True
    assert t.prompt_override is None
    assert t.color_hex is None