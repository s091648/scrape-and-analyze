def test_tag_mode_values():
    from src.shared.domain.value_objects.tag_mode import TagMode
    assert TagMode.UNSUPERVISED == 'unsupervised'
    assert TagMode.SEMI_SUPERVISED == 'semi_supervised'
    assert TagMode.SUPERVISED == 'supervised'


def test_tag_mode_is_str():
    from src.shared.domain.value_objects.tag_mode import TagMode
    assert isinstance(TagMode.UNSUPERVISED, str)


def test_tag_mode_from_string():
    from src.shared.domain.value_objects.tag_mode import TagMode
    assert TagMode('unsupervised') is TagMode.UNSUPERVISED
    assert TagMode('semi_supervised') is TagMode.SEMI_SUPERVISED
    assert TagMode('supervised') is TagMode.SUPERVISED
