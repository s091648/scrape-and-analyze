from enum import Enum


class TagMode(str, Enum):
    UNSUPERVISED = 'unsupervised'
    SEMI_SUPERVISED = 'semi_supervised'
    SUPERVISED = 'supervised'
