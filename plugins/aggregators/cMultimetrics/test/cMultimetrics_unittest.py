import unittest
# import doctest


class LoadTest(unittest.TestCase):
    "Just tries to load the module"

    def runTest(self):
        try:
            import cMultimetrics  # NoQA
        except ImportError as exc:
            self.fail(str(exc))


class InitTest(unittest.TestCase):
    "Tries to create object of cMultimetrics class"

    def runTest(self):
        from cMultimetrics import cMultimetrics
        cmm = cMultimetrics({})
        self.assertIsNotNone(cmm)

        # init rps test
        self.assertIn("'rps': True", str(cMultimetrics({})))  # by default
        self.assertIn("'rps': False", str(cMultimetrics({"rps": False})))
        self.assertIn("'rps': False", str(cMultimetrics({"rps": "no"})))
        self.assertIn("'rps': True", str(cMultimetrics({"rps": "yes"})))
        self.assertRaises(TypeError, cMultimetrics, {"rps": tuple()})

        # init get_prc test
        self.assertIn("'get_prc': False", str(cMultimetrics({})))  # default
        self.assertIn("'get_prc': True", str(cMultimetrics({"get_prc": 1})))
        self.assertIn("'get_prc': False", str(cMultimetrics({"get_prc": "no"})))
        self.assertIn("'get_prc': True", str(cMultimetrics({"get_prc": "yes"})))
        self.assertRaises(TypeError, cMultimetrics, {"get_prc": dict()})

        # init timings_is
        self.assertRaises(TypeError, cMultimetrics, {"timings_is": int()})
        self.assertIn("'timings_is': 'my_custom_timings'",
                      str(cMultimetrics({"timings_is": "my_custom_timings"})))


        # init factor
        self.assertRaises(TypeError, cMultimetrics, {"factor": "2"})
        self.assertRaises(TypeError, cMultimetrics, {"factor": 2.0})
        self.assertIn("'factor': 1000", str(cMultimetrics({"factor": 1000})))
