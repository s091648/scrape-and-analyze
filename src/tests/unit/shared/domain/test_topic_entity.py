def test_topic_defaults():
    from src.shared.domain.entities import Topic
    from src.shared.domain.value_objects.tag_mode import TagMode
    t = Topic(name="digital-twins", display_name="Digital Twins")
    assert t.id is None
    assert t.is_active is True
    assert t.prompt_override is None
    assert t.color_hex is None
    assert t.tag_mode == TagMode.UNSUPERVISED
