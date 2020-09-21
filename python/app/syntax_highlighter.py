# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import keyword as py_keywords

# NOTE: This repo is typically used as a Toolkit app, but it is also possible use the console in a
# stand alone fashion. This try/except allows portions of the console to be imported outside of a
# Shotgun/Toolkit environment. Flame, for example, uses the console when there is no Toolkit
# engine running.
from .qt_importer import QtCore, QtGui

try:
    from tank_vendor.six.moves import builtins
except ImportError:
    import sys

    if sys.version_info.major == 2:
        import __builtin__ as builtins
    elif sys.version_info.major == 3:
        import builtins

from .util import colorize

# based on: https://wiki.python.org/moin/PyQt/Python%20syntax%20highlighting


def _format(color, style=""):
    """Return a QtGui.QTextCharFormat with the given attributes.
    """

    _format = QtGui.QTextCharFormat()
    _format.setForeground(color)
    if "bold" in style:
        _format.setFontWeight(QtGui.QFont.Bold)
    if "italic" in style:
        _format.setFontItalic(True)

    return _format


class PythonSyntaxHighlighter(QtGui.QSyntaxHighlighter):
    """Syntax highlighter for the Python language."""

    # Python keywords
    keywords = py_keywords.kwlist

    # Python builtins
    builtins = dir(builtins)

    # Python operators
    operators = [
        r"=",
        # Comparison
        r"==",
        r"!=",
        r"<",
        r"<=",
        r">",
        r">=",
        # Arithmetic
        r"\+",
        r"-",
        r"\*",
        r"/",
        r"//",
        r"\%",
        r"\*\*",
        # In-place
        r"\+=",
        r"-=",
        r"\*=",
        r"/=",
        r"\%=",
        # Bitwise
        r"\^",
        r"\|",
        r"\&",
        r"\~",
        r">>",
        r"<<",
    ]

    # Python braces
    braces = [
        r"\{",
        r"\}",
        r"\(",
        r"\)",
        r"\[",
        r"\]",
    ]

    def __init__(self, document, palette):
        QtGui.QSyntaxHighlighter.__init__(self, document)

        self._palette = palette

        # Multi-line strings (expression, flag, style)
        # FIXME: The triple-quotes in these two lines will mess up the
        # syntax highlighting from this point onward
        self.tri_single = (QtCore.QRegExp("'''"), 1, self._style("string2"))
        self.tri_double = (QtCore.QRegExp('"""'), 2, self._style("string2"))

        rules = []

        # Keyword, operator, and brace rules
        rules += [
            (r"\b%s\b" % w, 0, self._style("keyword"))
            for w in PythonSyntaxHighlighter.keywords
        ]
        rules += [
            (r"\b%s\b" % w, 0, self._style("builtin"))
            for w in PythonSyntaxHighlighter.builtins
        ]
        rules += [
            (r"%s" % o, 0, self._style("operator"))
            for o in PythonSyntaxHighlighter.operators
        ]
        rules += [
            (r"%s" % b, 0, self._style("brace")) for b in PythonSyntaxHighlighter.braces
        ]

        # All other rules
        rules += [
            # Numeric literals
            (r"\b[+-]?[0-9]+[lL]?\b", 0, self._style("numbers")),
            (r"\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b", 0, self._style("numbers")),
            (
                r"\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b",
                0,
                self._style("numbers"),
            ),
            # 'self'
            (r"\bself\b", 0, self._style("self")),
            # Double-quoted string, possibly containing escape sequences
            (r'"[^"\\]*(\\.[^"\\]*)*"', 0, self._style("string")),
            # Single-quoted string, possibly containing escape sequences
            (r"'[^'\\]*(\\.[^'\\]*)*'", 0, self._style("string")),
            # 'def' followed by an identifier
            (r"\bdef\b\s*(\w+)", 1, self._style("defclass")),
            # 'class' followed by an identifier
            (r"\bclass\b\s*(\w+)", 1, self._style("defclass")),
            # From '#' until a newline
            (r"#[^\n]*", 0, self._style("comment")),
        ]

        # Build a QtCore.QRegExp for each pattern
        self.rules = [(QtCore.QRegExp(pat), index, fmt) for (pat, index, fmt) in rules]

    def _style(self, style_type):

        styles = {
            "keyword": _format(QtGui.QColor(204, 120, 50), style="",),
            "builtin": _format(QtGui.QColor(136, 136, 198), style="",),
            "operator": _format(QtGui.QColor(169, 183, 198), style="",),
            "brace": _format(QtGui.QColor(169, 183, 198), style="",),
            "defclass": _format(QtGui.QColor(255, 198, 109), style="bold",),
            "string": _format(QtGui.QColor(106, 135, 89), style="bold",),
            "string2": _format(QtGui.QColor(98, 151, 85), style="",),
            "comment": _format(QtGui.QColor(128, 128, 128), style="italic",),
            "self": _format(QtGui.QColor(148, 85, 141), style="",),
            "numbers": _format(QtGui.QColor(104, 151, 187), style="",),
        }

        return styles[style_type]

    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text.
        """
        # Do other syntax formatting
        for expression, nth, format in self.rules:
            index = expression.indexIn(text, 0)

            while index >= 0:
                # We actually want the index of the nth match
                index = expression.pos(nth)
                length = len(expression.cap(nth))
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

        # Do multi-line strings
        in_multiline = self.match_multiline(text, *self.tri_single)
        if not in_multiline:
            in_multiline = self.match_multiline(text, *self.tri_double)

    def match_multiline(self, text, delimiter, in_state, style):
        """Do highlighting of multi-line strings. ``delimiter`` should be a
        ``QtCore.QRegExp`` for triple-single-quotes or triple-double-quotes, and
        ``in_state`` should be a unique integer to represent the corresponding
        state changes when inside those strings. Returns True if we're still
        inside a multi-line string when this function is finished.
        """
        # If inside triple-single quotes, start at 0
        if self.previousBlockState() == in_state:
            start = 0
            add = 0
        # Otherwise, look for the delimiter on this line
        else:
            start = delimiter.indexIn(text)
            # Move past this match
            add = delimiter.matchedLength()

        # As long as there's a delimiter match on this line...
        while start >= 0:
            # Look for the ending delimiter
            end = delimiter.indexIn(text, start + add)
            # Ending delimiter on this line?
            if end >= add:
                length = end - start + add + delimiter.matchedLength()
                self.setCurrentBlockState(0)
            # No; multi-line string
            else:
                self.setCurrentBlockState(in_state)
                length = len(text) - start + add
            # Apply formatting
            self.setFormat(start, length, style)
            # Look for the next match
            start = delimiter.indexIn(text, start + length)

        # Return True if still inside a multi-line string, False otherwise
        if self.currentBlockState() == in_state:
            return True
        else:
            return False
