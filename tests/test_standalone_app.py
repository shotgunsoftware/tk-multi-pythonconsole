# -*- coding: utf-8 -*-
import pytest
import sys
import os
import io


@pytest.fixture(scope="session")
def current_path():
    return os.path.dirname(os.path.realpath(__file__))


@pytest.fixture(scope="session")
def set_environment(current_path):
    """
    Tests the python console standalone without sgtk being present.
    :param current_path:
    :return:
    """
    # Added the path to the console app so it can be imported.
    sys.path.insert(0, current_path + "/../python")

    # make sure tk-core is removed from the path so that
    # we can test the python console app standalone.
    for a_path in reversed(sys.path):
        if "tk-core" in a_path:
            sys.path.remove(a_path)


@pytest.fixture(scope="session")
def imported_app(set_environment):
    import app as console_app
    from app.qt_importer import QtGui

    q_app = QtGui.QApplication([])
    return console_app


@pytest.fixture()
def console_widget(imported_app):
    return imported_app.console.PythonConsoleWidget()


def test_cant_import_sgtk(set_environment):
    """
    Since we are testing the python console app standalone
    make sure we can't import sgtk from tk-core.
    :return:
    """
    print(sys.path)
    with pytest.raises(ImportError):
        import sgtk


def test_import_app(set_environment):
    """
    Test that we can import the app.
    There should be no dependency on having sgtk present.
    :return:
    """
    import app


def test_create_tab(console_widget):
    """
    Test that we can create a new python editor tab on the `PythonConsoleWidget`.
    :return:
    """
    console_widget.tabs.add_tab()
    assert console_widget.tabs.count() == 1


def test_remove_tab(console_widget):
    """
    Test that we can remove a python editor tab on the `PythonConsoleWidget`.
    :return:
    """
    # We should have a fresh console_widget so no tabs will yet be created
    assert console_widget.tabs.count() == 0
    # By default the standalone console doesn't have a tab inserted and
    # it is up to the person invoking it to created the first tab.
    # However if you remove the last tab it will automatically create
    # another tab.
    console_widget.tabs.add_tab()
    console_widget.tabs.add_tab()
    assert console_widget.tabs.count() == 2
    # Check that when have to tabs and we remove one, we only have one left.
    console_widget.tabs.remove_tab(0)
    assert console_widget.tabs.count() == 1
    # Check that when we remove the last tab, we still have one tab,
    # due to it automatically creating one.
    console_widget.tabs.remove_tab(0)
    assert console_widget.tabs.count() == 1


@pytest.mark.parametrize(
    "script, python_version",
    [
        ("resource_script.py", 2),
        # only compare the contents of this one in Python 3
        ("resource_script_containing_unicode.py", 3),
        ("resource_script_surrogate_chars.py", 3),
    ],
)
def test_open_script(console_widget, current_path, script, python_version):
    """
    Test opening a script in a new tab and ensuring the contents of the input widget
    are the same as the original script.
    :param console_widget:
    :return:
    """
    script = os.path.join(current_path, script)
    console_widget.open(script)
    # make sure it created a new tab for the script
    assert console_widget.tabs.count() == 1

    if python_version <= sys.version_info.major:
        # Check the contents of the widget.
        # The contents won't be the same in python 2,
        # so only tests the files whose python_version is the same or less than
        # the current python major version.
        widget = console_widget.tabs.widget(0)
        tab_contents = widget.input_widget.toPlainText()
        with io.open(script, "r", encoding="utf-8") as f:
            original_contents = f.read()

        assert tab_contents == original_contents


@pytest.mark.parametrize(
    "script, python_version, expected_output",
    [
        ("resource_script.py", 2, "open script"),
        # Only compare the contents of this one in Python 3
        ("resource_script_containing_unicode.py", 3, "›š™º"),
        ("resource_script_surrogate_chars.py", 3, "𐀀𝄞"),
        # Check that it handles error in an expected way.
        ("resource_script_error.py", 2, "NameError: name 'b' is not defined"),
    ],
)
def test_execute_script(
    console_widget, current_path, script, python_version, expected_output
):
    """
    Test opening a script in a new tab and executing it.
    :param console_widget:
    :return:
    """
    # Check that test's required python version the current version or below.
    if python_version <= sys.version_info.major:
        script = os.path.join(current_path, script)
        console_widget.open(script)

        tab_widget = console_widget.tabs.widget(0)
        # Get the Python console to execute the script
        tab_widget.input_widget.execute()

        # The output text will add a `\n` to the end so we should add that to the expected output.
        expected_output += "\n"
        actual_output = tab_widget.output_widget.toPlainText()[-len(expected_output) :]

        # Now check that the expected output was added to the end of the output widget text.
        assert actual_output == expected_output
