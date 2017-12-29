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

import json
import threading

from slimit.ast import Identifier, Node, Assign, VarDecl
from slimit.parser import Parser

parser_store = threading.local()


def get_js_parser():
    parser = getattr(parser_store, 'parser', None)

    if parser is not None:
        return parser

    parser = parser_store.parser = Parser()

    return parser


def set_js_variable(tree, name, val):
    children = tree.children()

    if len(children) == 0:
        return

    c0 = children[0]
    if isinstance(tree, Assign) or isinstance(tree, VarDecl):
        if isinstance(c0, Identifier):
            if c0.value == name:
                valstr = "foo = {}".format(json.dumps(val))
                valast_root = get_js_parser().parse(valstr)
                valast = valast_root.children()[0].children()[0].children()[1]

                if isinstance(tree, VarDecl):
                    tree.initializer = valast

                elif isinstance(tree, Assign):
                    tree.right = valast

    for c in children:
        if isinstance(c, Node):
            set_js_variable(c, name, val)

    return tree
