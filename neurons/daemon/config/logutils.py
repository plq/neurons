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


from __future__ import print_function

import logging
logger = logging.getLogger(__name__)

import os
import sys
import gzip
import shutil
import neurons

from time import time
from pprint import pformat
from datetime import date

from spyne import ComplexModel
from spyne import Unicode
from spyne.util import six
from spyne.util.color import R, B, YEL, DARK_R, DARK_G


LOGLEVEL_MAP = dict(zip(
    ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
    [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR,
                                                               logging.CRITICAL]
))

LOGLEVEL_STR_MAP = {v: k for k, v in LOGLEVEL_MAP.items()}

LOGLEVEL_MAP_ABB = {
    logging.DEBUG: 'D',
    logging.INFO: B('I'),
    logging.WARNING: YEL('W'),
    logging.ERROR: R('E'),
    logging.CRITICAL: DARK_R('C'),
}


def _get_reactor_thread_sigil(record):
    if neurons.REACTOR_THREAD_ID is None:
        return ' '

    if record.thread == neurons.REACTOR_THREAD_ID:
        return DARK_R('R')

    return DARK_G('P')


class Logger(ComplexModel):
    path = Unicode
    level = Unicode(values=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])

    def __init__(self, *args, **kwargs):
        self._parent = None

        super(Logger, self).__init__(*args, **kwargs)

    def set_parent(self, parent):
        assert parent is not None
        self._parent = parent

    def apply(self):
        if self.path in (None, '', '.'):
            _logger = logging.getLogger()
        else:
            _logger = logging.getLogger(self.path)

        _logger.setLevel(LOGLEVEL_MAP[self.level])

        if self.path == '.':
            self._parent.boot_message()
            logger.info("Root logger level override: %s", self.level)
        else:
            logger.info("Logger level override %s = %s", self.path, self.level)

        return self


def TTwistedHandler(config, loggers, _meminfo):
    from twisted.logger import LogLevel

    # this is supposed to override the Logger object above. that's not cool but
    # that's the way it has to be
    from twisted.logger import Logger

    LOGLEVEL_TWISTED_MAP = {
        logging.DEBUG: LogLevel.debug,
        logging.INFO: LogLevel.info,
        logging.WARN: LogLevel.warn,
        logging.ERROR: LogLevel.error,
        logging.CRITICAL: LogLevel.critical,
    }

    class TwistedHandler(logging.Handler):
        if config.log_rss:
            if _meminfo is None:
                @staticmethod
                def _modify_record(record):
                    record.msg = '[psutil?] %s' % record.msg
            else:
                @staticmethod
                def _modify_record(record):
                    meminfo = _meminfo()
                    record.msg = '[%.2f] %s' % \
                                         (meminfo.rss / 1024.0 ** 2, record.msg)

        else:
            def _modify_record(self, record):
                pass

        def emit(self, record):
            assert isinstance(record, logging.LogRecord)

            record.l = LOGLEVEL_MAP_ABB.get(record.levelno, "?")
            record.r = _get_reactor_thread_sigil(record)

            self._modify_record(record)

            _logger = loggers.get(record.name, None)
            if _logger is None:
                _logger = loggers[record.name] = Logger(record.name)

            if six.PY2 and hasattr(record, 'msg') \
                                                and isinstance(record.msg, str):
                record.msg = record.msg.decode('utf8')

            t = self.format(record)

            if six.PY2 and isinstance(t, str):
                t = t.decode('utf8', errors='replace')

            _logger.emit(LOGLEVEL_TWISTED_MAP[record.levelno], log_text=t)

    return TwistedHandler


def TDynamicallyRotatedLog(config, comp_method):
    from twisted.python.logfile import DailyLogFile

    class DynamicallyRotatedLog(DailyLogFile):
        def suffix(self, tupledate):
            # this just adds leading zeroes to dates. it's otherwise
            # same with parent
            try:
                return '-'.join(("%02d" % i for i in tupledate))
            except:
                # try taking a float unixtime
                return '-'.join(("%02d" % i for i in
                    self.toDate(tupledate)))

        def write(self, data):
            if isinstance(data, six.text_type):
                data = data.encode('utf8')

            DailyLogFile.write(self, data)

        if comp_method == 'gzip':
            def compress_rotated_file(self, file_name):
                start = time()
                target_file_name = '{}.gz'.format(file_name)

                with open(file_name, 'rb') as f_in, \
                    gzip.open(target_file_name, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

                os.unlink(file_name)

                logger.info(
                    "Rotated log file '%s' => '%s', took %f seconds.",
                    file_name, target_file_name, time() - start)
        else:
            def compress_rotated_file(self, file_name):
                pass

        def rotate(self):
            """Rotate the file and create a new one.

            If it's not possible to open new logfile, this will fail
            silently, and continue logging to old logfile.
            """

            # copied from base class and modified with call to
            # compress_rotated_file

            if not (os.access(self.directory, os.W_OK) and os.access(
                self.path, os.W_OK)):
                return

            newpath = "%s.%s" % (self.path, self.suffix(self.lastDate))

            if os.path.exists(newpath):
                newpath_tmpl = "%s_{}" % newpath
                i = 0
                while os.path.exists(newpath):
                    i += 1

                    newpath = newpath_tmpl.format(i)

            self._file.close()

            os.rename(self.path, newpath)
            self._openFile()

            if 'twisted' in sys.modules:
                from twisted.internet.threads import deferToThread

                deferToThread(self.compress_rotated_file, newpath) \
                    .addErrback(lambda err:
                                         logger.error("%s", err.getTraceback()))

            else:
                self.compress_rotated_file(newpath)

        if config.logger_dest_rotation_period == "DAILY":
            def shouldRotate(self):
                return self.toDate() != self.lastDate

        elif config.logger_dest_rotation_period == "WEEKLY":
            def shouldRotate(self):
                today = date(*self.toDate())
                last = date(*self.lastDate)
                return (today.year != last.year or
                        today.isocalendar()[1] != last.isocalendar()[1])

        elif config.logger_dest_rotation_period == "MONTHLY":
            def shouldRotate(self):
                return self.toDate()[:2] != self.lastDate[:2]

        else:
            def shouldRotate(self):
                logger.warning("Invalid logger_dest_rotation_period value %r",
                                             config.logger_dest_rotation_period)
                return False

    return DynamicallyRotatedLog


def Trecord_as_string(formatter):
    from twisted.logger import LogLevel

    LOGLEVEL_TWISTED_MAP = {
        logging.DEBUG: LogLevel.debug,
        logging.INFO: LogLevel.info,
        logging.WARN: LogLevel.warn,
        logging.ERROR: LogLevel.error,
        logging.CRITICAL: LogLevel.critical,
    }

    TWISTED_LOGLEVEL_MAP = {v: k for k, v in LOGLEVEL_TWISTED_MAP.items()}

    def record_as_string(record):
        if 'log_failure' in record:
            failure = record['log_failure']
            try:
                s = pformat(vars(failure.value))
            except TypeError:
                # vars() argument must have __dict__ attribute
                s = repr(failure.value)
            return "%s: %s" % (failure.type, s)

        if 'log_text' in record:
            return record['log_text'] + "\n"

        if 'log_format' in record:
            level = record.get('log_level', LogLevel.debug)
            level = LOGLEVEL_MAP_ABB[TWISTED_LOGLEVEL_MAP[level]]

            text = record['log_format'].format(**record) + "\n"
            ns = record.get('log_namespace', "???")
            lineno = 0
            record = logging.LogRecord('?', level, ns, lineno, text,
                None, None)
            record.l = level
            record.r = _get_reactor_thread_sigil(record)
            record.module = ns.split('.')[-2]

            return formatter.format(record)

        if 'log_io' in record:
            return record['log_io'] + "\n"

        if 'message' in record:
            return record['message'] + "\n"

        return pformat(record)

    return record_as_string
