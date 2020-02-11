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
import io

# NOTE: This repo is typically used as a Toolkit app, but it is also possible use the console in a
# stand alone fashion. This try/except allows portions of the console to be imported outside of a
# Shotgun/Toolkit environment. Flame, for example, uses the console when there is no Toolkit
# engine running.
from .qt_importer import QtGui, QtCore

# make sure the images are imported for access to the resources
from .ui import resources_rc

from .input_widget import PythonInputWidget
from .output_widget import OutputStreamWidget
from .util import colorize


class PythonConsoleWidget(QtGui.QWidget):
    """A dockable, interactive python console widget."""

    def __init__(self, parent=None):
        """
        Initialize the console.

        :param parent: The console's parent widget.
        """
        super(PythonConsoleWidget, self).__init__(parent)

        self.tabs = PythonTabWidget(self)

        # ---- output related buttons

        # clear output
        out_clear_btn = QtGui.QToolButton(self)
        out_clear_btn.setMinimumSize(QtCore.QSize(30, 30))
        out_clear_btn.setMaximumSize(QtCore.QSize(30, 30))
        out_clear_btn.setObjectName("out_clear_btn")
        out_clear_btn.setToolTip("Clear all output.")

        # echo output
        self._out_echo_btn = QtGui.QToolButton()
        self._out_echo_btn.setCheckable(True)
        self._out_echo_btn.setChecked(True)
        self._out_echo_btn.setDown(True)
        self._out_echo_btn.setMinimumSize(QtCore.QSize(30, 30))
        self._out_echo_btn.setMaximumSize(QtCore.QSize(30, 30))
        self._out_echo_btn.setObjectName("out_echo_btn")
        self._out_echo_btn.setToolTip("Echo python commands in output.")

        # output buttons layout
        out_btn_box = QtGui.QVBoxLayout()
        out_btn_box.setContentsMargins(0, 0, 0, 0)
        out_btn_box.addWidget(out_clear_btn)
        out_btn_box.addSpacing(10)
        out_btn_box.addWidget(self._out_echo_btn)
        out_btn_box.addSpacing(10)
        out_btn_box.addStretch()

        # ---- input

        # clear input
        in_clear_btn = QtGui.QToolButton()
        in_clear_btn.setMinimumSize(QtCore.QSize(30, 30))
        in_clear_btn.setMaximumSize(QtCore.QSize(30, 30))
        in_clear_btn.setObjectName("in_clear_btn")
        in_clear_btn.setToolTip("Clear all input.")

        # show/hide line numbers
        self._line_num_btn = QtGui.QToolButton()
        self._line_num_btn.setCheckable(True)
        self._line_num_btn.setChecked(True)
        self._line_num_btn.setDown(True)
        self._line_num_btn.setMinimumSize(QtCore.QSize(30, 30))
        self._line_num_btn.setMaximumSize(QtCore.QSize(30, 30))
        self._line_num_btn.setObjectName("line_num_btn")
        self._line_num_btn.setToolTip("Show/hide line numbers.")

        # open file
        self._open_file_menu = QtGui.QMenu(self)
        self._open_file_menu.aboutToShow.connect(self._build_open_file_menu)

        self._cached_static_actions = {}

        in_open_btn = QtGui.QToolButton()
        in_open_btn.setMinimumSize(QtCore.QSize(30, 30))
        in_open_btn.setMaximumSize(QtCore.QSize(30, 30))
        in_open_btn.setObjectName("in_open_btn")
        in_open_btn.setToolTip("Load python script from a file.")
        # Delayed load of menu.
        # Click and hold the open button to trigger the menu.
        in_open_btn.setMenu(self._open_file_menu)
        in_open_btn.setPopupMode(QtGui.QToolButton.DelayedPopup)

        # reusable action for opening from disk
        open_file_icon = QtGui.QIcon(":/tk_multi_pythonconsole/open.png")
        self._open_file_action = QtGui.QAction(
            open_file_icon, "Load from disk...", self
        )
        self._open_file_action.triggered.connect(self.open)

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
        self._in_exec_btn.setToolTip(
            "Execute the current python script. Shortcut: Ctrl+Enter"
        )

        # add tab
        add_tab_btn = QtGui.QToolButton(self)
        add_tab_btn.setMinimumSize(QtCore.QSize(12, 12))
        add_tab_btn.setMaximumSize(QtCore.QSize(12, 12))
        add_tab_btn.setObjectName("add_tab_btn")
        add_tab_btn.setToolTip("Add a new tab")

        # input buttons layout
        in_btn_box = QtGui.QVBoxLayout()
        in_btn_box.setContentsMargins(0, 0, 0, 0)
        in_btn_box.addStretch()
        in_btn_box.addWidget(self._in_exec_btn)
        in_btn_box.addSpacing(10)
        in_btn_box.addWidget(self._in_save_btn)
        in_btn_box.addSpacing(10)
        in_btn_box.addWidget(in_open_btn)
        in_btn_box.addSpacing(10)
        in_btn_box.addWidget(in_clear_btn)
        in_btn_box.addSpacing(10)
        in_btn_box.addWidget(self._line_num_btn)
        in_btn_box.addSpacing(20)
        in_btn_box.addWidget(add_tab_btn)
        in_btn_box.addSpacing(4)

        in_btn_box.setAlignment(
            add_tab_btn, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignCenter
        )

        button_layout = QtGui.QVBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(0)
        button_layout.addLayout(out_btn_box)
        button_layout.addStretch()
        button_layout.addLayout(in_btn_box)

        # main layout
        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addWidget(self.tabs)
        layout.addLayout(button_layout)

        layout.setStretchFactor(self.tabs, 100)

        # ---- connect singals and slots

        self._cur_tab_widget = lambda: self.tabs.currentWidget()

        # buttons clicked
        out_clear_btn.clicked.connect(
            lambda: self._cur_tab_widget().output_widget.clear()
        )

        self._in_save_btn.clicked.connect(
            lambda: self._cur_tab_widget().input_widget.save()
        )

        in_open_btn.clicked.connect(self.open)

        in_clear_btn.clicked.connect(
            lambda: self._cur_tab_widget().input_widget.clear()
        )

        self._in_exec_btn.clicked.connect(
            lambda: self._cur_tab_widget().input_widget.execute()
        )

        add_tab_btn.clicked.connect(self.tabs.add_tab)

        # toggles
        self._out_echo_btn.toggled.connect(
            lambda t: self._cur_tab_widget().input_widget.toggle_echo(t)
        )

        self._line_num_btn.toggled.connect(
            lambda t: self._cur_tab_widget().input_widget.toggle_line_numbers(t)
        )

        self.tabs.input_text_changed.connect(self._check_button_state)
        self.tabs.currentChanged.connect(self._check_button_state)

        # ---- set the default state

        # no point in saving until there are contents
        self._in_save_btn.setEnabled(False)

    def open(self, path=None):
        """Open an external python script to edit.

        :param path: A path to a directory to browse or file to open.
        """

        # browse to a file to open
        if not path or os.path.isdir(path):
            open_dialog = QtGui.QFileDialog(
                parent=QtGui.QApplication.activeWindow(),
                caption="Open Python Script",
                # If this is called form a QAction trigger then the path gets passed the "checked" state of the action.
                # We should treat this as if no Path has been passed.
                directory=path if type(path) is str else "",
                filter="*.py",
            )
            open_dialog.setFileMode(QtGui.QFileDialog.ExistingFile)
            open_dialog.setOption(QtGui.QFileDialog.DontResolveSymlinks, True)
            open_dialog.setOption(QtGui.QFileDialog.DontUseNativeDialog, True)
            open_dialog.setViewMode(QtGui.QFileDialog.Detail)
            if open_dialog.exec_():
                path = open_dialog.selectedFiles()[0]

        if not path:
            return

        # clear the contents, open and load the file
        # Use io.open() instead of open() so that we can provide the encoding to use for python 2.6 > 2.7.
        # Python 3 supports passing the encoding to open().
        # FIXME: Using the encoding option makes things better but not perfect for unicode strings.
        with io.open(path, "r", encoding="utf-8") as fh:
            python_script = "".join(fh.readlines())
            index = self.tabs.add_tab(
                name=os.path.split(path)[-1], contents=python_script,
            )
            widget = self.tabs.widget(index)
            widget.input_widget.setPlainText(python_script)

    def _build_open_file_menu(self):
        """
        Dynamically build the popup menu for the file open/load button.
        This is called when the menu is triggered via a delayed load.
        The user must click and hold the open button to trigger the menu building.
        """

        self._open_file_menu.clear()
        self._open_file_menu.addAction(self._open_file_action)

    def _check_button_state(self):
        """
        Checks state to determine if buttons should be toggled, disabled, etc.
        """

        # see if save/exc should be enabled
        script_len = len(self._cur_tab_widget().input_widget.toPlainText())
        self._in_save_btn.setEnabled(script_len > 0)
        self._in_exec_btn.setEnabled(script_len > 0)

        # see if line numbers turned on for the widget
        show_line_nums = self._cur_tab_widget().input_widget.showing_line_numbers()
        self._line_num_btn.setDown(show_line_nums)
        self._line_num_btn.setChecked(show_line_nums)

        # see if echo is enabled
        echo = self._cur_tab_widget().input_widget.echoing_output()
        self._out_echo_btn.setDown(echo)
        self._out_echo_btn.setChecked(echo)


class PythonTabWidget(QtGui.QTabWidget):
    """A tab widget where each tab contains an input and output widget.


    :signal: ``input_text_changed(str)`` - emits the input widget's text as the
        text changes.
    :signal: ``tab_renamed(int)`` - emits the index of a tab when it is renamed
    :signal: ``tab_added(int)`` - emits the index of newly added tabs.

    """

    input_text_changed = QtCore.Signal(str)
    tab_renamed = QtCore.Signal(int)
    tab_added = QtCore.Signal(int)

    def __init__(self, parent=None):
        """
        Initialize the tab widget.

        :param parent:
        """

        super(PythonTabWidget, self).__init__(parent)

        # setup the tabs on the bottom, make the closable and movable
        self.setTabPosition(QtGui.QTabWidget.South)
        self.setTabsClosable(True)
        self.tabBar().setMovable(True)

        # ---- connect signals

        self._emit_current_input_text = lambda: self.input_text_changed.emit(
            self.currentWidget().input_widget.toPlainText()
        )
        self.tabCloseRequested.connect(self.remove_tab)

        # watch for double click events on the tabbar
        self.tabBar().installEventFilter(self)

    def add_tab(self, name=None, contents=None, icon=None):
        """
        Add a new tab.

        :param name: The name of the new tab or ``None``
        :param contents: The contents of the new tab's input or ``None``.
        :param icon: The icon to use for the new tab or ``None``.

        :return: The index of the new tab.
        """

        # if no contents supplied, add a timestamped comment to the input
        contents = contents or ""

        # splitter
        widget = _PythonConsoleSplitter(QtCore.Qt.Vertical, self)
        widget.input_widget.setPlainText(contents)

        name = name or ".py"

        # add the tab
        if icon:
            index = self.addTab(widget, icon, name)
        else:
            index = self.addTab(widget, name)

        # make sure the new tab is current
        self.setCurrentIndex(index)

        # connect input and output widgets
        widget.input_widget.input.connect(widget.output_widget.add_input)
        widget.input_widget.output.connect(widget.output_widget.add_output)
        widget.input_widget.error.connect(widget.output_widget.add_error)
        widget.input_widget.results.connect(widget.output_widget.add_results)
        widget.input_widget.textChanged.connect(self._emit_current_input_text)

        # emit the signal that the new tab was added
        self.tab_added.emit(index)

        # adds a timestamp
        time_stamp = datetime.now().strftime("%x %X")
        widget.output_widget.add_input(
            "---- [Tab created %s] ----\n\n" % (time_stamp,), prefix=""
        )

        # TODO: do something with the description

        return index

    def eventFilter(self, obj, event):
        """
        Watches for double clicks on the tab bar to allow renaming tabs.
        """

        if obj == self.tabBar():
            if event.type() == QtCore.QEvent.MouseButtonDblClick:
                self._prompt_rename_tab()
                return True

        return super(PythonTabWidget, self).eventFilter(obj, event)

    def get_tab_info(self):
        """
        Returns a dictionary of information about all the existing tabs.

        Typically used for saving the widget's state.
        """

        tab_info = []

        for index in range(0, self.count()):
            widget = self.widget(index)
            tab_info.append(
                {
                    "tab_name": self.tabText(index),
                    "tab_contents": widget.input_widget.toPlainText(),
                }
            )

        return tab_info

    def goto_tab(self, offset):
        """
        Handles setting the current index when the supplied offset is outside
        the range of the tab widget's indices.

        Typically used by hotkeys for navigating through tabs.
        """

        new_index = self.currentIndex() + offset
        if new_index >= self.count():
            new_index = 0
        elif new_index < 0:
            new_index = self.count() - 1

        self.setCurrentIndex(new_index)

    def keyPressEvent(self, event):
        """
        Adds support for tab creation and navigation via hotkeys.
        """

        if QtCore.Qt.ControlModifier & event.modifiers():
            # Ctrl+T to add a new tab
            if event.key() == QtCore.Qt.Key_T:
                self.add_tab()
                return True
            # Ctrl+Shift+[ or Ctrl+Shift+] to navigate tabs
            if QtCore.Qt.ShiftModifier & event.modifiers():
                if event.key() in [QtCore.Qt.Key_BracketLeft]:
                    self.goto_tab(-1)
                elif event.key() in [QtCore.Qt.Key_BracketRight]:
                    self.goto_tab(1)

        return False

    def remove_tab(self, index):
        """
        Remove the tab for the supplied index.
        """

        self.blockSignals(True)
        self.removeTab(index)
        self.blockSignals(False)

        if self.count() == 0:
            self.add_tab()

    def _prompt_rename_tab(self):
        """
        Shows a dialog prompt for tab renaming.
        """

        dialog = QtGui.QInputDialog(parent=self, flags=QtCore.Qt.FramelessWindowHint)
        dialog.setLabelText("New Tab Name:")
        dialog.adjustSize()

        parent_pos = self.mapToGlobal(self.pos())

        dialog.resize(self.width(), dialog.height())
        dialog.move(
            self.mapToGlobal(self.rect().topLeft()).x(),
            self.mapToGlobal(self.rect().bottomLeft()).y()
            - dialog.height()
            - self.tabBar().height(),
        )

        if dialog.exec_() == QtGui.QDialog.Accepted:
            new_name = str(dialog.textValue()).strip()
            if new_name:
                self.setTabText(self.currentIndex(), str(dialog.textValue()))


class _PythonConsoleSplitter(QtGui.QSplitter):
    """
    A light wrapper around QSplitter that exposes internal input/output/info widgets.
    """

    def __init__(self, orientation, parent):
        """
        Initialize the splitter.

        :param orientation: Splitter orientation
        :param parent: The parent ``QtGui.QWidget``
        """

        super(_PythonConsoleSplitter, self).__init__(orientation, parent)

        self.output_widget = OutputStreamWidget(parent=self)
        self.input_widget = PythonInputWidget(parent=self)
        self.info_widget = _PythonInputInfoWidget(parent=self)

        self.addWidget(self.output_widget)

        input_widgets_layout = QtGui.QVBoxLayout()
        input_widgets_layout.setContentsMargins(0, 0, 0, 0)
        input_widgets_layout.setSpacing(0)
        input_widgets_layout.addWidget(self.input_widget)
        input_widgets_layout.addWidget(self.info_widget)

        input_widgets = QtGui.QWidget(self)
        input_widgets.setLayout(input_widgets_layout)

        self.addWidget(input_widgets)

        self.input_widget.cursor_column_changed.connect(
            self.info_widget.set_current_column
        )


class _PythonInputInfoWidget(QtGui.QWidget):
    """
    An internal widget used to display some additional information.
    """

    def __init__(self, parent=None):
        """
        Initialize the info widget.

        :param parent: The widget's parent.
        """

        super(_PythonInputInfoWidget, self).__init__(parent)

        self._column_lbl = QtGui.QLabel()

        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch()
        layout.addWidget(self._column_lbl)

        self._text_grey = colorize(
            self.palette().window().color(), 1, self.palette().windowText().color(), 1,
        ).name()

    def set_current_column(self, col):
        """
        Sets the display for the current column.

        :param int col: The column number to display.
        """
        self._column_lbl.setText(
            "<font color='%s'>col: %s</font>" % (self._text_grey, str(col),)
        )
