# encoding: utf8
#
# This file is part of the Neurons project.
# Copyright (c), Arskom Ltd. (arskom.com.tr),
#                Burak Arslan <burak.arslan@arskom.com.tr>.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the Arskom Ltd., the neurons project nor the names of
#   its its contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

# retrieved from: http://code.activestate.com/recipes/278731/
# Licensed under the PSF License

"""Disk And Execution MONitor (Daemon)

Configurable daemon behaviors:

   1.) The current working directory set to the "/" directory.
   2.) The current file creation mode mask set to 0.
   3.) Close all open files (1024).
   4.) Redirect standard I/O streams to "/dev/null".

A failed call to fork() now raises an exception.

References:
   1) Advanced Programming in the Unix Environment: W. Richard Stevens
   2) Unix Programming Frequently Asked Questions:
         http://www.erlenstar.demon.co.uk/unix/faq_toc.html
"""

__author__ = "Chad J. Schroeder"
__copyright__ = "Copyright (C) 2005 Chad J. Schroeder"

__revision__ = "$Id$"
__version__ = "0.2"


import os
import logging
logger = logging.getLogger(__name__)


# Default maximum for the number of available file descriptors.
MAXFD = 1024


def daemonize_do(umask=0, workdir='/', maxfd=None, redirect_to=os.devnull):
    """Detach a process from the controlling terminal and run it in the
    background as a daemon.

    :param umask: File mode creation mask of the daemon.
    :param workdir: Default working directory for the daemon.
    :param maxfd: Default maximum for the number of available file descriptors.
    :param redirect_to: The target for standard I/O file descriptors. By
        default, it's `/dev/null`.
    """

    # Fork a child process so the parent can exit.  This returns control to
    # the command-line or shell.  It also guarantees that the child will not
    # be a process group leader, since the child receives a new process ID
    # and inherits the parent's process group ID.  This step is required
    # to insure that the next call to os.setsid is successful.
    pid = os.fork()

    if pid == 0:      # The first child.
        # To become the session leader of this new session and the process group
        # leader of the new process group, we call os.setsid().  The process is
        # also guaranteed not to have a controlling terminal.
        os.setsid()

        # Is ignoring SIGHUP necessary?
        #
        # It's often suggested that the SIGHUP signal should be ignored before
        # the second fork to avoid premature termination of the process.  The
        # reason is that when the first child terminates, all processes, e.g.
        # the second child, in the orphaned group will be sent a SIGHUP.
        #
        # "However, as part of the session management system, there are exactly
        # two cases where SIGHUP is sent on the death of a process:
        #
        # 1) When the process that dies is the session leader of a session that
        #      is attached to a terminal device, SIGHUP is sent to all processes
        #      in the foreground process group of that terminal device.
        # 2) When the death of a process causes a process group to become
        #      orphaned, and one or more processes in the orphaned group are
        #      stopped, then SIGHUP and SIGCONT are sent to all members of the
        #      orphaned group." [2]
        #
        # The first case can be ignored since the child is guaranteed not to
        # have a controlling terminal. The second case isn't so easy to
        # dismiss.
        # The process group is orphaned when the first child terminates and
        # POSIX.1 requires that every STOPPED process in an orphaned process
        # group be sent a SIGHUP signal followed by a SIGCONT signal.  Since the
        # second child is not STOPPED though, we can safely forego ignoring the
        # SIGHUP signal. In any case, there are no ill-effects if it is ignored.
        #
        import signal           # Set handlers for asynchronous events.
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

        # Fork a second child and exit immediately to prevent zombies.  This
        # causes the second child process to be orphaned, making the init
        # process responsible for its cleanup. And, since the first child is
        # a session leader without a controlling terminal, it's possible for
        # it to acquire one by opening a terminal in the future (System V-
        # based systems).  This second fork guarantees that the child is no
        # longer a session leader, preventing the daemon from ever acquiring
        # a controlling terminal.
        pid = os.fork()    # Fork a second child.

        if pid == 0:    # The second child.
            # Since the current working directory may be a mounted filesystem,
            # we avoid the issue of not being able to unmount the filesystem at
            # shutdown time by changing it to the root directory.
            logger.debug("Change working directory to: %s", workdir)
            os.chdir(workdir)

            # We probably don't want the file mode creation mask inherited from
            # the parent, so we give the child complete control over
            # permissions.
            os.umask(umask)

        else:
            # exit() or _exit()?  See below.
            os._exit(0)    # Exit parent (the first child) of the second child.
    else:
        # exit() or _exit()?
        # _exit is like exit(), but it doesn't call any functions registered
        # with atexit (and on_exit) or any registered signal handlers.  It also
        # closes any open file descriptors.  Using exit() may cause all stdio
        # streams to be flushed twice and any temporary files may be
        # unexpectedly removed.  It's therefore recommended that child branches
        # of a fork() and the parent branch(es) of a daemon use _exit().
        os._exit(0)    # Exit parent of the first child.

    # Close all open file descriptors.  This prevents the child from keeping
    # open any file descriptors inherited from the parent.  There is a variety
    # of methods to accomplish this task.  Three are listed below.
    #
    # Try the system configuration variable, SC_OPEN_MAX, to obtain the maximum
    # number of open file descriptors to close.  If it doesn't exists, use
    # the default value (configurable).
    #
    # try:
    #    maxfd = os.sysconf("SC_OPEN_MAX")
    # except (AttributeError, ValueError):
    #    maxfd = MAXFD
    #
    # OR
    #
    # if (os.sysconf_names.has_key("SC_OPEN_MAX")):
    #    maxfd = os.sysconf("SC_OPEN_MAX")
    # else:
    #    maxfd = MAXFD
    #
    # OR
    #
    # Use the getrlimit method to retrieve the maximum file descriptor number
    # that can be opened by this process.  If there is not limit on the
    # resource, use the default value.
    #
    import resource  # Resource usage information.

    if maxfd is None:
        soft_fd_limit, hard_fd_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
        if hard_fd_limit != resource.RLIM_INFINITY:
            maxfd = hard_fd_limit
        else:
            maxfd = MAXFD

    # Iterate through and close all file descriptors.
    for fd in range(0, maxfd):
        try:
            os.close(fd)
        except OSError:    # ERROR, fd wasn't open to begin with (ignored)
            pass

    # Redirect the standard I/O file descriptors to the specified file.  Since
    # the daemon has no controlling terminal, most daemons redirect stdin,
    # stdout, and stderr to /dev/null.  This is done to prevent side-effects
    # from reads and writes to the standard I/O file descriptors.

    # This call to open is guaranteed to return the lowest file descriptor,
    # which will be 0 (stdin), since it was closed above.
    os.open(redirect_to, os.O_RDWR)    # standard input (0)

    # Duplicate standard input to standard output and standard error.
    os.dup2(0, 1)            # standard output (1)
    os.dup2(0, 2)            # standard error (2)

    return 0
