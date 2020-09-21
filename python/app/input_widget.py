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

import math
import traceback
import re

# NOTE: This repo is typically used as a Toolkit app, but it is also possible use the console in a
# stand alone fashion. This try/except allows portions of the console to be imported outside of a
# Shotgun/Toolkit environment. Flame, for example, uses the console when there is no Toolkit
# engine running.
from .qt_importer import QtGui, QtCore


from .redirect import StderrRedirector, StdinRedirector, StdoutRedirector
from .syntax_highlighter import PythonSyntaxHighlighter
from .util import colorize

try:
    import sgtk
except ImportError:
    sgtk = None


def safe_modify_content(func):
    """
    This method can be used as a decorator, on methods that alter the contents of the
    text edit.
    It handles starting and ending of undo blocks, and performs an undo in the event of the
    method erroring.
    """

    def function_wrapper(self, *args):
        cur = self.textCursor()

        # beginEditBlock will start the undo block, we end it after making the changes.
        # That ensures all the changes are recorded as one undo level.
        cur.beginEditBlock()
        perform_undo = False

        # Try to modify the content but if it errors undo our changes.
        try:
            # call the main function with any args.
            func(self, *args)
        except Exception:
            # if Shotgun/Toolkit is available, log the error message to the current engine.
            if sgtk:
                sgtk.platform.current_engine().logger.exception("Add new line failed.")
            perform_undo = True
        finally:
            # End our undo block.
            cur.endEditBlock()
            # Check if the operation failed an roll back if it did.
            if perform_undo:
                self.undo()

    return function_wrapper


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
        # match what dunders appear in an interactive python shell
        self._locals = {
            "__name__": "__main__",
            "__doc__": None,
            "__package__": None,
        }
        self._echo = True
        self._show_line_numbers = True

        # helps prevent unnecessary redraws of the line number area later.
        # See the Qt docs example for line numbers in text edit widgets:
        # http://doc.qt.io/qt-4.8/qt-widgets-codeeditor-example.html
        self._count_cache = {"blocks": None, "cursor_blocks": None}

        self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.setWordWrapMode(QtGui.QTextOption.NoWrap)

        # action to trigger execution of the current code
        self.execute_action = QtGui.QAction("Execute", self)
        self.execute_action.setShortcut(QtGui.QKeySequence("Ctrl+Return"))
        self.addAction(self.execute_action)

        # these are used to redirect stdout/stderr to the signals
        self._stdout_redirect = StdoutRedirector()
        self._stderr_redirect = StderrRedirector()
        self._stdin_redirect = StdinRedirector(self._readline)

        self._syntax_highlighter = PythonSyntaxHighlighter(
            self.document(), self.palette()
        )
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
        self._update_line_number_area_width(0)

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
        except SyntaxError:
            # not an expression. must exec
            eval_code = False
            try:
                python_code = compile(python_script, "python input", "exec")
            except SyntaxError:
                # oops, syntax error. write to our stderr
                self._stderr_redirect.write(self._format_exc())
                return

        # exec the python code, redirecting any stdout to the ouptut signal.
        # also redirect stdin if need be
        if eval_code:
            # Use two with statements inside each other as python 2.6 doesn't support passing a tuple
            # and Python 3 doesn't support contextlib.nested().
            with self._stdout_redirect:
                with self._stdin_redirect:
                    try:
                        # Use our copy of locals to allow persistence between executions
                        # We provide the locals dict as both the global and local scopes
                        # So that any methods executed in the python console can access the top
                        # level/global variables.
                        # example:
                        # a = "hello"
                        # def do_something():
                        #     print(a)
                        # do_something()
                        #
                        # The above would fail if we don't provide the same dictionary for both scopes.
                        results = eval(python_code, self._locals, self._locals)
                    except Exception:
                        # oops, error encountered. write/redirect to the error signal
                        self._stderr_redirect.write(self._format_exc())
                    else:
                        self.results.emit(str(results))

        # exec
        else:
            # Use two with statements inside each other as python 2.6 doesn't support passing a tuple
            # and Python 3 doesn't support contextlib.nested().
            with self._stdout_redirect:
                with self._stdin_redirect:
                    try:
                        # locals gets passed in as both global and locals to fix look up issues.
                        # See example above in the if eval_code true block.
                        exec(python_code, self._locals, self._locals)
                    except Exception:
                        # oops, error encountered. write/redirect to the error signal
                        self._stderr_redirect.write(self._format_exc())

    def highlight_current_line(self):
        """Highlight the current line of the input widget."""

        extra_selection = QtGui.QTextEdit.ExtraSelection()
        extra_selection.format.setBackground(QtGui.QBrush(self._current_line_color()))
        extra_selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
        extra_selection.cursor = self.textCursor()
        extra_selection.cursor.clearSelection()

        self.setExtraSelections([extra_selection])

    def keyPressEvent(self, event):
        """Intercept any key events for special casing.

        :param event: key press event object.
        """
        if event.key() in [
            QtCore.Qt.Key_Enter,
            QtCore.Qt.Key_Return,
        ]:
            self.add_new_line()
            event.accept()
        elif event.key() == QtCore.Qt.Key_Backspace:
            # Attempt to remove the indentation if the cursor is within the indentation section of the line
            # other wise fall back to default behaviour.
            if self.remove_character_indentation():
                event.accept()
            else:
                super(PythonInputWidget, self).keyPressEvent(event)
        elif (
            event.key() == QtCore.Qt.Key_Slash
            and event.modifiers() == QtCore.Qt.ControlModifier
        ):
            self.block_comment_selection()
            event.accept()
        elif event.key() == QtCore.Qt.Key_Backtab:
            self.unindent()
            event.accept()
        elif event.key() == QtCore.Qt.Key_Tab:
            # intercept the tab key and insert 4 spaces
            self.indent()
            event.accept()
        else:
            super(PythonInputWidget, self).keyPressEvent(event)

    def remove_character_indentation(self):
        """
        Attempts to remove a single indentation block if there is no selection and the cursor is in the indentation
        part of the line. It returns True if we unindented and False if we didn't.
        :return: bool
        """
        # We don't need to decorate this method with @safe_modify_content since it doesn't make any changes itself
        # and calls unindent() which is decorated.
        cur = self.textCursor()
        if not cur.hasSelection():
            user_cur_pos = cur.positionInBlock()
            line = cur.block().text()

            # Now separate out the indentation from the rest of the line and figure out how many spaces it is.
            indentation, rest_of_line = self._split_indentation(line)

            # The current user cursor position is within the indentation.
            if user_cur_pos <= len(indentation) and len(indentation) != 0:
                self.unindent()
                return True
        return False

    @safe_modify_content
    def add_new_line(self):
        """
        Adds a new line from the cursor position.
        The new line will be indented at the same level as the previous line.
        :return: None
        """
        cur = self.textCursor()

        cur_pos, anchor, start, end = self._get_cursor_positions(cur)

        # We only want to match the indentation of the up most selected line.
        cur.setPosition(start)

        # Get the text for the current line, so that we can figure out the current line's indentation.
        line = cur.block().text()

        # Now separate out the indentation from the rest of the line and figure out how many spaces it is.
        indentation, rest_of_line = self._split_indentation(line)
        n_spaces = self._get_indentation_length(indentation)

        # We should check the current position in the line, if it sits somewhere in the indentation then match that.
        cur_pos_in_block = cur.positionInBlock()
        # Note don't use n_spaces in this calculation as tabs might have been removed.
        if not self.textCursor().hasSelection() and cur_pos_in_block < len(indentation):
            n_spaces = cur_pos_in_block

        # Check if the current line has a `:` at the end. Also account for any white spaces or comments after it.
        # If we find one, then the next line should auto indent four spaces.
        # https://regex101.com/r/BnEhPk/1
        match = re.search(r":[ \t]*(#.*)?$", line)
        # Make sure we have a match and that the cursor is after the colon
        if match and cur_pos_in_block > match.span()[0]:
            n_spaces += 4

        # Add a new line plus the number of spaces in the previous line, plus any extra we might have added if a
        # colon was found at the end of the line before.
        new_line = "\n" + (" " * n_spaces)

        # Remove the currently selected text, as usually editors delete the selection and move onto the new line.
        self.textCursor().removeSelectedText()

        cur.insertText(new_line)

    @safe_modify_content
    def block_comment_selection(self):
        """
        Either adds or removes comments from the selected line. If one line in the selection doesn't contain a comment
         then it will add comments to all lines, otherwise it will remove comments from all lines.
        :return: None
        """

        def add_comment_to_line(line):
            # Will insert a hash followed by a space to the given line, and the
            # lowest indentation index for the selected lines.
            return line[:lowest_indent_index] + "# " + line[lowest_indent_index:]

        def remove_comment_to_line(line):
            # Will remove the # from the given line and if present the immediate space after.
            # This regex should strip the first # before a character and the immediate space after if found.
            # https://regex101.com/r/bQ9OXk/1
            altered_line = re.sub(r"^((?:[ \t]+)?)# ?", r"\g<1>", line, 1)
            return altered_line

        # Before attempting to alter the line, we should loop over the selected lines
        # and check if any don't have a # at the start. If we find a line that doesn't then we
        # will want to add commenting to all lines. If we don't find one then we want to remove the comments.
        # Also during this loop we can find the lowest indentation point across all selected lines,
        # and then use that as the index to insert the comment (if we are inserting)

        cur = self.textCursor()

        cur_pos, anchor, start, end = self._get_cursor_positions(cur)

        # Loop over the lines from the bottom up
        cur.setPosition(start)

        add_comment = False
        lowest_indent_index = None

        # This regex matches lines that have a hash before any text.
        # https://regex101.com/r/JsYVpL/1
        hash_pattern = re.compile(r"^((?:[ \t]+)?)#")

        while True:
            line = cur.block().text()

            # check to see if the line has a hash before the first character
            if not hash_pattern.match(line):
                add_comment = True

            # find the lowest indent
            indentation, rest_of_line = self._split_indentation(line)
            before_first_char_index = len(indentation)
            if (
                lowest_indent_index is None
                or before_first_char_index < lowest_indent_index
            ):
                lowest_indent_index = before_first_char_index

            line_pos = cur.position()
            # Now move up a line ready for the next loop and check we haven't gone beyond the start of the selection.
            cur.movePosition(QtGui.QTextCursor.Down)

            if line_pos == cur.position():
                # moving down a line hasn't altered the position so we must be on the last time.
                break

            # Move to the start of the line before checking, so that we can be sure the cursor cannot be on the
            # same line but after the end point.
            cur.movePosition(QtGui.QTextCursor.StartOfLine)
            if cur.position() > end:
                # break out of the loop
                break

        if add_comment:
            self._operate_on_selected_lines(add_comment_to_line)
        else:
            self._operate_on_selected_lines(remove_comment_to_line)

    @safe_modify_content
    def indent(self):
        """
        Will indent the selected lines with four spaces
        """

        def indent_line(line):
            indentation, rest_of_line = self._split_indentation(line)
            n_spaces = self._get_indentation_length(indentation)

            # break the number of spaces down in to multiples of 4
            # so that we indent to whole levels of 4
            r = n_spaces / 4.0
            if r.is_integer():
                n_spaces = n_spaces + 4
            else:
                # math.floor returns an int in Python 3 and a float in Python 2 so ensure it's a int.
                n_spaces = int(math.ceil(r) * 4)

            return (" " * n_spaces) + rest_of_line

        self._operate_on_selected_lines(indent_line)

    @safe_modify_content
    def unindent(self):
        """
        Will attempt to unindent the selected lines by removing four spaces or tab characters.
        """

        def unindent_line(line):
            indentation, rest_of_line = self._split_indentation(line)
            n_spaces = self._get_indentation_length(indentation)

            r = n_spaces / 4.0
            if r.is_integer():
                n_spaces = n_spaces - 4
            else:
                # math.floor returns an int in Python 3 and a float in Python 2 so ensure it's a int.
                n_spaces = int(math.floor(r) * 4)

            return (" " * n_spaces) + rest_of_line

        self._operate_on_selected_lines(unindent_line)

    def line_number_area_width(self):
        """Calculate the width of the line number area."""

        if self._show_line_numbers:
            digits = math.floor(math.log10(self.blockCount())) + 1
            return 6 + self.fontMetrics().boundingRect("8").width() * digits
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
        painter.fillRect(line_num_rect, self._line_number_area_base_color())

        painter.setPen(self.palette().base().color())
        painter.drawLine(line_num_rect.topLeft(), line_num_rect.bottomLeft())
        painter.drawLine(line_num_rect.topLeft(), line_num_rect.topRight())
        painter.drawLine(line_num_rect.bottomLeft(), line_num_rect.bottomRight())

        # ---- process the visible blocks

        block = self.firstVisibleBlock()
        block_num = block.blockNumber()

        top = int(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )

        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= line_num_rect.bottom():

            if block.isVisible() and bottom >= line_num_rect.top():

                num = str(block_num + 1)
                painter.setPen(self._line_number_color())
                painter.drawText(
                    -2,
                    top,
                    self._line_number_area.width(),
                    self.fontMetrics().height(),
                    QtCore.Qt.AlignRight,
                    num,
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
            contents_rect.height(),
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
        save_dialog.setDefaultSuffix(".py")
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
        except Exception as e:
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

    def _current_line_color(self):
        """Returns a line color for the current line highlighting.

        5 parts base color, 1 part highlight.
        """

        if not hasattr(self, "_cur_line_color"):

            palette = self.palette()
            base_color = palette.base().color()
            highlight_color = palette.highlight().color()

            self._cur_line_color = QtGui.QColor(50, 50, 50)

        return self._cur_line_color

    def _format_exc(self):
        """Get the latest stack trace and format it for display."""
        return traceback.format_exc()

    def _line_number_area_base_color(self):
        """Get a line number base color."""

        if not hasattr(self, "_line_num_base_color"):
            self._line_num_base_color = QtGui.QColor(49, 51, 53)

        return self._line_num_base_color

    def _line_number_color(self):
        """Get a line number color."""

        if not hasattr(self, "_line_num_color"):
            self._line_num_color = QtGui.QColor(96, 99, 102)

        return self._line_num_color

    def _readline(self):
        """
        Reads a line of input text from the user.

        :return: a string for the user input.
        """
        dialog = QtGui.QInputDialog(parent=self, flags=QtCore.Qt.FramelessWindowHint)
        dialog.setLabelText("Python is requesting input")
        dialog.adjustSize()

        dialog.resize(self.width() - 2, dialog.height())
        dialog.move(
            self.mapToGlobal(self.rect().topLeft()).x(),
            self.mapToGlobal(self.rect().bottomLeft()).y() - dialog.height(),
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

        if dy:
            self._line_number_area.scroll(0, dy)
        elif (
            self._count_cache["blocks"] != self.blockCount()
            or self._count_cache["cursor_blocks"]
            != self.textCursor().block().lineCount()
        ):
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height()
            )
            self._count_cache = {
                "blocks": self.blockCount(),
                "cursor_blocks": self.textCursor().block().lineCount(),
            }

        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def _update_line_number_area_width(self, count):
        """Update the display of the line number area.

        :param count: block count. unused, but comes from connected singal.

        """
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _operate_on_selected_lines(self, operation):
        """
        This method will operate on the text the user has selected, using the passed operation callable.
        It will also modify the selection so that it is relative to the increase or decrease in length of the lines.

        :param operation: A callable object that accepts a str "line" argument which will perform the desired
         operation on the line.
        :return: None
        """

        cur = self.textCursor()

        cur_pos, anchor, start, end = self._get_cursor_positions(cur)

        # Create new start and end points that we can modify whilst we are iterating of the lines performing
        # the operation so that we can use these to reselect the appropriate text at the end.
        new_start_pos = start
        new_end_pos = end

        # Loop over the lines from the bottom up and un-indent them.
        cur.setPosition(end)

        while True:
            # Jump to the end the end of the line, with both the cursor and the anchor
            cur.movePosition(QtGui.QTextCursor.EndOfLine)
            # Get the text for the block and perform the unindent
            # It appears that a block in our situation represents a line. However if this turns out not to be the case
            # Then we should change this to select the line and then grab the selected text.
            line = cur.block().text()
            altered_line = operation(line)

            if line != altered_line:
                # check if the line has increased in length or decreased.
                increase = True if len(altered_line) > len(line) else False

                # The line must have had it's indentation changed, so record an updated end position
                if increase:
                    new_end_pos += len(altered_line) - len(line)
                else:
                    new_end_pos -= len(line) - len(altered_line)

            # Now move the cursor to the beginning of the line, but leave the anchor so that the line becomes selected
            # and replace the selected text.
            cur.movePosition(
                QtGui.QTextCursor.StartOfLine, QtGui.QTextCursor.KeepAnchor
            )
            cur.removeSelectedText()
            cur.insertText(altered_line)

            # Now capture the position of the beginning of the line so we can check it at the end of this loop
            # to ensure that the new selection cursor position does not shift before the beginning of the line.
            cur.movePosition(QtGui.QTextCursor.StartOfLine)
            beginning_of_line_pos = cur.position()

            # Now move up a line ready for the next loop and check we haven't gone beyond the start of the selection.
            cur.movePosition(QtGui.QTextCursor.Up)
            # Move to the end of the line before checking, so that we can be sure the cursor cannot be on the
            # same line but before the start point.
            cur.movePosition(QtGui.QTextCursor.EndOfLine)
            if cur.position() < start or beginning_of_line_pos == 0:
                # We've moved a line above the start of the selection
                if line != altered_line:
                    if increase:
                        if start != beginning_of_line_pos or cur_pos == anchor:
                            # Only alter the start position on indentation if the selection cursor was not at the
                            # beginning of the line, or if we've not selected a block of text.
                            new_start_pos += len(altered_line) - len(line)
                    else:
                        # The line must have been unindented so record an updated end position
                        new_start_pos -= len(line) - len(altered_line)
                        # If the cursor was selecting the beginning of the line and we unindented,
                        # then don't want to move the selection back as it wil shift on the line before.
                        new_start_pos = (
                            new_start_pos
                            if new_start_pos >= beginning_of_line_pos
                            else beginning_of_line_pos
                        )
                        new_end_pos = (
                            new_end_pos
                            if new_end_pos >= beginning_of_line_pos
                            else beginning_of_line_pos
                        )

                # break out of the while loop
                break

        # Restore the selection, but alter it so that it is relative to the changes we made.
        if cur_pos > anchor:
            cur.setPosition(new_start_pos)
            cur.setPosition(new_end_pos, QtGui.QTextCursor.KeepAnchor)
        else:
            cur.setPosition(new_end_pos)
            cur.setPosition(new_start_pos, QtGui.QTextCursor.KeepAnchor)

        self.setTextCursor(cur)

    def _split_indentation(self, line):
        """
        Returns the line as a tuple broken up into indentation and the rest of the line.
        :param line: str
        :return: tuple containing two strings, the first contains the indentation, and the second contains the
        """
        # The regex separates the indent and the rest of the line into two groups.
        # https://regex101.com/r/XZluTm/2
        m = re.match(r"^([ \t]*)(.*)", line)
        return m.group(1), m.group(2)

    def _get_indentation_length(self, indentation_str):
        """
        Returns the length of the indentation_str but substitutes tabs for four spaces.
        :param line: str
        :return: int
        """
        # convert any tabs to four spaces
        return len(indentation_str.replace("\t", "    "))

    def _get_cursor_positions(self, cursor):
        """
        This method returns back the cursor's position, anchor, and the start and end.
        Since the selection direction can be either way it can be useful to know which
        out of the cursor and anchor positions are the earliest and furthest points, so the start
        and end is also provided.
        :param cursor: QCursor
        :return: tuple containing current cursor position, anchor, start, and end
        """
        cur_pos = cursor.position()  # Where a selection ends
        anchor = cursor.anchor()  # Where a selection starts (can be the same as above)

        # Since the anchor and the cursor position can be higher or lower in position than each other
        # depending on which direction you selected the text, you should mark the position of the start and end
        # with the start being the lowest position and the end being the highest position.
        start = cur_pos if cur_pos < anchor else anchor
        end = cur_pos if cur_pos > anchor else anchor
        return cur_pos, anchor, start, end


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
