
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
    }
    ,process_getter_response: function(e) {
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
    ,process_putter_response: function(e) {
        var resp = e.detail.response;
        if (window.console) console.log(resp);
    }

});
