import unittest
from timer import Timer;

class TestTimer(unittest.TestCase):
    def setUp(self):
        pass

    def test_timer(self):
        t = Timer()
        id = t.start();
        id1 = t.start();
        print("wheeeeee")
        t.end(id, "mooo")
        t.end(id1, "fooo")
        t.finish()

if __name__ == '__main__':
    unittest.main()
