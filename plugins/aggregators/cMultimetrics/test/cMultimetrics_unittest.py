import unittest
# import doctest


class LoadTest(unittest.TestCase):
    "Just tries to load the module"

    def runTest(self):
        try:
            import cMultimetrics
        except ImportError as exc:
            self.fail(str(exc))


class InitTest(unittest.TestCase):
    "Tries to create object of cMultimetrics class"

    def runTest(self):
        try:
            import cMultimetrics
            cmm = cMultimetrics.cMultimetrics({})
            self.assertIsNotNone(cmm)

            # init rps test
            msg = lambda x: "str(%s) have not rps field" % str(x)
            cmm = cMultimetrics.cMultimetrics({"rps": False})
            self.assertIn("'rps': 0", str(cmm), msg(cmm))
            cmm = cMultimetrics.cMultimetrics({"rps": "no"})
            self.assertIn("'rps': 0", str(cmm), msg(cmm))
            cmm = cMultimetrics.cMultimetrics({"rps": "yes"})
            self.assertIn("'rps': 1", str(cmm), msg(cmm))

        except Exception as exc:
            self.fail(str(exc))
