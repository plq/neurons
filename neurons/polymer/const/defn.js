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
        submitStatus: {
            type: String,
            notify: true
        },
        submitError: {}
    }
    ,listeners: {
      'iron-form-presubmit': '_presubmit',
      'iron-form-element-register': '_register_element'
    }
    ,created: function() {
        this._elements = {};
        this._parameters = {};
    }
    ,attached: function() {
        var children = this.getEffectiveChildren();

        // remove parameters from local dom
        var this_dom = Polymer.dom(this);
        for (var i = 0, l = children.length; i < l; ++i) {
            this_dom.removeChild(children[i]);
        }

        // parse parameters
        this._parameters = neurons.xml_to_jsobj(children);

        var getter = this.$.ajax_getter;
        getter.params = this._parameters;
        getter.generateRequest();

        for (var k in this._elements) {
            var elt = this._elements[k];
            if (window.console) console.log("Setting params on " + elt.getAttribute("name"));
            if (elt.getAttribute("need-parent-params")) {
                elt.params = this._parameters;
            }
        }

        var parent = this;
        this.$.form.addEventListener('change', function(event) {
            parent.$.form.disabled = !parent.$.form.validate();
        });
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

            if (elt.tagName.toLowerCase() == 'neurons-complex-dropdown') {
                elt.complexValue = resp[k];
            }
            else if (elt.tagName.toLowerCase() == 'neurons-array') {
                elt.complexValue = resp[k];
            }
            else if (elt.tagName.toLowerCase() == 'neurons-complex-href') {
                elt.complexValue = resp[k];
            }
            else {
                elt.value = resp[k];
            }
        }
    }
    ,_register_element: function(e) {
        var elt = Polymer.dom(e).rootTarget;
        this._elements[elt.getAttribute('name')] = elt;
    }
    ,_serialize: function(data, form_data, prefix) {
        for (var k in form_data) {
            var subval = form_data[k];
            if (neurons.isString(subval) || neurons.isNumber(subval)) {
                data[prefix + k] = subval;
            }
            else {
                this._serialize(data, subval, prefix + k + ".");
            }
        }
        return data;
    }
    ,_presubmit: function(e) {
        e.preventDefault();
        this.submitStatus = "submit-waiting";
        this.submitError = '';

        var form_data = this.$.form.serialize();
        for (var k in this._elements) {
            var elt = this._elements[k];
            if (elt.tagName.toLowerCase() == 'neurons-complex-reference') {
                form_data[k] = {};
                form_data[k][elt.attr_item_value] =
                                          elt.complexValue[elt.attr_item_value];
            }
        }

        var params = this._serialize({}, form_data, 'self.');
        for (var k in this._parameters) {
            params[k] = this._parameters[k];
        }

        var putter = this.$.ajax_putter;
        putter.params = params;
        putter.generateRequest();
    }
    ,_process_putter_response: function(e) {
        var resp = e.detail.response;
        this.submitStatus = "submit-success";
        this.submitError = '';
    }
    ,_process_putter_error: function(e) {
        var req = e.detail.request;
        this.submitStatus = "submit-failure";

        // FIXME: Make these locale-aware
        if (req.status == 0) {
            this.submitError = "Communication error, please try again";
        }
        else {
            this.submitError = "Error " + req.status + ": " + req.statusText;
        }
    }
    ,_effectiveParams: function(params) {
        var retval = neurons.clone(params);
        if (this.paramWhitelist && this.paramWhitelist.length > 0) {
            for (k in retval) {
                if (! this._contains(this.paramWhitelist, k)) {
                    delete retval[k];
                }
            }
        }
        return retval;
    }
    ,_urlencodeParams: function(elt_id, method_name) {
        var params = this._effectiveParams(this._parameters);
        var pam = this.$[elt_id].argMap[method_name];
        for (var k in pam) {
            var v = pam[k];
            if (v !== null) {
                params[v] = params[k];
            }
            delete params[k];
        }
        return neurons.urlencode(params);
    }
});
