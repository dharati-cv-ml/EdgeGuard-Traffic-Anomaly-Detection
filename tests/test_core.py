import csv,tempfile,unittest
from pathlib import Path
from edgeguard.core import *
DATA=Path(__file__).resolve().parents[1]/'data'/'sample.csv'
class EdgeGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rows=load_csv(DATA);cls.model=train(cls.rows)
    def test_dataset_size(self):self.assertEqual(len(self.rows),400)
    def test_model_train(self):self.assertEqual(self.model['training_size'],400)
    def test_predictions(self):
        out=predict(self.model,self.rows);self.assertEqual(len(out),400)
        self.assertTrue(set(x['prediction'] for x in out)<={'NORMAL','REVIEW'})
    def test_metrics(self):self.assertEqual(metrics(predict(self.model,self.rows))['labeled_count'],400)
    def test_serialization(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'model.json';save_model(self.model,f);self.assertEqual(self.model,load_model(f))
    def test_export(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'out.csv';export_predictions(predict(self.model,self.rows),f);self.assertEqual(len(f.read_text().splitlines()),401)
    def test_invalid_contamination(self):
        with self.assertRaises(ValueError):train(self.rows,0.8)
    def test_invalid_missing_column(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'bad.csv';f.write_text('a,b\n1,2\n')
            with self.assertRaises(ValueError):load_csv(f)
    def test_score_nonnegative(self):self.assertTrue(all(score(self.model,r)>=0 for r in self.rows))
    def test_small_dataset(self):
        with self.assertRaises(ValueError):train(self.rows[:8])
if __name__=='__main__':unittest.main()
