import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.add import add

def test_add_simple():
    assert add(2, 3) == 5
