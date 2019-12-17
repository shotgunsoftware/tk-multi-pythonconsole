# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# allow context manager in python 2.5
from __future__ import with_statement

from contextlib import nested
import math
import sys
import traceback

# NOTE: This repo is typically used as a Toolkit app, but it is also possible use the console in a
# stand alone fashion. This try/except allows portions of the console to be imported outside of a
# Shotgun/Toolkit environment. Flame, for example, uses the console when there is no Toolkit
# engine running.
try:
    from sgtk.platform.qt import QtCore, QtGui
except ImportError:
    from PySide import QtCore, QtGui

from .redirect import StderrRedirector, StdinRedirector, StdoutRedirector
from .syntax_highlighter import PythonSyntaxHighlighter
from .util import colorize


class PythonInputWidget(QtGui.QPlainTextEdit):
    """A simple python editor widget.

    :signal: ``input(str)`` - emits the input input text when submitted
    :signal: ``output(str)`` - emits the output when eval'd/exec'd
    :signal: ``results(str)`` - emits the returned results as a ``str`` after eval/exec
    :signal: ``error(str)`` - emits any error as a ``str`` after eval/exec
    :signal: ``cursor_column_changed(int)`` - emits the current column as the cursor changes

    """

    # signals.
    input = QtCore.Signal(str)
    output = QtCore.Signal(str)
    results = QtCore.Signal(str)
    error = QtCore.Signal(str)
    cursor_column_changed = QtCore.Signal(int)

    def __init__(self, parent=None):
        """Initialize the input widget.

        :param echo: bool, echo input if True.
        :param parent: The parent widget.
        """

        super(PythonInputWidget, self).__init__(parent)

        # local symbol table for this input widget.
        # copy globals and use this for everything
        self._locals = globals().copy()
        self._echo = True
        self._show_line_numbers = True

        # helps prevent unnecessary redraws of the line number area later.
        # See the Qt docs example for line numbers in text edit widgets:
        # http://doc.qt.io/qt-4.8/qt-widgets-codeeditor-example.html
        self._count_cache = {
            "blocks": None,
            "cursor_blocks": None
        }

        self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.setWordWrapMode(QtGui.QTextOption.NoWrap)

        # action to trigger execution of the current code
        self.execute_action = QtGui.QAction('Execute', self)
        self.execute_action.setShortcut(QtGui.QKeySequence("Ctrl+Return"))
        self.addAction(self.execute_action)

        # these are used to redirect stdout/stderr to the signals
        self._stdout_redirect = StdoutRedirector()
        self._stderr_redirect = StderrRedirector()
        self._stdin_redirect = StdinRedirector(self._readline)

        self._syntax_highlighter = PythonSyntaxHighlighter(self.document(), self.palette())
        self._syntax_highlighter.setDocument(self.document())

        self._line_number_area = _LineNumberArea(self)

        # ---- connect signals/slots

        self.execute_action.triggered.connect(self.execute)

        # redirect any stdout to the output signal
        self._stdout_redirect.output.connect(self.output.emit)

        # redirect any stderr to the error signal
        self._stderr_redirect.error.connect(self.error.emit)

        # make sure the current line is always highlighted
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.cursorPositionChanged.connect(
            lambda: self.cursor_column_changed.emit(
                self.textCursor().columnNumber() + 1
            )
        )

        # keep line numbers updated
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)

        # ---- initialize the state

        # go ahead and highlight the current line
        self.highlight_current_line()

        # initialize the line number area
        self._update_line_number_area_width(0);

    def add_globals(self, new_globals):
        """
        Updates global variables with the supplied values.
        """

        self._locals.update(new_globals)

    def execute(self):
        """Execute the contents of the input widget."""

        # see if there is selected text. if so, use that
        text_cursor = self.textCursor()
        python_script = text_cursor.selectedText()

        # as per the docs...
        # If the selection obtained from an editor spans a line break, the
        # text will contain a Unicode U+2029 paragraph separator character
        # instead of a newline \n character.
        python_script = python_script.replace(u"\u2029", "\n")
        python_script = str(python_script).strip()

        if not python_script:
            # no text selected, fall back to the full script
            python_script = self.toPlainText().strip()

        if not python_script:
            return

        if self._echo:
            # forward the input text
            self.input.emit(python_script)

        # start by assuming the code is an expression
        eval_code = True

        try:
            # try to compile the python as an expression
            python_code = compile(python_script, "<python input>", "eval")
        except SyntaxError, e:
            # not an expression. must exec
            eval_code = False
            try:
                python_code = compile(python_script, "python input", "exec")
            except SyntaxError, e:
                # oops, syntax error. write to our stderr
                with self._stderr_redirect as stderr:
                    stderr.write(self._format_exc())
                return

        # exec the python code, redirecting any stdout to the ouptut signal.
        # also redirect stdin if need be
        if eval_code:
            with nested(self._stdout_redirect, self._stdin_redirect):
                try:
                    # use our copy of locals to allow persistence between executions
                    results = eval(python_code, self._locals, self._locals)
                except Exception:
                    # oops, error encountered. write/redirect to the error signal
                    with self._stderr_redirect as stderr:
                        stderr.write(self._format_exc())
                else:
                    self.results.emit(str(results))

        # exec
        else:
            with nested(self._stdout_redirect, self._stdin_redirect):
                try:
                    # locals gets passed in as both global and locals to fix look up issues
                    exec(python_code, self._locals, self._locals)
                except Exception:
                    # oops, error encountered. write/redirect to the error signal
                    with self._stderr_redirect as stderr:
                        stderr.write(self._format_exc())

    def highlight_current_line(self):
        """Highlight the current line of the input widget."""

        extra_selection = QtGui.QTextEdit.ExtraSelection()
        extra_selection.format.setBackground(
            QtGui.QBrush(self._current_line_color()))
        extra_selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
        extra_selection.cursor = self.textCursor()
        extra_selection.cursor.clearSelection()

        self.setExtraSelections([extra_selection])

    def keyPressEvent(self, event):
        """Intercept any key events for special casing.

        :param event: key press event object.
        """

        if (event.modifiers() & QtCore.Qt.ShiftModifier and
            event.key() in [QtCore.Qt.Key_Enter, QtCore.Qt.Key_Return]):
                self.insertPlainText("\n")
                event.accept()
        elif event.key() == QtCore.Qt.Key_Tab:
            # intercept the tab key and insert 4 spaces
            self.insertPlainText("    ")
            event.accept()
        else:
            super(PythonInputWidget, self).keyPressEvent(event)

    def line_number_area_width(self):
        """Calculate the width of the line number area."""

        if self._show_line_numbers:
            digits = math.floor(math.log10(self.blockCount())) + 1
            return 6 + self.fontMetrics().width('8') * digits
        else:
            return 0

    def paint_line_numbers(self, event):
        """Paint the line numbers for the input widget.

        :param event:  paint event object.
        """

        if not self._show_line_numbers:
            return

        # paint on the line number area
        painter = QtGui.QPainter(self._line_number_area)

        line_num_rect = event.rect()

        # fill it with the line number base color
        painter.fillRect(
            line_num_rect,
            self._line_number_area_base_color()
        )

        painter.setPen(self.palette().base().color())
        painter.drawLine(line_num_rect.topLeft(), line_num_rect.bottomLeft())
        painter.drawLine(line_num_rect.topLeft(), line_num_rect.topRight())
        painter.drawLine(line_num_rect.bottomLeft(), line_num_rect.bottomRight())

        # ---- process the visible blocks

        block = self.firstVisibleBlock()
        block_num = block.blockNumber()

        top = int(
            self.blockBoundingGeometry(block).translated(
                self.contentOffset()
            ).top()
        )

        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= line_num_rect.bottom():

            if block.isVisible() and bottom >= line_num_rect.top():

                num = str(block_num + 1)
                painter.setPen(self._line_number_color())
                painter.drawText(
                    -2, top,
                    self._line_number_area.width(),
                    self.fontMetrics().height(),
                    QtCore.Qt.AlignRight,
                    num
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_num += 1

    def resizeEvent(self, event):
        """Make sure line number area is updated on resize.

        :param event: resize event object
        """

        super(PythonInputWidget, self).resizeEvent(event)

        contents_rect = self.contentsRect()
        line_number_area_rect = QtCore.QRect(
            contents_rect.left(),
            contents_rect.top(),
            self.line_number_area_width(),
            contents_rect.height()
        )
        self._line_number_area.setGeometry(line_number_area_rect)

    def save(self, start_path=None):
        """Save the current contents to a file.

        :param path: A path to a file to save or dir to browse.
        """

        save_dialog = QtGui.QFileDialog(
            parent=QtGui.QApplication.activeWindow(),
            caption="Save Python Script",
            directory=start_path,
            filter="*.py",
        )
        save_dialog.setOption(QtGui.QFileDialog.DontResolveSymlinks, True)
        save_dialog.setOption(QtGui.QFileDialog.DontUseNativeDialog, True)
        save_dialog.setAcceptMode(QtGui.QFileDialog.AcceptSave)
        save_dialog.setViewMode(QtGui.QFileDialog.Detail)
        save_path = None
        if save_dialog.exec_():
            save_path = save_dialog.selectedFiles()[0]

        if not save_path:
            return False

        # write the contents of the editor to a file.
        python_script = str(self.toPlainText())
        fh = open(save_path, "w")
        try:
            fh.write(python_script)
        except Exception, e:
            QtGui.QMessageBox.warning(
                self,
                "Failed to Save Python Script",
                "There was an error saving the python script:\n\n%s" % (str(e)),
            )
        finally:
            fh.close()

        return True

    def echoing_output(self):
        # returns ``True`` if echoing python commands/statements to the output window
        return self._echo

    def showing_line_numbers(self):
        # returns ``True`` if line numbers are being shown, ``False`` otherwise.
        return self._show_line_numbers

    def toggle_echo(self, echo):
        """Toggles the echo'ing of the input.

        NOTE: This does not update the UI.

        :param echo: bool, if True, forward the input to the signal.
        """
        self._echo = echo

    def toggle_line_numbers(self, line_numbers):
        """
        Toggles line numbers on/off based on the supplied value.
        """
        self._show_line_numbers = line_numbers

        # redraw the whole thing to get it to update immediately
        self._update_line_number_area(self.rect(), 0)

    def wheelEvent(self, event):
        """
        Handles zoom in/out of the text.
        """

        if event.modifiers() & QtCore.Qt.ControlModifier:

            delta = event.delta()
            if delta < 0:
                self.zoom_out()
            elif delta > 0:
                self.zoom_in()

            return True

        return super(PythonInputWidget, self).wheelEvent(event)

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
        """ % (size,)
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

    def _current_line_color(self):
        """Returns a line color for the current line highlighting.

        5 parts base color, 1 part highlight.
        """

        if not hasattr(self, "_cur_line_color"):

            palette = self.palette()
            base_color = palette.base().color()
            highlight_color = palette.highlight().color()

            self._cur_line_color = colorize(
                base_color, 2,
                highlight_color, 1,
            )

        return self._cur_line_color

    def _format_exc(self):
        """Get the latest stack trace and format it for display."""
        tb = sys.exc_info()[2]
        return traceback.format_exc(tb)

    def _line_number_area_base_color(self):
        """Get a line number base color."""

        if not hasattr(self, '_line_num_base_color'):
            palette = self.palette()
            base_color = palette.base().color()
            window_color = palette.window().color()

            self._line_num_base_color = colorize(
                base_color, 1,
                window_color, 1,
            )

        return self._line_num_base_color

    def _line_number_color(self):
        """Get a line number color."""

        if not hasattr(self, '_line_num_color'):

            palette = self.palette()
            base_color = palette.base().color()
            highlight_color = palette.highlight().color()

            self._line_num_color = colorize(
                base_color, 1,
                highlight_color, 2,
            )

        return self._line_num_color

    def _readline(self):
        """
        Reads a line of input text from the user.

        :return: a string for the user input.
        """
        dialog = QtGui.QInputDialog(
            parent=self,
            flags=QtCore.Qt.FramelessWindowHint
        )
        dialog.setLabelText("Python is requesting input")
        dialog.adjustSize()

        dialog.resize(self.width() - 2, dialog.height())
        dialog.move(
            self.mapToGlobal(self.rect().topLeft()).x(),
            self.mapToGlobal(self.rect().bottomLeft()).y() - dialog.height()
        )

        try:
            if dialog.exec_() == QtGui.QDialog.Accepted:
                return str(dialog.textValue()) + "\n"
            else:
                return ""
        finally:
            self.setFocus()

    def _update_line_number_area(self, rect, dy):
        """Update the contents of the line number area.

        :param rect: The line number are rect.
        :param dy: The horizontal scrolled difference.
        """

        if (dy):
            self._line_number_area.scroll(0, dy)
        elif (self._count_cache["blocks"] != self.blockCount() or
              self._count_cache["cursor_blocks"] != self.textCursor().block().lineCount()):
            self._line_number_area.update(
                0,
                rect.y(),
                self._line_number_area.width(),
                rect.height()
            )
            self._count_cache = {
                "blocks": self.blockCount(),
                "cursor_blocks": self.textCursor().block().lineCount()
            }

        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def _update_line_number_area_width(self, count):
        """Update the display of the line number area.

        :param count: block count. unused, but comes from connected singal.

        """
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)


class _LineNumberArea(QtGui.QWidget):
    """Display line numbers for an input widget."""

    def __init__(self, editor):
        """Initialize the line number area.

        :param editor: The editor widget where line numbers will be displayed.
        """

        super(_LineNumberArea, self).__init__(parent=editor)
        self._editor = editor

    def paintEvent(self, event):
        """Paint line numbers on the editor.

        :param event: paint event object.
        """
        self._editor.paint_line_numbers(event)

