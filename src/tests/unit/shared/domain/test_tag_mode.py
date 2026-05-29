import pytest


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


def test_tag_mode_invalid_value_raises():
    from src.shared.domain.value_objects.tag_mode import TagMode
    with pytest.raises(ValueError):
        TagMode('invalid_mode')


def test_tag_mode_serialization_roundtrip():
    from src.shared.domain.value_objects.tag_mode import TagMode
    for mode in TagMode:
        assert TagMode(mode.value) is mode
    assert TagMode('unsupervised').value == 'unsupervised'
    assert TagMode('semi_supervised').value == 'semi_supervised'
    assert TagMode('supervised').value == 'supervised'
