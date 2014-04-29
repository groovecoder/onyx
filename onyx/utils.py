import sys
import multiprocessing
import logging
from onyx.webapp import create_app, setup_routes
from flask.ext.script import Command, Option
from gunicorn.app.base import Application as GunicornApplication
from gunicorn.config import Config as GunicornConfig
from heka.config import client_from_dict_config

def setup_debug_logger(logger_name):
    """
    Setup a stdout logger for debug mode
    """
    fmt = logging.Formatter("HEKA: [%(asctime)-15s] %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def environment_manager_create(config=None):
    """
    Create and configure application
    """
    app = create_app(config)
    setup_routes(app)
    app.hekalog = client_from_dict_config(app.config['HEKA'])
    if app.config['DEBUG']:
        setup_debug_logger(app.config['HEKA']['logger'])
    return app

class GunicornServerCommand(Command):
    """
    Run the Onyx Server using gunicorn
    """
    def __init__(self, host='127.0.0.1', port=5000, workers=1, access_logfile='-', max_requests=0, debug=True):
        self.host = host
        self.port = port
        self.workers = workers
        self.access_logfile = access_logfile
        self.max_requests = max_requests
        self.debug = debug

    def get_options(self):
        options = (
            Option('-H', '--host', dest='host', type=str, default=self.host, help="hostname to bind server to"),
            Option('-p', '--port', dest='port', type=int, default=self.port, help="port to bind server to"),
            Option('-w', '--workers', dest='workers', type=int, default=self.workers, help="set the number of workers"),
            Option('--access-logfile', dest='access_logfile', type=str, default=self.access_logfile, help="set the access log output location"),
            Option('--max-requests', dest='max_requests', type=int, default=self.max_requests, help="set the maximum number of requests to serve before reloading"),
            Option('--no-debug', dest='debug', action='store_false', default=self.debug, help="turn off debug mode"),
        )
        return options

    def handle(self, app, host, port, workers, access_logfile, max_requests, debug):
        if not debug:
            workers = multiprocessing.cpu_count()
            max_requests = 0

        class GunicornServer(GunicornApplication):
            def init(self):
                config = {
                    'bind': '{0}:{1}'.format(host, port),
                    'workers': workers,
                    'worker_class': 'gevent',
                    'accesslog': access_logfile,
                    'max_requests': max_requests,
                }
                return config

            def load(self):
                return app

            def load_config(self):
                # Overriding to prevent Gunicorn from reading the command-line arguments
                self.cfg = GunicornConfig(self.usage, prog=self.prog)
                cfg = self.init()
                if cfg and cfg is not None:
                    for k, v in cfg.items():
                        self.cfg.set(k.lower(), v)

        GunicornServer().run()
