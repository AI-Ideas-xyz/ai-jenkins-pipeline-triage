import sys
import unittest

sys.path.insert(0, ".")
from scripts.gen_eks_log import generate, SCENARIOS


class TestGenEksLog(unittest.TestCase):
    def test_all_scenarios_produce_non_empty_output(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                output = generate(scenario)
                self.assertIsInstance(output, str)
                self.assertGreater(len(output), 100)

    def test_crashloopbackoff_keywords(self):
        output = generate("CrashLoopBackOff")
        self.assertIn("CrashLoopBackOff", output)
        self.assertIn("kubectl", output)
        self.assertIn("BackOff", output)

    def test_oomkilled_keywords(self):
        output = generate("OOMKilled")
        self.assertIn("OOMKilled", output)
        self.assertIn("137", output)

    def test_imagepullbackoff_keywords(self):
        output = generate("ImagePullBackOff")
        self.assertIn("ImagePullBackOff", output)
        self.assertIn("401", output)

    def test_readinessprobefailed_keywords(self):
        output = generate("ReadinessProbeFailed")
        self.assertIn("Readiness", output)
        self.assertIn("503", output)

    def test_unknown_scenario_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate("NonExistentScenario")


if __name__ == "__main__":
    unittest.main()
