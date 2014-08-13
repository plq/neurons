
from os.path import abspath
from os.path import isfile
from pkg_resources import resource_filename

_ROOT = __name__

T_TEST = abspath(resource_filename(_ROOT, 'test.xhtml'))
assert isfile(T_TEST)
