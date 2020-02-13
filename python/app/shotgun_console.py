# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys

import sgtk
from sgtk.errors import TankError
from sgtk.platform.engine import current_engine
from sgtk.platform.qt import QtCore, QtGui

settings = sgtk.platform.import_framework("tk-framework-shotgunutils", "settings")

from .console import PythonConsoleWidget


class ShotgunPythonConsoleWidget(PythonConsoleWidget):
    """A dockable, interactive, Shotgun-aware python console widget.

    Exposes Shotgun-specific globals by default in the editor. Similar to the
    tk-shell engine.

    - A tk API handle is available via the `tk` variable
    - A Shotgun API handle is available via the `shotgun` variable
    - The current context is stored in the `context` variable
    - The shell engine can be accessed via the `engine` variable

    """

    def __init__(self, parent=None):
        """
        Initialize the console widget.

        :param parent: The console's parent widget.
        """

        super(ShotgunPythonConsoleWidget, self).__init__(parent)

        engine = current_engine()
        self._settings_manager = settings.UserSettings(sgtk.platform.current_bundle())

        # if not running in an engine, then we're hosed
        if not engine:
            raise TankError(
                "Unable to initialize ShotgunPythonConsole. No engine running"
            )

        # add a welcome message to the output widget
        welcome_message = (
            "Welcome to the Shotgun Python Console!\n\n"
            "Python %s\n\n"
            "- A tk API handle is available via the 'tk' variable\n"
            "- A Shotgun API handle is available via the 'shotgun' variable\n"
            "- Your current context is stored in the 'context' variable\n"
            "- The shell engine can be accessed via the 'engine' variable\n\n"
            % (sys.version,)
        )

        add_sg_globals = lambda i: self.tabs.widget(i).input_widget.add_globals(
            self._get_sg_globals()
        )

        # lambda to add the welcome message to a tab at a given index
        add_welcome_msg = lambda i: self.tabs.widget(i).output_widget.add_input(
            welcome_message, prefix=None
        )

        # set globals as new tabs are created
        self.tabs.tab_added.connect(add_sg_globals)

        # when a new tab is added, add the welcome message
        self.tabs.tab_added.connect(add_welcome_msg)

        # try to restore previous tabs
        scope = self._settings_manager.SCOPE_ENGINE

        tab_info_list = self._settings_manager.retrieve("tab_info", None, scope)

        if tab_info_list:
            for tab_info in tab_info_list:
                index = self.tabs.add_tab(
                    name=tab_info.get("tab_name"),
                    contents=tab_info.get("tab_contents"),
                )
        else:
            self.tabs.add_tab()

        cur_tab_index = self._settings_manager.retrieve("current_tab", None, scope)
        if cur_tab_index is not None:
            self.tabs.setCurrentIndex(cur_tab_index)

        # make sure the settings are saved before the application quits
        app = QtGui.QApplication.instance()
        app.aboutToQuit.connect(self._save_settings)

    def closeEvent(self, event):
        """
        Handles saving settings for the console before it is closed.
        """

        # closing. disconnect this instance from the about to quit signal
        app = QtGui.QApplication.instance()
        app.aboutToQuit.disconnect()

        self._save_settings()
        super(ShotgunPythonConsoleWidget, self).closeEvent(event)

    def _get_sg_globals(self):
        """
        Returns a dict of sg globals for the current engine.
        """

        engine = current_engine()
        return {
            "tk": engine.tank,
            "shotgun": engine.shotgun,
            "context": engine.context,
            "engine": engine,
        }

    def _save_settings(self):
        """
        Save the current tab settings for the session.
        """
        scope = self._settings_manager.SCOPE_ENGINE
        self._settings_manager.store("tab_info", self.tabs.get_tab_info(), scope)
        self._settings_manager.store("current_tab", self.tabs.currentIndex(), scope)

    def _build_open_file_menu(self):
        """
        Dynamically build the popup menu for the file open/load button.
        This is called when the menu is triggered via a delayed load.
        The user must click and hold the open button to trigger the menu building.
        """

        super(ShotgunPythonConsoleWidget, self)._build_open_file_menu()

        app = sgtk.platform.current_bundle()

        # get a list of tuples for the external source types
        actions = app.execute_hook_method(
            "external_sources_hook",
            "get_external_source_actions",
            parent_obj=self._open_file_menu,
        )

        for action in actions:
            self._open_file_menu.addAction(action)
