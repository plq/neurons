
#
# spyne - Copyright (C) Spyne contributors.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301
#

#
# Copyright (c) 2004-2016, CherryPy Team (team@cherrypy.org)
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the CherryPy Team nor the names of its contributors
#       may be used to endorse or promote products derived from this software
#       without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

import os
import re
import sys
import time
import threading


# _module__file__base is used by Autoreload to make
# absolute any filenames retrieved from sys.modules which are not
# already absolute paths.  This is to work around Python's quirk
# of importing the startup script and using a relative filename
# for it in sys.modules.
#
# Autoreload examines sys.modules afresh every time it runs. If an application
# changes the current directory by executing os.chdir(), then the next time
# Autoreload runs, it will not be able to find any filenames which are
# not absolute paths, because the current directory is not the same as when the
# module was first imported.  Autoreload will then wrongly conclude the file
# has "changed", and initiate the shutdown/re-exec sequence.
# See cherrypy ticket #917.
# For this workaround to have a decent probability of success, this module
# needs to be imported as early as possible, before the app has much chance
# to change the working directory.
_module__file__base = os.getcwd()


class BackgroundTask(threading.Thread):
    """A subclass of threading.Thread whose run() method repeats.

    Use this class for most repeating tasks. It uses time.sleep() to wait
    for each interval, which isn't very responsive; that is, even if you call
    self.cancel(), you'll have to wait until the sleep() call finishes before
    the thread stops. To compensate, it defaults to being daemonic, which means
    it won't delay stopping the whole process.
    """

    def __init__(self, interval, function, args=None, kwargs=None, bus=None):
        threading.Thread.__init__(self)

        if args is None:
            args = []

        if kwargs is None:
            kwargs = {}

        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.running = False
        self.bus = bus

        # default to daemonic
        self.daemon = True

    def cancel(self):
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            time.sleep(self.interval)
            if not self.running:
                return
            try:
                self.function(*self.args, **self.kwargs)
            except Exception:
                if self.bus:
                    self.bus.log("Error in background task thread function %r."
                                 % self.function, level=40, traceback=True)
                # Quit on first error to avoid massive logs.
                raise


class SimplePlugin(object):

    """Plugin base class which auto-subscribes methods for known channels."""

    bus = None
    """A :class:`Bus <cherrypy.process.wspbus.Bus>`, usually cherrypy.engine.
    """

    def __init__(self, bus):
        self.bus = bus

    def subscribe(self):
        """Register this object as a (multi-channel) listener on the bus."""
        for channel in self.bus.listeners:
            # Subscribe self.start, self.exit, etc. if present.
            method = getattr(self, channel, None)
            if method is not None:
                self.bus.subscribe(channel, method)

    def unsubscribe(self):
        """Unregister this object as a listener on the bus."""
        for channel in self.bus.listeners:
            # Unsubscribe self.start, self.exit, etc. if present.
            method = getattr(self, channel, None)
            if method is not None:
                self.bus.unsubscribe(channel, method)


class Monitor(SimplePlugin):

    """WSPBus listener to periodically run a callback in its own thread."""

    callback = None
    """The function to call at intervals."""

    frequency = 60
    """The time in seconds between callback runs."""

    thread = None
    """A :class:`BackgroundTask<cherrypy.process.plugins.BackgroundTask>`
    thread.
    """

    def __init__(self, bus, callback, frequency=60, name=None):
        SimplePlugin.__init__(self, bus)
        self.callback = callback
        self.frequency = frequency
        self.thread = None
        self.name = name

    def start(self):
        """Start our callback in its own background thread."""
        if self.frequency > 0:
            threadname = self.name or self.__class__.__name__
            if self.thread is None:
                self.thread = BackgroundTask(self.frequency, self.callback,
                                             bus=self.bus)
                self.thread.setName(threadname)
                self.thread.start()
                self.bus.log("Started monitor thread %r." % threadname)
            else:
                self.bus.log("Monitor thread %r already started." % threadname)
    start.priority = 70

    def stop(self):
        """Stop our callback's background task thread."""
        if self.thread is None:
            self.bus.log("No thread running for %s." %
                         self.name or self.__class__.__name__)
        else:
            if self.thread is not threading.currentThread():
                name = self.thread.getName()
                self.thread.cancel()
                if not self.thread.daemon:
                    self.bus.log("Joining %r" % name)
                    self.thread.join()
                self.bus.log("Stopped thread %r." % name)
            self.thread = None

    def graceful(self):
        """Stop the callback's background task thread and restart it."""
        self.stop()
        self.start()


class Autoreloader(Monitor):
    """Monitor which re-executes the process when files change.

    This :ref:`plugin<plugins>` restarts the process (via :func:`os.execv`)
    if any of the files it monitors change (or is deleted). By default, the
    autoreloader monitors all imported modules; you can add to the
    set by adding to ``autoreload.files``::

        cherrypy.engine.autoreload.files.add(myFile)

    If there are imported files you do *not* wish to monitor, you can
    adjust the ``match`` attribute, a regular expression. For example,
    to stop monitoring cherrypy itself::

        cherrypy.engine.autoreload.match = r'^(?!cherrypy).+'

    Like all :class:`Monitor<cherrypy.process.plugins.Monitor>` plugins,
    the autoreload plugin takes a ``frequency`` argument. The default is
    1 second; that is, the autoreloader will examine files once each second.
    """

    files = None
    """The set of files to poll for modifications."""

    frequency = 1
    """The interval in seconds at which to poll for modified files."""

    match = '.*'
    """A regular expression by which to match filenames."""

    def __init__(self, bus, frequency=1, match='.*'):
        self.mtimes = {}
        self.files = set()
        self.match = match
        Monitor.__init__(self, bus, self.run, frequency)

    def start(self):
        """Start our own background task thread for self.run."""
        if self.thread is None:
            self.mtimes = {}
        Monitor.start(self)
    start.priority = 70

    def sysfiles(self):
        """Return a Set of sys.modules filenames to monitor."""
        files = set()
        for k, m in list(sys.modules.items()):
            if re.match(self.match, k):
                if (
                    hasattr(m, '__loader__') and
                    hasattr(m.__loader__, 'archive')
                ):
                    f = m.__loader__.archive
                else:
                    f = getattr(m, '__file__', None)
                    if f is not None and not os.path.isabs(f):
                        # ensure absolute paths so a os.chdir() in the app
                        # doesn't break me
                        f = os.path.normpath(
                            os.path.join(_module__file__base, f))
                files.add(f)
        return files

    def run(self):
        """Reload the process if registered files have been modified."""
        for filename in self.sysfiles() | self.files:
            if filename:
                if filename.endswith('.pyc'):
                    filename = filename[:-1]

                oldtime = self.mtimes.get(filename, 0)
                if oldtime is None:
                    # Module with no .py file. Skip it.
                    continue

                try:
                    mtime = os.stat(filename).st_mtime
                except OSError:
                    # Either a module with no .py file, or it's been deleted.
                    mtime = None

                if filename not in self.mtimes:
                    # If a module has no .py file, this will be None.
                    self.mtimes[filename] = mtime
                else:
                    if mtime is None or mtime > oldtime:
                        # The file has been deleted or modified.
                        self.bus.log("Restarting because %s changed." %
                                     filename)
                        self.thread.cancel()
                        self.bus.log("Stopped thread %r." %
                                     self.thread.getName())
                        self.bus.restart()
                        return
