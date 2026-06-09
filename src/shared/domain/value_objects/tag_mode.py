from enum import Enum


class TagMode(str, Enum):
    """Enum controlling how tags are assigned: unsupervised, semi-supervised, or supervised."""
    UNSUPERVISED = 'unsupervised'
    SEMI_SUPERVISED = 'semi_supervised'
    SUPERVISED = 'supervised'
