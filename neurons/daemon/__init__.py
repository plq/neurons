
from neurons.daemon.config import parse_config

def main(daemon_name, argv, cls, init):
    daemon = parse_config(daemon_name, sys.argv, cls)
    daemon.apply()

    return 0
