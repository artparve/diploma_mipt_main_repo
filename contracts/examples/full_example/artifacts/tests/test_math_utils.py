import pytest
from src.math_utils import average


def test_empty():
    with pytest.raises(ValueError):
        average([])


def test_positive():
    assert average([2, 4]) == 3


def test_negative():
    assert average([-2, -4]) == -3


def test_single():
    assert average([5]) == 5
