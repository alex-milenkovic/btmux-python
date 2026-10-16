"""Strict value conversion and assertions shared by normal APS bindings."""


def boolean(value):
    return {"True": True, "False": False}[value]


def equal(actual, expected):
    assert actual == expected, f"expected {expected!r}, got {actual!r}"


def near(actual, expected):
    assert abs(actual - float(expected)) < 1e-6, f"expected {expected}, got {actual}"
