import argparse,json
from pathlib import Path
from .core import load_csv,train,predict,metrics,save_model,load_model,export_predictions

def main(argv=None):
    p=argparse.ArgumentParser(description='EdgeGuard offline command line')
    sub=p.add_subparsers(dest='command',required=True)
    t=sub.add_parser('train');t.add_argument('--input',required=True);t.add_argument('--model',required=True)
    t.add_argument('--contamination',type=float,default=.08)
    e=sub.add_parser('evaluate');e.add_argument('--input',required=True);e.add_argument('--model',required=True)
    e.add_argument('--output',required=True);e.add_argument('--csv')
    a=p.parse_args(argv)
    if a.command=='train':
        m=train(load_csv(a.input),a.contamination);save_model(m,a.model)
        print(json.dumps({'model':a.model,'rows':m['training_size'],'threshold':m['threshold']},indent=2))
    else:
        rows=predict(load_model(a.model),load_csv(a.input)); result=metrics(rows)
        Path(a.output).parent.mkdir(parents=True,exist_ok=True)
        Path(a.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
        if a.csv:export_predictions(rows,a.csv)
        print(json.dumps(result,indent=2))
if __name__=='__main__':main()
