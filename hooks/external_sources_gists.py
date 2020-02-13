# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import json
import os

import sgtk
from sgtk.platform.qt import QtGui
from tank_vendor.six.moves import urllib

HookBaseClass = sgtk.get_hook_baseclass()

# Note: for this hook to work, a valid env variable called GITHUB_OAUTH_TOKEN
# must be defined with a valid oauth token as a value. A list of github user
# names should be added below

# add a list of github user names here
GITHUB_GIST_USERS = []

# github API url
PUBLIC_GISTS_QUERY_URL = "https://api.github.com/users/%s/gists?access_token=%s"

# cached gists for queried users
QUERIED_GISTS = {}


class ExternalSources(HookBaseClass):
    """
    Methods that define external sources for python console tabs.

    An example for loading github gists is included.
    """

    def get_external_source_actions(self, parent_obj):
        """
        Return a list of ``QActions`` with options for loading content.

        The actions (or sub actions in the case of returned menu actions) should
        call ``app.add_tab()`` when triggered to add the external content to a new
        tab in the console.

        A parent ``QObject`` is supplied for creating the actions so that they
        do not go out of scope.

        :param parent_obj: The ``QtCore.QObject`` the returned actions should be parented under

        :returns: A list of ``QActions``
        """

        return [
            self._get_gists_action(parent_obj),
        ]

    def _get_gists_action(self, parent):
        """
        Returns a ``QtGui.QAction`` for loading gists.

        The returned action is a menu action showing actions for each gist
        for the users defined in ``GITHUB_GIST_USERS``.

        :param parent: The ``QtGui.QObject`` to use as the action's parent
        """

        app = self.parent

        gists_menu = QtGui.QMenu("Gists", parent)

        icon = QtGui.QIcon(":/tk_multi_pythonconsole/github.png")
        gists_menu.setIcon(icon)

        for gist_user in GITHUB_GIST_USERS:

            if not gist_user in QUERIED_GISTS:
                # query gists for this user
                QUERIED_GISTS[gist_user] = get_gists(gist_user, app)

            gists = QUERIED_GISTS[gist_user]

            # no gists for this user, don't create a submenu
            if not gists:
                continue

            # construct a menu for this user
            gist_user_menu = gists_menu.addMenu(gist_user)

            for gist in gists:

                gist_action = QtGui.QAction(gist["file_name"], gist_user_menu)
                # PySide2 seems to pass the checked state through as an args instead of a kwarg
                # so we need to provide a kwarg for it to pass the check state without overriding the gist value.
                add_gist = lambda checked=False, g=gist: self._add_gist_tab(g)
                gist_action.triggered.connect(add_gist)
                gist_user_menu.addAction(gist_action)

        return gists_menu.menuAction()

    def _add_gist_tab(self, gist):
        """
        Adds a new tab for the supplied gist.

        :param gist: A dictionary with information about a gist.
        """

        name = gist["file_name"]

        try:
            contents = urllib.request.urlopen(gist["file_url"]).read()
        except Exception:
            contents = "# Unable to load gist contents... :("

        github_icon = QtGui.QIcon(":/tk_multi_pythonconsole/github.png")

        app = self.parent
        app.add_tab(name, contents, icon=github_icon)


def get_gists(username, app):
    """
    Returns a list of dicts with gist info for a supplied github username.

    :param username: The github username to get gists for.

    """

    if not "GITHUB_OAUTH_TOKEN" in os.environ:
        app.log_debug("No github oauth token found in env.")
        return []

    url = PUBLIC_GISTS_QUERY_URL % (username, os.environ["GITHUB_OAUTH_TOKEN"])
    try:
        data = json.load(urllib.request.urlopen(url))
    except Exception:
        data = {}

    gists = []

    for gist_data in data:

        # should only return public, but just to be safe
        public = gist_data.get("public", False)
        if not public:
            continue

        description = gist_data.get("description", False)

        file_data = gist_data.get("files")
        if not file_data:
            continue

        # only return gists with 1 file (don't know how to handle more yet)
        if len(file_data) != 1:
            app.log_debug(
                "Found gist with multiple files. Don't know how to handle that yet."
            )
            continue

        # since the dictionary only contains one key value pair,
        # just extract the first and only one.
        file_info = list(file_data.values())[0]

        file_url = file_info.get("raw_url")
        if not file_url:
            continue

        # NOTE: not limiting to just python gists since that field may or may
        # not be populated when the gist is created (it's optional)

        gists.append(
            {
                "file_name": str(file_info.get("filename", "gist")),
                "file_url": str(file_url),
                "description": description,
                "language": str(file_info.get("language", "unknown")),
                "author": gist_data.get("owner", {}).get("login"),
                "gist_url": gist_data.get("html_url"),
            }
        )

    return gists
