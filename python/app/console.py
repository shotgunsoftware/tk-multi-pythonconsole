"""
Copyright (c) 2016, Michael Kessler, Josh Tomlinson
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""

# allow context manager in python 2.5
from __future__ import with_statement

import __builtin__
import cgi
from contextlib import nested
import keyword as py_keywords
import math
import os
import sys
from threading import Lock
import traceback

from sgtk.errors import TankError
from sgtk.platform.engine import current_engine
from sgtk.platform.qt import QtCore, QtGui

# make sure the images are imported for access to the resources
from .ui import resources_rc


class OutputStreamWidget(QtGui.QTextBrowser):
    """A widget to display input, output, and errors."""

    def __init__(self, parent=None):
        """Initialize the widget."""

        super(OutputStreamWidget, self).__init__(parent)

        self.setReadOnly(True)
        self.setWordWrapMode(QtGui.QTextOption.NoWrap)

        fixed_width_font = QtGui.QFont("Monospace")
        fixed_width_font.setStyleHint(
            fixed_width_font.TypeWriter,
            fixed_width_font.PreferDefault
        )
        self.setFont(fixed_width_font)

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

        if not hasattr(self, '_input_color'):

            self._input_color = _colorize(
                self.palette().base().color(), 1,
                QtGui.QColor(127, 127, 127), 2,
            )

        return self._input_color

    def _error_text_color(self):
        """The error text color."""

        if not hasattr(self, '_err_color'):

            self._err_color = _colorize(
                self.textColor(), 1,
                QtGui.QColor(255, 0, 0), 3,
            )

        return self._err_color

    def _to_html(self, text, color=None):
        """Attempt to properly escape and color text for display."""

        text = cgi.escape(text)
        text = text.replace(" ", "&nbsp;")
        text = text.replace("\n", "<br />")

        if color:
            text = """<font color="%s">%s</font>""" % (color.name(), text)

        text = "<p>%s</p>" % (text,)

        return text


class PythonSyntaxHighlighter(QtGui.QSyntaxHighlighter):
    """Adds syntax highlighting for python text."""

    def __init__(self, palette, parent=None):
        """Initialize the highlighter.

        :param palette: The color palette to use for highlighting.

        """

        super(PythonSyntaxHighlighter, self).__init__(parent)

        self._rules = []

        # ---- builtins

        builtins_color = _colorize(
            palette.windowText().color(), 3,
            QtGui.QColor(0, 255, 0), 2,
        )

        builtins_brush = QtGui.QBrush(builtins_color)
        builtins_format = QtGui.QTextCharFormat()
        builtins_format.setForeground(builtins_brush)
        builtins_format.setFontWeight(QtGui.QFont.Bold)
        builtins = dir(__builtin__)

        for word in builtins:
            builtin_pattern = QtCore.QRegExp("\\b{w}\\b".format(w=word))
            self._rules.append((builtin_pattern, builtins_format))

        # ---- keywords

        keywords_color = _colorize(
            palette.windowText().color(), 3,
            QtGui.QColor(0, 0, 255), 2,
        )
        keywords_brush = QtGui.QBrush(keywords_color)
        keywords_format = QtGui.QTextCharFormat()
        keywords_format.setForeground(keywords_brush)
        keywords_format.setFontWeight(QtGui.QFont.Bold)
        keywords = py_keywords.kwlist

        for word in keywords:
            keywords_pattern = QtCore.QRegExp("\\b{w}\\b".format(w=word))
            self._rules.append((keywords_pattern, keywords_format))

        # ---- comments

        comments_color = _colorize(
            palette.base().color(), 1,
            QtGui.QColor(127, 127, 127), 2,
        )
        comments_brush = QtGui.QBrush(comments_color)
        comments_pattern = QtCore.QRegExp("#[^\n]*")
        comments_format = QtGui.QTextCharFormat()
        comments_format.setForeground(comments_brush)
        comments_format.setFontWeight(QtGui.QFont.Light)
        comments_format.setProperty(QtGui.QTextFormat.FontItalic, True)
        self._rules.append((comments_pattern, comments_format))

    def highlightBlock(self, text):
        """Handles highlighting a block of text based on highlight rules.

        :param text: The text to highlight.
        """

        for (pattern, format) in self._rules:

            # see if we can match the pattern in the text
            expression = QtCore.QRegExp(pattern)
            index = expression.indexIn(text)

            # process all of the text, formatting each match
            while index >= 0:

                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

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


class PythonInputWidget(QtGui.QPlainTextEdit):
    """A simple python editor widget."""

    # signals.
    input = QtCore.Signal(str)
    output = QtCore.Signal(str)
    results = QtCore.Signal(str)
    error = QtCore.Signal(str)

    def __init__(self, echo=False, parent=None):
        """Initialize the input widget.

        :param echo: bool, echo input if True.
        :param parent: The parent widget.
        """

        super(PythonInputWidget, self).__init__(parent)

        # local symbol table for this input widget.
        self._locals = {}

        self._echo = echo

        # helps prevent unnecessary redraws of the line number area later.
        # See the Qt docs example for line numbers in text edit widgets:
        # http://doc.qt.io/qt-4.8/qt-widgets-codeeditor-example.html
        self._count_cache = {
            "blocks": None,
            "cursor_blocks": None
        }

        fixed_width_font = QtGui.QFont("Monospace")
        fixed_width_font.setStyleHint(
            fixed_width_font.TypeWriter,
            fixed_width_font.PreferDefault
        )
        self.setFont(fixed_width_font)

        self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.setWordWrapMode(QtGui.QTextOption.NoWrap)

        # action to trigger execution of the current code
        self.execute_action = QtGui.QAction('Execute', self)
        self.execute_action.setShortcut(QtGui.QKeySequence("Ctrl+Return"))
        self.addAction(self.execute_action)

        # these are used to redirect stdout/stderr to the signals
        self._stdout_redirect = _StdoutRedirector()
        self._stderr_redirect = _StderrRedirector()
        self._stdin_redirect = _StdinRedirector(self._readline)

        self._syntax_highlighter = PythonSyntaxHighlighter(self.palette(), self)
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

        # keep line numbers updated
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)

        # ---- initialize the state

        # go ahead and highlight the current line
        self.highlight_current_line()

        # initialize the line number area
        self._update_line_number_area_width(0);

    def execute(self):
        """Execute the contents of the input widget."""

        python_script = self.toPlainText().strip()
        num_lines = len(os.linesep.split(python_script))

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
        with nested(self._stdout_redirect, self._stdin_redirect):
            try:
                # use our copy of locals to allow persistence between executions
                if eval_code:
                    results = eval(python_code, globals(), self._locals)
                    self.results.emit(str(results))
                else:
                    exec(python_code, globals(), self._locals)
            except StandardError:
                # oops, error encountered. write/redirect to the error signal
                with self._stderr_redirect as stderr:
                    stderr.write(self._format_exc())

    def _format_exc(self):
        """Get the latest stack trace and format it for display."""
        tb = sys.exc_info()[2]
        return traceback.format_exc(tb)

    def highlight_current_line(self):
        """Highlight the current line of the input widget."""

        extra_selection = QtGui.QTextEdit.ExtraSelection()
        extra_selection.format.setBackground(
            QtGui.QBrush(self._current_line_color()))
        extra_selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
        extra_selection.cursor = self.textCursor()
        extra_selection.cursor.clearSelection()

        self.setExtraSelections([extra_selection])

    def paint_line_numbers(self, event):
        """Paint the line numbers for the input widget.

        :param event:  paint event object.
        """

        # paint on the line number area
        painter = QtGui.QPainter(self._line_number_area)

        # fill it with the line number base color
        painter.fillRect(
            event.rect(),
            self._line_number_area_base_color()
        )

        # ---- process the visible blocks

        block = self.firstVisibleBlock()
        block_num = block.blockNumber()

        top = int(
            self.blockBoundingGeometry(block).translated(
                self.contentOffset()
            ).top()
        )

        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():

            if block.isVisible() and bottom >= event.rect().top():

                num = str(block_num + 1)
                painter.setPen(self._line_number_color())
                painter.drawText(
                    0, top,
                    self._line_number_area.width(),
                    self.fontMetrics().height(),
                    QtCore.Qt.AlignRight,
                    num
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_num += 1

    def _line_number_color(self):
        """Get a line number color.

        7 parts med grey, 1 part window text.
        """

        if not hasattr(self, '_line_num_color'):

            self._line_num_color = _colorize(
                self.palette().windowText().color(), 1,
                QtGui.QColor(127, 127, 127), 7,
            )

        return self._line_num_color

    def _line_number_area_base_color(self):
        """Get a line number base color.

        3 parts base color, 1 part med grey.
        """

        if not hasattr(self, '_line_num_base_color'):

            self._line_num_base_color = _colorize(
                self.palette().base().color(), 3,
                QtGui.QColor(127, 127, 127), 1,
            )

        return self._line_num_base_color

    def _readline(self):
        """
        Reads a line of input text from the user.

        :return: a string for the user input.
        """

        dialog = QtGui.QInputDialog(flags=QtCore.Qt.FramelessWindowHint)
        dialog.setLabelText("Python is requesting input")
        dialog.adjustSize()

        parent_pos = self.mapToGlobal(self.pos())

        dialog.resize(self.width() - 2, dialog.height())
        dialog.move(
            parent_pos.x() + (self.width() / 2.0) - (dialog.width() / 2.0),
            parent_pos.y() + self.height() - dialog.height() - 1
        )

        self.setEnabled(False)

        try:
            if dialog.exec_() == QtGui.QDialog.Accepted:
                return str(dialog.textValue()) + "\n"
            else:
                return ""
        finally:
            self.setFocus()
            self.setEnabled(True)


    def line_number_area_width(self):
        """Calculate the width of the line number area."""

        digits = math.floor(math.log10(self.blockCount())) + 1
        return 3 + self.fontMetrics().width('8') * digits

    def keyPressEvent(self, event):
        """Intercept any key events for special casing.

        :param event: key press event object.
        """

        if event.key() == QtCore.Qt.Key_Tab:
            # intercept the tab key and insert 4 spaces
            self.insertPlainText("    ")
            event.accept()
        else:
            super(PythonInputWidget, self).keyPressEvent(event)

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

    def open(self, path=None):
        """Open an external python script to edit.

        :param path: A path to a directory to browse or file to open.
        """

        # prompt to continue if there is existing code in the input widget.
        cur_python = str(self.toPlainText()).strip()

        if cur_python:
            btn_clicked = QtGui.QMessageBox.question(
                self,
                "Existing Python Code",
                ("If you continue, you will loose the python code currently "
                 "in the editor."),
                buttons=QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel,
                defaultButton=QtGui.QMessageBox.Cancel,
            )
            if btn_clicked == QtGui.QMessageBox.Cancel:
                return

        # browse to a file to open
        if not path or os.path.isdir(path):
            open_path_data = QtGui.QFileDialog.getOpenFileName(
                self,
                "Open Python Script",
                dir=path,
                selectedFilter="*.py",
                options=QtGui.QFileDialog.DontResolveSymlinks,
            )
            path = str(open_path_data[0])

        if not path:
            return

        # clear the contents, open and load the file
        fh = open(path)
        try:
            self.clear()
            python_script = "".join(fh.readlines())
            self.setPlainText(python_script)
        finally:
            fh.close()

    def save(self, path=None):
        """Save the current contents to a file.

        :param path: A path to a file to save or dir to browse.
        """

        save_path_data = QtGui.QFileDialog.getSaveFileName(
            self,
            "Save Python Script",
            dir=path,
            selectedFilter="*.py",
            options=QtGui.QFileDialog.DontResolveSymlinks,
        )

        if not save_path_data or not save_path_data[0]:
            return False

        # write the contents of the editor to a file.
        python_script = str(self.toPlainText())
        fh = open(str(save_path_data[0]), "w")
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


    def toggle_echo(self, echo):
        """Toggles the echo'ing of the input.

        NOTE: This does not update the UI.

        :param echo: bool, if True, forward the input to the signal.
        """
        self._echo = echo

    def _update_line_number_area_width(self, count):
        """Update the display of the line number area.

        :param count: block count. unused, but comes from connected singal.

        """
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        """Update the contents of the line number area.

        :param rect: The line number are rect.
        :param dy: The horizontal scrolled difference.

        """

        if (dy):
            self._line_number_area.scroll(0, dy)
        elif (self._count_cache["blocks"] != self.blockCount() or
              self._count_cache["cursor_blocks"] != \
                self.textCursor().block().lineCount()):
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

    def _current_line_color(self):
        """Returns a line color for the current line highlighting.

        5 parts base color, 1 part highlight.
        """

        if not hasattr(self, "_cur_line_color"):

            palette = self.palette()
            base_color = palette.base().color()
            highlight_color = palette.highlight().color()

            self._cur_line_color = _colorize(
                base_color, 5,
                highlight_color, 1,
            )

        return self._cur_line_color

class _StdinRedirector(QtCore.QObject):
    """Handles redirecting stdin.

    Sends an input signal when stdin is read from.
    """

    input_requested = QtCore.Signal(str)

    def __init__(self, readline_callback, parent=None):
        """Initialize the redirection object.

        :param parent: The parent qt object.
        """
        super(_StdinRedirector, self).__init__(parent)
        self._handle = None
        self._readline_callback = readline_callback

    def __enter__(self):
        """Begin rediredtion.

        Temporarily assigns stdin to this object for writing.
        """
        self._handle = sys.stdin
        sys.stdin = self
        return self

    def __exit__(self, type, value, traceback):
        """Finish redirection.

        Repoint sys.stdin to the original handle.
        """
        sys.stdin = self._handle

    def readline(self):
        return self._readline_callback()


class _StdoutRedirector(QtCore.QObject):
    """Handles redirecting stdout.

    Sends an output signal when stdout is written to.
    """

    output = QtCore.Signal(str)

    def __init__(self, tee=True, parent=None):
        """Initialize the redirection object.

        :param tee: Also write to sys stdout when True.
        :param parent: The parent qt object.
        """
        super(_StdoutRedirector, self).__init__(parent)
        self._handle = None
        self._tee = tee

    def __enter__(self):
        """Begin rediredtion.

        Temporarily assigns stdout to this object for writing.
        """
        self._handle = sys.stdout
        sys.stdout = self
        return self

    def __exit__(self, type, value, traceback):
        """Finish redirection.

        Repoint sys.stdout to the original handle.
        """
        sys.stdout = self._handle

    def write(self, msg):
        """Forward the writted output to the output signal.

        If tee, then also write to stdout.
        """
        self.output.emit(msg)
        if self._tee and self._handle:
            self._handle.write(msg)

class _StderrRedirector(QtCore.QObject):
    """Handles redirecting stderr.

    Sends an output signal when stderr is written to.
    """

    error = QtCore.Signal(str)

    def __init__(self, tee=True, parent=None):
        """Initialize the redirection object.

        :param tee: Also write to sys stderr when True.
        :param parent: The parent qt object.
        """
        super(_StderrRedirector, self).__init__(parent)
        self._handle = None
        self._tee = tee

    def __enter__(self):
        """Begin rediredtion.

        Temporarily assigns stderr to this object for writing.
        """
        self._handle = sys.stderr
        sys.stderr= self
        return self

    def __exit__(self, type, value, traceback):
        """Finish redirection.

        Repoint sys.stderr to the original handle.
        """
        sys.stderr= self._handle

    def write(self, msg):
        """Forward the writted output to the error signal.

        If tee, then also write to stderr.
        """
        self.error.emit(msg)
        if self._tee:
            self._handle.write(msg)


class PythonConsoleWidget(QtGui.QWidget):
    """A dockable, interactive python console widget."""

    def __init__(self, parent=None):
        super(PythonConsoleWidget, self).__init__(parent)

        # ---- output

        # main output widget
        self._output_widget = OutputStreamWidget(parent=self)

        # clear output
        out_clear_btn = QtGui.QToolButton(self)
        out_clear_btn.setMinimumSize(QtCore.QSize(30, 30))
        out_clear_btn.setMaximumSize(QtCore.QSize(30, 30))
        out_clear_btn.setObjectName("out_clear_btn")
        out_clear_btn.setToolTip("Clear all output.")

        # echo output
        out_echo_btn = QtGui.QToolButton()
        out_echo_btn.setCheckable(True)
        out_echo_btn.setChecked(True)
        out_echo_btn.setDown(True)
        out_echo_btn.setMinimumSize(QtCore.QSize(30, 30))
        out_echo_btn.setMaximumSize(QtCore.QSize(30, 30))
        out_echo_btn.setObjectName("out_echo_btn")
        out_echo_btn.setToolTip("Echo python commands in output.")

        # output buttons layout
        out_btn_box = QtGui.QVBoxLayout()
        out_btn_box.addSpacing(10)
        out_btn_box.addWidget(out_clear_btn)
        out_btn_box.addSpacing(10)
        out_btn_box.addWidget(out_echo_btn)
        out_btn_box.addSpacing(10)
        out_btn_box.addStretch()

        # complete output layout
        out_layout = QtGui.QHBoxLayout()
        out_layout.setContentsMargins(0, 0, 0, 0)
        out_layout.setSpacing(4)
        out_layout.addWidget(self._output_widget)
        out_layout.addLayout(out_btn_box)

        # output widget to add to splitter
        out_widget = QtGui.QWidget(self)
        out_widget.setLayout(out_layout)
        out_widget.setFocusPolicy(QtCore.Qt.NoFocus)

        # ---- input

        self._python_input_widget = PythonInputWidget(self)

        # clear input
        in_clear_btn = QtGui.QToolButton()
        in_clear_btn.setMinimumSize(QtCore.QSize(30, 30))
        in_clear_btn.setMaximumSize(QtCore.QSize(30, 30))
        in_clear_btn.setObjectName("in_clear_btn")
        in_clear_btn.setToolTip("Clear all input.")

        # open file
        in_open_btn = QtGui.QToolButton()
        in_open_btn.setMinimumSize(QtCore.QSize(30, 30))
        in_open_btn.setMaximumSize(QtCore.QSize(30, 30))
        in_open_btn.setObjectName("in_open_btn")
        in_open_btn.setToolTip("Load python script from a file.")

        # save file
        self._in_save_btn = QtGui.QToolButton()
        self._in_save_btn.setMinimumSize(QtCore.QSize(30, 30))
        self._in_save_btn.setMaximumSize(QtCore.QSize(30, 30))
        self._in_save_btn.setObjectName("in_save_btn")
        self._in_save_btn.setToolTip("Save current python script to a file.")

        # execute
        self._in_exec_btn = QtGui.QToolButton()
        self._in_exec_btn.setMinimumSize(QtCore.QSize(30, 30))
        self._in_exec_btn.setMaximumSize(QtCore.QSize(30, 30))
        self._in_exec_btn.setObjectName("in_exec_btn")
        self._in_exec_btn.setToolTip("Execute the current python script. Shortcut: Ctrl+Enter")

        # input buttons layout
        in_btn_box = QtGui.QVBoxLayout()
        in_btn_box.addWidget(in_clear_btn)
        in_btn_box.addSpacing(10)
        in_btn_box.addWidget(in_open_btn)
        in_btn_box.addSpacing(10)
        in_btn_box.addWidget(self._in_save_btn)
        in_btn_box.addSpacing(10)
        in_btn_box.addWidget(self._in_exec_btn)
        in_btn_box.addStretch()

        # complete input layout
        in_layout = QtGui.QHBoxLayout()
        in_layout.setContentsMargins(0, 0, 0, 0)
        in_layout.setSpacing(4)
        in_layout.addWidget(self._python_input_widget)
        in_layout.addLayout(in_btn_box)

        # input widget to add to splitter
        in_widget = QtGui.QWidget(self)
        in_widget.setLayout(in_layout)

        # splitter
        splitter = QtGui.QSplitter(QtCore.Qt.Vertical, self)
        splitter.addWidget(out_widget)
        splitter.addWidget(in_widget)

        # main layout
        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(splitter)

        # ---- connect singals and slots

        # buttons clicked
        out_clear_btn.clicked.connect(self._output_widget.clear)
        self._in_save_btn.clicked.connect(self._python_input_widget.save)
        in_open_btn.clicked.connect(self._python_input_widget.open)
        in_clear_btn.clicked.connect(self._python_input_widget.clear)
        self._in_exec_btn.clicked.connect(self._python_input_widget.execute)

        # toggles
        out_echo_btn.toggled.connect(self._python_input_widget.toggle_echo)

        # connect input and output widgets
        self._python_input_widget.input.connect(self._output_widget.add_input)
        self._python_input_widget.output.connect(self._output_widget.add_output)
        self._python_input_widget.error.connect(self._output_widget.add_error)
        self._python_input_widget.results.connect(self._output_widget.add_results)

        self._python_input_widget.textChanged.connect(self._check_button_state)

        # ---- set the default state

        # make sure the input has focus
        self._python_input_widget.setFocus()

        # no point in saving until there are contents
        self._in_save_btn.setEnabled(False)

    def _check_button_state(self):

        script_len = len(self._python_input_widget.toPlainText())

        self._in_save_btn.setEnabled(script_len > 0)
        self._in_exec_btn.setEnabled(script_len > 0)

class ShotgunPythonConsoleWidget(PythonConsoleWidget):
    """A dockable, interactive python console widget.

    Exposes Shotgun-specific globals by default in the editor. Similar to the
    tk-shell engine.

    - A tk API handle is available via the `tk` variable
    - A Shotgun API handle is available via the `shotgun` variable
    - The current context is stored in the `context` variable
    - The shell engine can be accessed via the `engine` variable

    """

    def __init__(self, parent=None):
        super(ShotgunPythonConsoleWidget, self).__init__(parent)

        engine = current_engine()

        # if not running in an engine, then we're hosed
        if not engine:
            raise TankError(
                "Unable to initialize ShotgunPythonConsole. No engine running")

        # add some Shotgun-specific globals
        global_vars = globals()
        global_vars["tk"] = engine.tank
        global_vars["shotgun"] = engine.shotgun
        global_vars["context"] = engine.context
        global_vars["engine"] = engine

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

        self._output_widget.add_input(welcome_message, prefix=None)

def _colorize(c1, c1_strength, c2, c2_strength):
    """Convenience method for making a color from 2 existing colors.

    :param c1: QtGui.QColor 1
    :param c1_strength: int factor of the strength of this color
    :param c2: QtGui.QColor 2
    :param c2_strength: int factor of the strength of this color

    This is primarily used to prevent hardcoding of colors that don't work in
    other color palettes. The idea is that you can provide a color from the
    current widget palette and shift it toward another color. For example,
    you could get a red-shifted text color by supplying the windowText color
    for a widget as color 1, and the full red as color 2. Then use the strength
    args to weight the resulting color more toward the windowText or full red.

    It's still important to test the resulting colors in multiple color schemes.

    """

    total = c1_strength + c2_strength

    r = ((c1.red() * c1_strength) + (c2.red() * c2_strength)) / total
    g = ((c1.green() * c1_strength) + (c2.green() * c2_strength)) / total
    b = ((c1.blue() * c1_strength) + (c2.blue() * c2_strength)) / total

    return QtGui.QColor(r, g, b)

