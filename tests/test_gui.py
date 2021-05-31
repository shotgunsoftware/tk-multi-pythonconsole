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
import subprocess
import time
import os
import sys
import sgtk

try:
    from MA.UI import topwindows
except ImportError:
    pytestmark = pytest.mark.skip()


# This fixture will launch tk-run-app on first usage
# and will remain valid until the test run ends.
@pytest.fixture(scope="session")
def host_application(tk_test_project):
    """
    Launch the host application for the Toolkit application.

    TODO: This can probably be refactored, as it is not
     likely to change between apps, except for the context.
     One way to pass in a context would be to have the repo being
     tested to define a fixture named context and this fixture
     would consume it.
    """
    process = subprocess.Popen(
        [
            "python",
            "-m",
            "tk_toolchain.cmd_line_tools.tk_run_app",
            # Allows the test for this application to be invoked from
            # another repository, namely the tk-framework-widget repo,
            # by specifying that the repo detection should start
            # at the specified location.
            "--location",
            os.path.dirname(__file__),
            "--context-entity-type",
            tk_test_project["type"],
            "--context-entity-id",
            str(tk_test_project["id"]),
        ]
    )
    try:
        yield
    finally:
        # We're done. Grab all the output from the process
        # and print it so that is there was an error
        # we'll know about it.
        stdout, stderr = process.communicate()
        sys.stdout.write(stdout or "")
        sys.stderr.write(stderr or "")
        process.poll()
        # If returncode is not set, then the process
        # was hung and we need to kill it
        if process.returncode is None:
            process.kill()
        else:
            assert process.returncode == 0


@pytest.fixture(scope="session")
def app_dialog(host_application):
    """
    Retrieve the application dialog and return the AppDialogAppWrapper.
    """
    before = time.time()
    while before + 60 > time.time():
        if sgtk.util.is_windows():
            app_dialog = AppDialogAppWrapper(topwindows)
        else:
            app_dialog = AppDialogAppWrapper(topwindows["python"])

        if app_dialog.exists():
            yield app_dialog
            app_dialog.close()
            return
    else:
        raise RuntimeError("Timeout waiting for the app dialog to launch.")


class AppDialogAppWrapper(object):
    """
    Wrapper around the app dialog.
    """

    def __init__(self, parent):
        """
        :param root:
        """
        self.root = parent["ShotGrid: ShotGrid Python Console"].get()

    def exists(self):
        """
        ``True`` if the widget was found, ``False`` otherwise.
        """
        return self.root.exists()

    def close(self):
        self.root.buttons["Close"].get().mouseClick()


def test_ui_validation(app_dialog):
    """
    UI validation of the Python Console to make sure all widgets are available.
    """
    # Make sure all buttons and available
    assert app_dialog.root.buttons[
        "Clear all output."
    ].exists(), "Clear all output button is missing"
    assert app_dialog.root.checkboxes[
        "Echo python commands in output."
    ].exists(), "Echo python commands in output checkbox is missing"
    assert app_dialog.root.buttons[
        "Execute the current python script. Shortcut: Ctrl+Enter"
    ].exists(), "Execute current python commands button is missing"
    assert app_dialog.root.buttons[
        "Save current python script to a file."
    ].exists(), "Save current python script to a file button is missing"
    assert app_dialog.root[
        "Load python script from a file."
    ].exists(), "Load python script from a file drop down button is missing"
    assert app_dialog.root.buttons[
        "Clear all input."
    ].exists(), "Clear all input button is missing"
    assert app_dialog.root.checkboxes[
        "Show/hide line numbers."
    ].exists(), "Show/hide line numbers checkbox is missing"
    assert app_dialog.root.buttons[
        "Add a new tab"
    ].exists(), "Add a new tab button is missing"
    assert app_dialog.root.tabs[".py"].exists(), ".py tab is missing"


def test_load_script(app_dialog):
    """
    Make sure Python Console can load and run a python script
    """
    # Load a script
    app_dialog.root["Load python script from a file."].mouseClick()
    app_dialog.root.dialogs["Open Python Script"].waitExist(timeout=30)
    open_script_path = os.path.normpath(
        os.path.expandvars("${TK_TEST_FIXTURES}/files/script/UiAutomationScript.py")
    )
    app_dialog.root.dialogs["Open Python Script"].textfields["File name:"].pasteIn(
        open_script_path, enter=True
    )
    app_dialog.root.tabs["UiAutomationScript.py"].waitExist()
    # Clear output dialog and disable echo python commands
    app_dialog.root.buttons["Clear all output."].mouseClick()
    assert app_dialog.root.captions[""].exists()
    app_dialog.root.checkboxes["Echo python commands in output."].mouseClick()
    assert (
        app_dialog.root.checkboxes["Echo python commands in output."].selected is False
    ), "Echo python commands in output checkbox should be disabled"
    # Run the loaded script
    app_dialog.root.buttons[
        "Execute the current python script. Shortcut: Ctrl+Enter"
    ].mouseClick()
    assert app_dialog.root.captions[
        "0\n1\n2"
    ].exists(), "Print Ci Automation is missing"


def test_save_script(app_dialog):
    """
    Make sure Python Console can save a python script
    """
    # Crate a new tab, run and save a Python script
    app_dialog.root.buttons["Clear all input."].mouseClick()
    app_dialog.root.buttons["Add a new tab"].mouseClick()
    app_dialog.root.textfields.mouseClick()
    app_dialog.root.textfields.pasteIn('print("Hello World!")')
    app_dialog.root.checkboxes["Show/hide line numbers."].mouseClick()
    app_dialog.root.buttons[
        "Execute the current python script. Shortcut: Ctrl+Enter"
    ].mouseClick()
    assert app_dialog.root.captions[
        '*print("Hello World!")\nHello World!'
    ].exists(), "Print Hello World! is missing"
    # Save the updated script
    app_dialog.root.buttons["Save current python script to a file."].mouseClick()
    app_dialog.root.dialogs["Save Python Script"].waitExist(timeout=30)
    save_script_path = os.path.normpath(
        os.path.expandvars(
            "${TK_TEST_FIXTURES}/files/script/UiAutomationScriptUpdated.py"
        )
    )
    app_dialog.root.dialogs["Save Python Script"].textfields["File name:"].pasteIn(
        save_script_path, enter=True
    )
    # Wait until the saved script exist locally
    time_to_wait = 10
    time_counter = 0
    while not os.path.exists(save_script_path):
        time.sleep(1)
        time_counter += 1
        if time_counter > time_to_wait:
            break
    # Validate the saved script exist locally
    assert os.path.isfile(save_script_path)
    # Validate saved script content
    content = open(save_script_path).read()
    assert content == 'print("Hello World!")'
