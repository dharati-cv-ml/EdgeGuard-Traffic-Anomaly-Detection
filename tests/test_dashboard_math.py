import unittest
from edgeguard.desktop import score_histogram, feature_deviations
from edgeguard.core import train, load_csv
from pathlib import Path

class DashboardLogicTests(unittest.TestCase):
    def test_histogram_counts(self):
        edges, counts = score_histogram([1, 2, 3, 4, 5], 3)
        self.assertEqual(sum(counts), 5)
        self.assertEqual(len(edges), 4)

    def test_identical_scores(self):
        _, counts = score_histogram([2, 2, 2])
        self.assertEqual(sum(counts), 3)

    def test_empty_histogram(self):
        self.assertEqual(score_histogram([]), ([], []))

    def test_bad_bins(self):
        with self.assertRaises(ValueError):
            score_histogram([1], 0)

    def test_feature_explanations(self):
        rows = load_csv(Path(__file__).resolve().parent.parent / 'data' / 'sample.csv')
        model = train(rows)
        deviations = feature_deviations(model, rows[0])
        self.assertEqual(len(deviations), 5)
        self.assertGreaterEqual(deviations[0][1], deviations[-1][1])

if __name__ == '__main__':
    unittest.main()
