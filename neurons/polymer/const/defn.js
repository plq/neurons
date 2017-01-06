/*
 * This file is part of the Neurons project.
 * Copyright (c), Arskom Ltd. (arskom.com.tr),
 *                Burak Arslan <burak.arslan@arskom.com.tr>.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * * Redistributions of source code must retain the above copyright notice, this
 *   list of conditions and the following disclaimer.
 *
 * * Redistributions in binary form must reproduce the above copyright notice,
 *   this list of conditions and the following disclaimer in the documentation
 *   and/or other materials provided with the distribution.
 *
 * * Neither the name of the Arskom Ltd. nor the names of its
 *   contributors may be used to endorse or promote products derived from
 *   this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

Polymer({is: "blabla"
    ,properties: {

    }
    ,listeners: {
      'iron-form-presubmit': '_presubmit',
      'iron-form-element-register': '_register_element',
    }
    ,created: function() {
        this._elements = {};
        this._parameters = {};
    }
    ,attached: function() {
        var children = this.getEffectiveChildren();
        this._parameters = neurons.xml_to_jsobj(children);
        var getter = this.$.ajax_getter;
        getter.params = this._parameters;
        getter.generateRequest();

        for (var k in this._elements) {
            var elt = this._elements[k];
            if (elt.getAttribute("need-parent-params")) {
                elt.params = this._parameters;
            }
        }
    }
    ,_process_getter_response: function(e) {
        var resp = e.detail.response;
        var form = this.$.form;

        for (var k in resp) {
            var elt = this._elements[k];
            if (! elt) {
                if (window.console) console.log("Skipping " + k +
                                                      " -- element not found.");
                continue;
            }

            elt.value = resp[k];
        }
    }
    ,_register_element: function(e) {
        var elt = Polymer.dom(e).rootTarget;
        this._elements[elt.getAttribute('name')] = elt;
    }
    ,_presubmit: function(e) {
        e.preventDefault();

        var form_data = this.$.form.serialize();

        var data = {};
        for (var k in form_data) {
            data["self." + k] = form_data[k];
        }
        for (var k in this._parameters) {
            data[k] = this._parameters[k];
        }

        var putter = this.$.ajax_putter;
        putter.params = data;
        putter.generateRequest();
    }
    ,_process_putter_response: function(e) {
        var resp = e.detail.response;
        if (window.console) console.log(resp);
    }

});
