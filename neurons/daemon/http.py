
import logging
from spyne import Application
from spyne.server.wsgi import WsgiApplication
from spyne.util.wsgi_wrapper import WsgiMounter


def sync_root(apps, daemon):
    import twisted.web.server
    import twisted.web.static

    from twisted.web.resource import ForbiddenResource
    from twisted.python import log
    from twisted.internet import reactor
    from twisted.web.resource import Resource
    from twisted.web.wsgi import WSGIResource

    class StaticFile(twisted.web.static.File):
        def directoryListing(self):
            return ForbiddenResource()

    global log_repr
    from spyne.util.web import log_repr as l
    log_repr = l

    class WSGIRootResource(Resource):
        """Root resource when you want a WSGI resource be the default serving
        resource for a Twisted Web site, but have subpaths served by
        different resources.
        This is a hack needed since
        `twisted.web.wsgi.WSGIResource <http://twistedmatrix.com/documents/current/api/twisted.web.wsgi.WSGIResource.html>`_.
        does not provide a `putChild()` method.
        See also:
        * `Autobahn Twisted Web WSGI example <https://github.com/tavendo/AutobahnPython/tree/master/examples/websocket/echo_wsgi>`_
        * `Original hack <http://blog.vrplumber.com/index.php?/archives/2426-Making-your-Twisted-resources-a-url-sub-tree-of-your-WSGI-resource....html>`_
        """

        def __init__(self, wsgiResource, children):
            """Creates a Twisted Web root resource.

            :param wsgiResource:
            :type wsgiResource: Instance of `twisted.web.wsgi.WSGIResource <http://twistedmatrix.com/documents/current/api/twisted.web.wsgi.WSGIResource.html>`_.
            :param children: A dictionary with string keys constituting URL subpaths, and Twisted Web resources as values.
            :type children: dict
            """
            Resource.__init__(self)
            self._wsgiResource = wsgiResource
            self.children = children

        def getChild(self, path, request):
            return self._wsgiResource

    def _get_twisted_resource(key, app):
        if isinstance(app, Resource):
            app.prepath = key
            return app

        if isinstance(app, Static):
            return StaticFile(app.root_path)

        if isinstance(app, Application):
            app = WsgiApplication(app)

        if isinstance(app, (WsgiApplication, WsgiMounter)):
            return WSGIResource(reactor, reactor.getThreadPool(), app)

        raise Exception("%r ile ne yapacagimi bilemedim." % app)

    observer = log.PythonLoggingObserver()
    observer.start()

    _logger = logging.getLogger(daemon_name)

    root_app = dict(app_params['services']).get('', None)
    if root_app is None:
        if static_dir is None:
            root = Resource()
        else:
            _logger.info("registering static server %r on /",
                                                    os.path.abspath(static_dir))
            root = twisted.web.static.File(static_dir)
    else:
        root = _get_twisted_resource('', root_app)
        if isinstance(root, WSGIResource):
            root = WSGIRootResource(root, {})

    thread_pool = reactor.getThreadPool()
    thread_pool.adjustPoolsize(thread_min, thread_max)

    if len(app_params['services']) > 0:
        for url, app in app_params['services']:
            if url.find('/') > 0:
                raise Exception("'/' not allowed in urls")
            if url == '': # That's left as root path
                continue

            resource = _get_twisted_resource(url, app)

            _logger.info("registering %r on %r" % ( app, url ))
            root.putChild(url, resource)

        site = twisted.web.server.Site(root)

        reactor.listenTCP(port, site, interface=host)
        _logger.info("listening on: %s:%d" % (host, port))
    else:
        logger.info("Services dict is empty, skipping http site.")

    if before_run:
        before_run(daemon, app_params)

    return reactor.run()
