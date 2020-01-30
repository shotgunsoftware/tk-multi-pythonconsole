import sys
import os
import pytest

# Tests the python console standalone without sgtk being present.
current_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, current_path + "/../python")

# make sure tk-core is removed from the path so that
# we can test the python console app standalone.
for a_path in reversed(sys.path):
    if "tk-core" in a_path:
        sys.path.remove(a_path)


def test_cant_import_sgtk():
    """
    Since we are testing the python console app standalone
    make sure we can't import sgtk from tk-core.
    :return:
    """
    with pytest.raises(ImportError):
        import sgtk


def test_import_app():
    """
    Test that we can import the app.
    There should be no dependency on having sgtk present.
    :return:
    """
    import app
