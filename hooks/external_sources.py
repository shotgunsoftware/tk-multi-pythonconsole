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

HookBaseClass = sgtk.get_hook_baseclass()


class ExternalSources(HookBaseClass):
    """
    Methods that define external sources for python console tabs.
    """

    def get_external_source_actions(self, parent_obj):
        """
        Return a list of ``QActions`` with options for loading content.

        The actions (or sub actions in the case of returned menu actions) should
        call ``app.add_tab()`` when triggered to add the external content to a
        new tab in the console.

        A parent ``QObject`` is supplied for creating the actions so that they
        do not go out of scope.

        :param parent_obj: The ``QtCore.QObject`` the returned actions should be
            parented under

        :returns: A list of ``QActions``
        """

        return []
