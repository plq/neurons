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

var polymer_init_options = {};

// Setup Polymer options
window.Polymer = {
  dom: 'shadow',
  lazyRegister: true
};

// Load webcomponentsjs polyfill if browser does not support native Web Components
(function () {
  'use strict';

  var onload = function () {
    // For native Imports, manually fire WebComponentsReady so user code
    // can use the same code path for native and polyfill'd imports.
    if (!window.HTMLImports) {
      document.dispatchEvent(
              new CustomEvent('WebComponentsReady', {bubbles: true})
      );
    }
  };

  var webComponentsSupported = (
          'registerElement' in document &&
                           'import' in document.createElement('link') &&
                           'content' in document.createElement('template'));

  if (!webComponentsSupported) {
    var script = document.createElement('script');
    script.async = true;
    script.src = polymer_init_options.url_polyfill;
    script.onload = onload;
    document.head.appendChild(script);
  }
  else {
    onload();
  }
})();

// Load pre-caching Service Worker
if (polymer_init_options.url_service_worker) {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register(polymer_init_options.url_service_worker);
    });
  }
}
