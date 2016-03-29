
## Shotgun Python Console

This is a python console panel for use in DCCs with an embeded python interpreter
that have limited or no support for interacting with said interpreter.

Once installed, the console is registered as a panel in the DCC and is available
in the Shotgun menu. In apps that support embedded Toolkit panels (maya, nuke,
houdini), the console will display in a docked panel. When using with older versions
of these DCCs or in a DCC that does not support panels, the console will simply
be shown as a regular Toolkit dialog.

Here are some screenshots of the console running in various Shotgun engines:

### Maya

<a href="https://raw.githubusercontent.com/josh-t/tk-multi-pythonconsole/master/docs/images/screen_maya.png"">
    <img src="https://raw.githubusercontent.com/josh-t/tk-multi-pythonconsole/master/docs/images/screen_maya.png" width="500px">
</a>

### Nuke

<a href="https://raw.githubusercontent.com/josh-t/tk-multi-pythonconsole/master/docs/images/screen_nuke.png">
    <img src="https://raw.githubusercontent.com/josh-t/tk-multi-pythonconsole/master/docs/images/screen_nuke.png" width="500px">
</a>

### 3ds Max

... coming soon

## Features

The console has an input area for editing python. The input editor includes line numbers,
highlights the cursor's current line, and does some basic syntax highlighting.

The output displays the results of the executed python. Echoing the source python
commands is turned on by default and is differentiated in the output by being
prefixed with `>>>`. There is a toggle for turning the echo off.

Syntax and Runtime errors are shown in red with a full stack trace for debugging.

There are buttons for clearing the input and output areas.

There are also buttons for loading an external python file as well as saving the
current editor contents.

There is a button to execute the current editor contents as well as a shortcut
`Ctrl+Enter` (`Command+Enter` on mac).

The console attempts to use the palette of the DCC to give it an integrated  look
and feel.

Some Shotgun/Toolkit globals are pre-defined in the console, similar to the `tk-shell` engine.
* Tk API handle is available via the `tk` variable
* Shotgun API handle is available via the `shotgun` variable
* The current context is stored in the `context` variable
* The shell engine can be accessed via the `engine` variable

## Installation

This app works in conjunction with the Shotgun Pipeline Toolkit.

To install it, simply run:

```
# ./tank install_app <context> <engine> https://github.com/josh-t/tk-multi-pythonconsole.git
# example:

./tank install_app shot_step nuke https://github.com/josh-t/tk-multi-pythonconsole.git

```

- For general information and documentation on Shotgun Toolkit, click here: https://support.shotgunsoftware.com/entries/95441257
- For information about Shotgun in general, click here: http://www.shotgunsoftware.com/toolkit

## Attribution

This app is based on the **awesome** work of Mike Kessler: https://github.com/mikepkes/pyqtterm