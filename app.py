# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk


class PythonConsoleApp(sgtk.platform.Application):
    """A python console dialog/panel"""

    def add_tab(self, name=None, contents=None, icon=None):
        """
        Add a new tab.

        :param str name: The name of the new tab or ``None``
        :param str contents: The contents of the new tab's input or ``None``.
        :param icon: The icon to use for the new tab or ``None``.
        :type icon: ``QtGui.QIcon``

        :return: The index of the new tab.
        :rtype: ``int``
        """

        widget = self._current_panel or self._current_dialog

        if widget:
            return widget.tabs.add_tab(name, contents, icon)

        raise sgtk.TankError("There is no current panel or dialog to add a tab to.")

    def init_app(self):
        """
        Called as the application is being initialized
        """

        # first, we use the special import_module command to access the app module
        # that resides inside the python folder in the app. This is where the actual UI
        # and business logic of the app is kept. By using the import_module command,
        # toolkit's code reload mechanism will work properly.
        app_payload = self.import_module("app")

        # now register a panel, this is to tell the engine about the our panel ui
        # that the engine can automatically create the panel - this happens for
        # example when a saved window layout is restored in Nuke or at startup.
        self._unique_panel_id = self.engine.register_panel(self.create_panel)

        # also register a menu entry on the shotgun menu so that users
        # can launch the panel
        self.engine.register_command(
            "Shotgun Python Console...",
            self.create_panel,
            {"type": "context_menu", "short_name": "python_console"},
        )

    def create_dialog(self):
        """
        Shows the panel as a dialog.

        Contrary to the create_panel() method, multiple calls
        to this method will result in multiple windows appearing.

        :returns: The widget associated with the dialog.
        """
        app_payload = self.import_module("app")
        widget = self.engine.show_dialog(
            "Python Console",
            self,
            app_payload.shotgun_console.ShotgunPythonConsoleWidget,
        )
        self._current_dialog = widget
        return widget

    def create_panel(self):
        """
        Shows the UI as a panel.
        Note that since panels are singletons by nature,
        calling this more than once will only result in one panel.

        :returns: The widget associated with the panel.
        """
        app_payload = self.import_module("app")

        # start the UI
        try:
            widget = self.engine.show_panel(
                self._unique_panel_id,
                "Shotgun Python Console",
                self,
                app_payload.shotgun_console.ShotgunPythonConsoleWidget,
            )
        except AttributeError as e:
            # just to gracefully handle older engines and older cores
            self.log_warning(
                "Could not execute show_panel method - please upgrade "
                "to latest core and engine! Falling back on show_dialog. "
                "Error: %s" % e
            )
            widget = self.create_dialog()
        self._current_panel = widget

        return widget
