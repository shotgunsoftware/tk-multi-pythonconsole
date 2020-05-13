# -*- coding: utf-8 -*-
# Copyright (c) 2020 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

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

    QtGui.QApplication([])
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
    with pytest.raises(ImportError):
        import sgtk  # noqa


def test_import_app(set_environment):
    """
    Test that we can import the app.
    There should be no dependency on having sgtk present.
    :return:
    """
    import app  # noqa


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
    # another tab. Create two tabs so that we can test this behavior.
    console_widget.tabs.add_tab()
    console_widget.tabs.add_tab()
    assert console_widget.tabs.count() == 2
    # Check that when have two tabs and we remove one, we only have one left.
    console_widget.tabs.remove_tab(0)
    assert console_widget.tabs.count() == 1
    # Check that when we remove the last tab, we still have one tab,
    # due to it automatically creating one.
    console_widget.tabs.remove_tab(0)
    assert console_widget.tabs.count() == 1


@pytest.mark.parametrize(
    "script",
    [
        ("resource_script.py"),
        ("resource_script_containing_unicode.py"),
        ("resource_script_surrogate_chars.py"),
    ],
)
def test_open_script(console_widget, current_path, script):
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
        # Check that it handles error in an expected way.
        ("resource_script_error.py", 2, "NameError: name 'b' is not defined"),
        # Only compare the contents of this one in Python 3
        ("resource_script_containing_unicode.py", 3, "›š™º"),
        ("resource_script_surrogate_chars.py", 3, "𐀀𝄞"),
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
    # Due to the way the Python 2 handles the unicode, the output will come out differently compared to Python 3.
    # So we are only checking some of the tests in Python 3.
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


# fmt: off
@pytest.mark.parametrize(
    "script, altered_script, operation, selection_range",
    [
        # test adding an indent. Should round up to the nearest for spaces.
        (
            # source
            "a = 1\n"
            "    b = 2\n"
            " c = 3",
            # result
            "    a = 1\n"
            "        b = 2\n"
            "    c = 3",
            # action
            "indent",
            # cursor selection start and end position (None selects all)
            None,
        ),
        # test unindenting. Should round up to the nearest for spaces.
        (
            # source
            "a = 1\n"
            "    b = 2\n"
            " c = 3\n"
            "        d = 4\n"
            "     e = 5",
            # result
            "a = 1\n"
            "b = 2\n"
            "c = 3\n"
            "    d = 4\n"
            "    e = 5",
            # action
            "unindent",
            # cursor selection start and end position (None selects all)
            None,
        ),
        # test adding a comment
        (
            # source
            "a = 1\n"
            "    # b = 2\n"
            " c = 3\n"
            "        d = 4",
            # result
            "# a = 1\n"
            "#     # b = 2\n"
            "#  c = 3\n"
            "#         d = 4",
            # action
            "comment",
            # cursor selection start and end position (None selects all)
            None,
        ),
        # test removing a comment
        (
            # Source
            "# a = 1\n"
            "    # b = 2",
            # result
            "a = 1\n"
            "    b = 2",
            # action
            "comment",
            # cursor selection start and end position (None selects all)
            None,
        ),
        # test comments being added at the correct level of indentation
        (
            # source
            "    a = 1\n"
            "    b = 2",
            # result
            "    # a = 1\n"
            "    # b = 2",
            # action
            "comment",
            # cursor selection start and end position (None selects all)
            None
        ),
        # test removing character when cursor in indentation
        (
            # source
            "    a = 1",
            # result
            "a = 1",
            # action
            "delete",
            # cursor selection start and end position
            (4, 4)
        ),
        # test removing character when cursor in indentation
        (
            # source
            "     a = 1",
            # result
            "    a = 1",
            # action
            "delete",
            # cursor selection start and end position
            (4, 4)),
        # test removing character when cursor not in indentation
        (
            # source
            "    a = 1",
            # result
            "    a = ",
            # action
            "delete",
            # cursor selection start and end position
            (9, 9)),
        # test adding a new line
        (
            # source
            "    a = 1",
            # result
            "    a = 1\n"
            "    ",
            # action
            "new_line",
            # cursor selection start and end position
            (9, 9)),
        # test adding a to a new line to a selection
        (
            # source
            "    a = 1",
            # result
            "    a\n"
            "    ",
            # action
            "new_line",
            # cursor selection start and end position
            (5, 9)),
        # test adding a new line after a colon, it should auto indent by 4
        (
            # source
            "    def test(): ",
            # result
            "    def test(): \n"
            "        ",
            # action
            "new_line",
            # cursor selection start and end position
            (16, 16)),
        # test adding a new line after a colon with an inline comment, it should auto indent by 4
        (
            # source
            "def test(): # asd#.",
            # result
            "def test(): # asd#.\n"
            "    ",
            # action
            "new_line",
            # cursor selection start and end position
            (19, 19)),
        # test adding a new line with the selection before the colon, it should indent to the same level.
        (
            # source
            "    def test(): ",
            # result
            "    def test(\n"
            "    ): ",
            # action
            "new_line",
            # cursor selection start and end position
            (13, 13)),
    ],
)
# fmt: on
def test_block_text_operations(
    console_widget, script, altered_script, operation, selection_range
):
    """
    Supports testing adding and removing comments and indents from a selection of lines.
    :param console_widget: QWidget
    :param script: str
    :param altered_script: str
    :param operation: str
    :return:
    """
    from app.qt_importer import QtCore, QtGui

    console_widget.tabs.add_tab()

    input_widget = console_widget.tabs.widget(0).input_widget

    input_widget.setPlainText(script)

    cur = input_widget.textCursor()

    if selection_range is None:
        # Select all the text
        cur.movePosition(QtGui.QTextCursor.Start)
        cur.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.KeepAnchor)
    else:
        cur.setPosition(selection_range[0])
        cur.setPosition(selection_range[1], QtGui.QTextCursor.KeepAnchor)

    input_widget.setTextCursor(cur)
    QtCore.QCoreApplication.processEvents()

    modifier = QtCore.Qt.NoModifier
    if operation == "indent":
        key = QtCore.Qt.Key_Tab
    elif operation == "unindent":
        key = QtCore.Qt.Key_Backtab
    elif operation == "comment":
        key = QtCore.Qt.Key_Slash
        modifier = QtCore.Qt.ControlModifier
    elif operation == "delete":
        key = QtCore.Qt.Key_Backspace
    elif operation == "new_line":
        key = QtCore.Qt.Key_Return

    # Now simulate the key press for the correct operation.
    event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, modifier)
    QtCore.QCoreApplication.postEvent(input_widget, event)
    QtCore.QCoreApplication.processEvents()

    # Get the resulting text and check it matches what we expect from the operation.
    tab_contents = input_widget.toPlainText()
    assert tab_contents == altered_script, (
        '(The operation being performed was "%s")' % operation
    )
