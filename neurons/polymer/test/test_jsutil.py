
from neurons.jsutil import set_js_variable, get_js_parser


def test_set_js_variable():
    parser = get_js_parser()
    tree = parser.parse("var foo = 42;")
    aa = set_js_variable(tree, 'foo', {'bar': 12.34})
    print(aa)
    assert aa == """var foo = {
  "bar": 12.34
};"""
