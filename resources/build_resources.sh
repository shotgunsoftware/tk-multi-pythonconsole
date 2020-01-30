#!/usr/bin/env bash
#
# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# The path to output all built .py files to:
UI_PYTHON_PATH=../python/app/ui

# Remove any problematic profiles from pngs.
for f in *.png; do mogrify $f; done

# Helper functions to build UI files
function build_qt {
    echo " > Building " $2

    # Compile ui to python
    $1 $2 > $UI_PYTHON_PATH/$3.py

    # Replace PySide imports with tank.platform.qt and remove line containing Created by date
    # On OSX sed doesn't interpret \n as a new line. Instead we must insert the new line string
    lf=$'\n'

    sed -i "" -e "s/\(from PySide import \(.*\)\)/try:\\$lf    from sgtk.platform.qt import \2\\$lf\except ImportError:\\$lf    try:\\$lf        from PySide2 import \2\\$lf    except ImportError:\\$lf        \1/g" -e "/# Created:/d" $UI_PYTHON_PATH/$3.py
    # NOTE: This repo is typically used as a Toolkit app, but it is also possible use the console in a
    # stand alone fashion. This try/except allows portions of the console to be imported outside of a
    # Shotgun/Toolkit environment. Flame, for example, uses the console when there is no Toolkit
    # engine running.
}

function build_ui {
    build_qt "pyside-uic --from-imports" "$1.ui" "$1"
}

function build_res {
    build_qt "pyside-rcc -py3" "$1.qrc" "$1_rc"
}


# build UI's:
#echo "building user interfaces..."
#build_ui dialog
# add any additional .ui files you want converted here!

# build resources
echo "building resources..."
build_res resources
