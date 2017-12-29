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


import logging
logger = logging.getLogger(__name__)

from time import time
from inspect import isclass

from twisted.internet.defer import Deferred


def _get_out_object(ctx):
    """Returns out object from context

    :param om: out_message
    :return: out_object
    """
    om = ctx.descriptor.out_message
    oo = None
    if ctx.descriptor.is_out_bare():
        oo = next(iter(ctx.out_object))

    else:  # om is a ComplexModelBase then.
        if len(om._type_info) == 0:
            oo, = ctx.out_object

        elif len(om._type_info) == 1:
            om, = om._type_info.values()
            oo, = ctx.out_object

        else:
            oo = om.get_serialization_instance(ctx.out_object)

    return oo


def t_log_method_return(LogEntry):
    def _on_method_return(ctx):
        if ctx.service_class is not None and ctx.service_class.is_auxiliary():
            return
        ctx.event.call_end = time()

        log_entry = LogEntry()

        omc = None
        if ctx.descriptor.is_out_bare():
            omc = ctx.descriptor.out_message

        elif len(ctx.descriptor.out_message._type_info) == 1:
            omc, = ctx.descriptor.out_message._type_info.values()

        if isclass(omc) and issubclass(omc, Integer) and \
                               isinstance(ctx.out_object[0], six.integer_types):
            log_entry.data_out_int = next(iter(ctx.out_object))

        if ctx.udc.no_persistent_log:
            logger.debug("not logging %r", ctx.descriptor.key)
            ctx.udc.log_entry = None

        else:
            oo = _get_out_object(ctx)
            ctx.udc.log_entry = log_entry

            def _log(ret, ctx, log_entry):
                from twisted.internet.threads import deferToThread
                return deferToThread(_fill_log, ctx, log_entry) \
                    .addCallbacks(lambda _: ret, lambda err: logging.exception(err.value))


            if isinstance(oo, Deferred):
                oo.addCallback(_log, ctx, log_entry)
                oo.addErrback(_log, ctx, log_entry)

            else:
                _log(None, ctx, log_entry)

    return _on_method_return


def _t_log_method_exception(_LogEntry):
    def _on_method_exception(ctx):
        logger.debug("Running arskom.web.base.on_method_exception() "
                                                                  "for logging")

        sc = ctx.service_class
        if sc is not None and sc.is_auxiliary():
            return

        ctx.event.call_end = time()

        logger.debug("logging method exception for %r" %
                                                      ctx.method_request_string)

        log_entry = _LogEntry()
        log_entry.ro = True

        try:
            out_data = ''.join(ctx.out_string)
        except:
            out_data = None
        else:
            # ctx.out_string generator ise az once kendisini tukettik. bari
            # tukettigimiz veriyi yerine koyalim ki bizden sonrakiler
            # kullanabilsin. degil idiyse de zarari yok bir suru stringi tek
            # string olarak birlestirdik.
            ctx.out_string = (out_data,)

        _fill_log(ctx, log_entry, 1, out_data)

    return _on_method_exception
