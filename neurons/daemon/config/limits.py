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

from __future__ import print_function, absolute_import

import logging
logger = logging.getLogger(__name__)

import os
import signal
import resource

from collections import namedtuple

from spyne import ComplexModel, Double, Integer32, UnsignedInteger32, M, Unicode
from spyne.util import memoize

RLimitEntry = namedtuple("RLimitEntry", "name unit type mult")


# Specifying stuff in bytes in config files could be inconvenient so we specify
# units and multipliers to make it easy to generate the config options
def _check_and_add_rlimit(name, unit, type, mult, **kwargs):
    aname = "RLIMIT_{}".format(name)
    if hasattr(resource, aname):
        RLIMIT_DICT[getattr(resource, aname)] = \
                                   RLimitEntry(name, unit, type(**kwargs), mult)


RLIMIT_DICT = {}


_check_and_add_rlimit("CORE", 'mb', Double, 2 ** 20,
    help="""The maximum size (in megabytes) of a core file that the current 
    process can create. This may result in the creation of a partial core file 
    if a larger core would be required to contain the entire process image.""")

_check_and_add_rlimit("CPU", 'h', Double, 3600,
    help="""The maximum amount of processor time (in hours) that a process can 
    use. If this limit is exceeded, a SIGXCPU signal is sent to the process.
    (See the signal module documentation for information about how to catch
    this signal and do something useful, e.g. flush open files to disk.)""")

_check_and_add_rlimit("FSIZE", 'mb', Double, 2 ** 20,
    help="""The maximum size (in bytes) of a file which the process may 
    create.""")

_check_and_add_rlimit("DATA", 'mb', Double, 2 ** 20,
    help="""The maximum size (in bytes) of the process’s heap.""")

_check_and_add_rlimit("STACK", 'mb', Double, 2 ** 20,
    help="""The maximum size (in bytes) of the call stack for the current 
    process. This only affects the stack of the main thread in a multi-threaded 
    process.""")

_check_and_add_rlimit("RSS", 'mb', Double, 2 ** 20,
    help="""The maximum resident set size that should be made available to the
    process.""")

_check_and_add_rlimit("NPROC", '', Integer32, 1,
    help="""The maximum number of processes the current process may create.""")

_check_and_add_rlimit("NOFILE", '', Integer32, 1,
    help="""The maximum number of open file descriptors for the current 
    process.""")

_check_and_add_rlimit("OFILE", '', Integer32, 1,
    help="""# The BSD name for RLIMIT_NOFILE.""")

_check_and_add_rlimit("MEMLOCK", 'mb', Double, 2 ** 20,
    help="""The maximum address space which may be locked in memory.""")

_check_and_add_rlimit("AS", 'mb', Double, 2 ** 20,
    help="""The maximum area (in bytes) of address space which may be taken by 
    the process.""")


class Limits(ComplexModel):
    _type_info = [
        ("{}_{}".format(v.name.lower(), v.unit), v.type(rlimit=k))
        if v.unit else
        (v.name.lower(), v.type(rlimit=k))

        for k, v in RLIMIT_DICT.items()
    ]

    def apply_limits_impl(self, limtype):
        for k, v in self.get_flat_type_info(self.__class__).items():
            val = getattr(self, k, None)
            if val is None:
                continue

            curr_rlimit = Limits._type_info[k].Attributes.rlimit
            oldlim = resource.getrlimit(curr_rlimit)

            newlim = list(oldlim)
            newlim[limtype] = int(val * 1024 ** 2)
            newlim = tuple(newlim)

            resource.setrlimit(curr_rlimit, newlim)
            logger.debug("RLIMIT_%s: was: %r now: %r", k, oldlim, newlim)


TIMED_ACTION_MAP = {
    'SIGTERM': lambda *_: os.kill(os.getpid(), signal.SIGTERM),
    'SIGKILL': lambda *_: os.kill(os.getpid(), signal.SIGKILL),
}


@memoize
def TTimedLimit(ValueType, rlimit):
    class TimedLimit(ComplexModel):
        __type_name__ = "Timed{}Limit".format(ValueType.get_type_name())

        _type_info = [
            ('value', M(ValueType)),
            ('action', M(Unicode(values=list(TIMED_ACTION_MAP.keys())))),
            ('period_s', UnsignedInteger32(default=60)),
            ('num_breaches', UnsignedInteger32(default=3)),
        ]

        def apply(self, name):
            logger.info("Enabling timed %s limit of %.1f %s "
                            "with period: %d seconds, num. breaches: %d",
                                  name, self.value, RLIMIT_DICT[rlimit].unit,
                                               self.period_s, self.num_breaches)
            return enforce_timed_limit(name, self, rlimit)

    return TimedLimit


class TimedLimits(ComplexModel):
    _type_info = [
        ("{}_{}".format(v.name.lower(), v.unit),
                      TTimedLimit(v.type, rlimit=k).customize(not_wrapped=True))

        if v.unit else

        (v.name.lower(),
                      TTimedLimit(v.type, rlimit=k).customize(not_wrapped=True))

        for k, v in RLIMIT_DICT.items()
    ]

    def apply(self):
        for k, v in self.get_flat_type_info(self.__class__).items():
            val = getattr(self, k, None)
            if val is None:
                continue

            val.apply(k)



class LimitsChoice(ComplexModel):
    _type_info = [
        ('soft', Limits.customize(not_wrapped=True)),
        ('hard', Limits.customize(not_wrapped=True)),
        ('timed', TimedLimits.customize(not_wrapped=True)),
    ]

    def apply(self):
        # Remember:
        #     soft, hard = resource.getrlimit(whatever)
        SOFT = 0
        HARD = 1

        if self.soft is not None:
            self.soft.apply(SOFT)

        if self.hard is not None:
            self.hard.apply(HARD)

        if self.timed is not None:
            self.timed.apply()


def enforce_timed_limit(name, limconf, rlimit):
    from twisted.internet.task import LoopingCall
    from twisted.internet.threads import deferToThread
    from neurons.daemon.config.daemon import meminfo

    status = [0]
    rlimit = RLIMIT_DICT[rlimit]
    assert isinstance(rlimit, RLimitEntry)
    callback = TIMED_ACTION_MAP[limconf.action]

    def _check():
        try:
            val = meminfo().rss

            if val < (limconf.value * rlimit.mult):
                if status[0] > 0:
                    logger.warning("%s limit went below treshold l: %.1f "
                              "c: %.1f", name, limconf.value, val / rlimit.mult)

                status[0] = 0
                return

            status[0] += 1

            if status[0] < limconf.num_breaches:
                logger.warning("%s limit reached, %d checks left "
                       "before taking %s action. s: %d l: %.1f c: %.1f",
                       name, (limconf.num_breaches - status[0]), limconf.action,
                                    status[0], limconf.value, val / rlimit.mult)
                return

            logger.warning("%s limit reached, performing %s. "
                           "s: %d l: %.1f c: %.1f", name, limconf.action,
                                    status[0], limconf.value, val / rlimit.mult)

            callback(limconf.value, limconf.period_s, limconf.num_breaches)

        except Exception as e:
            logger.error("Error in memory check job:")
            logger.exception(e)

    if meminfo is None:
        logger.warning("meminfo() not found! Please install psutil.")
        return

    if limconf.value is None:
        logger.warning("Timed limit %s is not set!", name)
        return

    if limconf.value <= 0:
        logger.warning("Timed limit %s is negative: %.1f", name, limconf.value)
        return

    logger.info("Starting %s timed check every %d second(s).", name,
                                                               limconf.period_s)
    lc = LoopingCall(deferToThread, _check)
    lc.start(limconf.period_s / 10)

    return lc
