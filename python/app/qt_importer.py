# Copyright (c) 2020 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# NOTE: This repo is typically used as a Toolkit app, but it is also possible use the console in a
# stand alone fashion. This try/except allows portions of the console to be imported outside of a
# Shotgun/Toolkit environment. Flame, for example, uses the console when there is no Toolkit
# engine running.

# This module handles importing of Qt modules
try:
    from sgtk.platform.qt import QtCore, QtGui
except ImportError:
    try:
        # Try to import from PySide2 and keep the QtGui interface
        # consistent with PySide (Qt 4).
        # We don't try to cover all cases, only the QtGui module as we
        # are using components from that which are different between Qt 5 and 4.
        # Approach is taken from the `tk-core` `pyside2_patcher.py` module.
        from PySide2 import QtCore
        import PySide2.QtGui as __PySide2_QtGui
        import PySide2.QtWidgets as __PySide2_QtWidgets

        def _move_attributes(dst, src, names):
            """
            Moves a list of attributes from one package to another.
            :param names: Names of the attributes to move.
            """
            for name in names:
                if not hasattr(dst, name):
                    setattr(dst, name, getattr(src, name))

        import types

        QtGui = types.ModuleType("PySide.QtGui")

        # Combine the attributes of the QtWidgets and QtGui into a new QtGui module.
        _move_attributes(QtGui, __PySide2_QtWidgets, dir(__PySide2_QtWidgets))
        _move_attributes(QtGui, __PySide2_QtGui, dir(__PySide2_QtGui))
    except ImportError:
        from PySide import QtCore, QtGui
