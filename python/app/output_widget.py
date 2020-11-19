# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from datetime import datetime
import os
import sys
from threading import Lock

# NOTE: This repo is typically used as a Toolkit app, but it is also possible use the console in a
# stand alone fashion. This try/except allows portions of the console to be imported outside of a
# Shotgun/Toolkit environment. Flame, for example, uses the console when there is no Toolkit
# engine running.

if sys.version_info.major == 2:
    from cgi import escape
elif sys.version_info.major == 3:
    from html import escape as escape

from .qt_importer import QtCore, QtGui

try:
    import sgtk
except ImportError:
    sgtk = None

try:
    from tank_vendor import six
except ImportError:
    try:
        import six
    except ImportError:
        six = None

from .util import colorize


class OutputStreamWidget(QtGui.QTextBrowser):
    """A widget to display input, output, and errors."""

    def __init__(self, parent=None):
        """Initialize the widget."""

        super(OutputStreamWidget, self).__init__(parent)

        self.setReadOnly(True)
        self.setWordWrapMode(QtGui.QTextOption.NoWrap)

        # lock to prevent multiple threads writing output at the same time
        self._write_lock = Lock()

    def add_input(self, text, prefix=">>>"):
        """
        Append the supplied input text to the contents.

        The text is formatted and colored to make it obvious that it is input.

        :param text: The input text to display.
        :param prefix: Prefix each line of input with this string.

        """

        text = str(text)

        if prefix:
            formatted_lines = []

            for line in text.split(os.linesep):
                line = "%s %s" % (prefix, line)
                formatted_lines.append(line)

            text = os.linesep.join(formatted_lines)
            text = "[%s]\n%s" % (datetime.now().strftime("%x %X"), text)
            text += "\n"

        with self._write_lock:
            text = self._to_html(text, self._input_text_color())
            self.moveCursor(QtGui.QTextCursor.End)
            self.insertHtml(text)
            self._scroll_to_bottom()

    def add_results(self, text, header="# Results:", prefix="# "):
        """
        Append results to the contents.

        The text is formatted similarly to the input. There's a prefix
        available for each line as well as a header to identify the text as
        results.

        :param text: The results text to display.
        :param header: A header to display in the widget to identify as results.
        :param prefix: Prefix the results will have.
        :return:
        """

        text = str(text)

        if prefix:
            formatted_lines = []

            for line in text.split(os.linesep):
                line = "%s %s" % (prefix, line)
                formatted_lines.append(line)

            text = os.linesep.join(formatted_lines)
            text += "\n"

        text = "%s\n%s" % (header, text)

        with self._write_lock:
            text = self._to_html(text, self._input_text_color())
            self.moveCursor(QtGui.QTextCursor.End)
            self.insertHtml(text)
            self._scroll_to_bottom()

    def add_output(self, text):
        """
        Append the supplied output text to the contents.

        The text is formatted and colored to make it obvious that it is output.

        :param text: The output text to display.

        """

        if six:
            # if six can be imported sanitize the string.
            # This may lead to unicode errors if not imported in Python 2
            text = six.ensure_str(text)
        else:
            text = str(text)

        with self._write_lock:
            text = self._to_html(text)
            self.moveCursor(QtGui.QTextCursor.End)
            self.insertHtml(text)
            self._scroll_to_bottom()

    def add_error(self, text):
        """
        Append the supplied error text to the contents.

        The text is formatted and colored to make it obvious that it is an error.

        :param text: The error text to display.

        """

        # if shotgun/toolkit is available, log the error message to the current
        # engine.
        if sgtk and sgtk.platform.current_engine():
            sgtk.platform.current_engine().logger.error(text)

        if six:
            # if six can be imported sanitize the string.
            # This may lead to unicode errors if not imported in python 2
            text = six.ensure_str(text)
        else:
            text = str(text)

        # write the error
        with self._write_lock:
            text = self._to_html(text, self._error_text_color())
            self.moveCursor(QtGui.QTextCursor.End)
            self.insertHtml(text)
            self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """Force scroll to the bottom of the contents."""

        v_scroll_bar = self.verticalScrollBar()
        v_scroll_bar.setValue(v_scroll_bar.maximum())

    def _input_text_color(self):
        """The input text color."""

        if not hasattr(self, "_input_color"):

            self._input_color = colorize(
                self.palette().base().color(), 1, QtGui.QColor(127, 127, 127), 2,
            )

        return self._input_color

    def _error_text_color(self):
        """The error text color."""

        if not hasattr(self, "_err_color"):

            self._err_color = colorize(self.textColor(), 1, QtGui.QColor(255, 0, 0), 3,)

        return self._err_color

    def _to_html(self, text, color=None):
        """Attempt to properly escape and color text for display."""

        text = escape(text)
        text = text.replace(" ", "&nbsp;")
        text = text.replace("\n", "<br />")

        if color:
            text = """<font color="%s">%s</font>""" % (color.name(), text)

        text = "<p>%s</p>" % (text,)

        return text

    def wheelEvent(self, event):
        """
        Handles zoom in/out of output text.
        """

        if event.modifiers() & QtCore.Qt.ControlModifier:

            delta = event.delta()
            if delta < 0:
                self.zoom_out()
            elif delta > 0:
                self.zoom_in()

            return True

        return super(OutputStreamWidget, self).wheelEvent(event)

    def zoom(self, direction):
        """
        Zoom in on the text.
        """

        font = self.font()
        size = font.pointSize()
        if size == -1:
            size = font.pixelSize()

        size += direction

        if size < 7:
            size = 7
        if size > 50:
            return

        style = """
        QWidget {
            font-size: %spt;
        }
        """ % (
            size,
        )
        self.setStyleSheet(style)

    def zoom_in(self):
        """
        Zoom in on the text.
        """
        self.zoom(1)

    def zoom_out(self):
        """
        Zoom out on the text.
        """
        self.zoom(-1)
