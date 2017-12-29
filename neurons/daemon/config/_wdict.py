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


from spyne.util.odict import odict

from neurons.daemon.config import ServiceDisabled


class wdict(odict):
    def getwrite(self, key, *args):
        if len(args) > 0:
            if not key in self:
                self[key], = args
        return self[key]


class wrdict(wdict):
    def getwrite(self, key, *args):
        """Raises ServiceDisabled when the service has disabled == True"""

        retval = super(wrdict, self).getwrite(key, *args)

        if getattr(retval, 'disabled', None):
            raise ServiceDisabled(getattr(retval, 'name', "??"))

        return retval


def Twrdict(parent, keyattr=None):
    class twrdict(wrdict):
        if keyattr is not None:
            def __setitem__(self, key, value):
                super(wrdict, self).__setitem__(key, value)
                setattr(value, keyattr, key)
                value._parent = parent
        else:
            def __setitem__(self, key, value):
                super(wrdict, self).__setitem__(key, value)
                value._parent = parent

    return twrdict
