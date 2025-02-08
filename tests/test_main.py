from tea_data_file_conversion.main import add


def test_add():
    """Adding two number works as expected."""
    assert add(1, 1) == 2
