"""Feature validation and robust-statistical anomaly detection. No external packages."""
import csv, json, math, statistics
from pathlib import Path

FEATURES = ('requests_per_min', 'error_rate', 'avg_response_ms', 'bytes_out_kb', 'unique_paths')
FIELDS = ('timestamp', 'client_id', *FEATURES, 'label')

def load_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        missing = set(FEATURES) - set(reader.fieldnames or [])
        if missing:
            raise ValueError('Missing columns: ' + ', '.join(sorted(missing)))
        rows = []
        for line, row in enumerate(reader, 2):
            try:
                vals = {k: float(row[k]) for k in FEATURES}
                if any(not math.isfinite(v) or v < 0 for v in vals.values()):
                    raise ValueError('non-finite or negative feature')
                if vals['error_rate'] > 1:
                    raise ValueError('error_rate must be between 0 and 1')
                rows.append({**row, **vals})
            except (TypeError, ValueError) as exc:
                raise ValueError(f'Row {line}: {exc}') from exc
    if not rows:
        raise ValueError('CSV is empty')
    return rows

def _percentile(values, pct):
    s = sorted(values)
    pos = (len(s) - 1) * pct
    lo = int(pos)
    return s[lo] + (s[min(len(s)-1,lo+1)]-s[lo])*(pos-lo)

def train(rows, contamination=0.08):
    if not 0 < contamination < 0.5:
        raise ValueError('contamination must be in (0, 0.5)')
    if len(rows) < 20:
        raise ValueError('At least 20 records required')
    centers = {}; scales = {}
    for key in FEATURES:
        nums = [float(r[key]) for r in rows]
        med = statistics.median(nums)
        mad = statistics.median(abs(v-med) for v in nums)
        centers[key] = med
        scales[key] = max(1.4826*mad, abs(med)*0.02, 1e-6)
    provisional = {'algorithm':'robust_log_deviation_v1','centers':centers,'scales':scales}
    training_scores = [score(provisional,r) for r in rows]
    threshold = _percentile(training_scores, 1-contamination)
    return {**provisional,'threshold':threshold,'contamination':contamination,'training_size':len(rows),'features':list(FEATURES)}

def score(model, row):
    # Weighted robust deviations; error rate is intentionally emphasized.
    weights = {'requests_per_min':1.2,'error_rate':1.8,'avg_response_ms':0.7,'bytes_out_kb':1,'unique_paths':1.2}
    vals=[]
    for k in FEATURES:
        deviation = abs(float(row[k])-model['centers'][k])/model['scales'][k]
        vals.append(weights[k]*math.log1p(deviation))
    return round(sum(vals)/sum(weights.values()),6)

def predict(model, rows):
    out=[]
    for r in rows:
        s=score(model,r)
        out.append({**r,'anomaly_score':s,'prediction':'REVIEW' if s > model['threshold'] else 'NORMAL'})
    return out

def metrics(predictions):
    matrix={'TP':0,'FP':0,'TN':0,'FN':0}
    for r in predictions:
        true=str(r.get('label','')).strip().lower()
        if true not in ('normal','anomaly'):
            continue
        flag=r['prediction']=='REVIEW'; bad=true=='anomaly'
        matrix['TP' if flag and bad else 'FP' if flag else 'FN' if bad else 'TN'] += 1
    tp,fp,tn,fn=(matrix[k] for k in ('TP','FP','TN','FN'))
    total=tp+fp+tn+fn
    return {**matrix,'count':len(predictions), 'labeled_count':total,
            'review_count':sum(r['prediction']=='REVIEW' for r in predictions),
            'precision':round(tp/(tp+fp),4) if tp+fp else None,
            'recall':round(tp/(tp+fn),4) if tp+fn else None,
            'false_positive_rate':round(fp/(fp+tn),4) if fp+tn else None}

def save_model(model,path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(model,indent=2),encoding='utf-8')

def load_model(path):
    model=json.loads(Path(path).read_text(encoding='utf-8'))
    if model.get('algorithm')!='robust_log_deviation_v1' or not set(FEATURES).issubset(model.get('centers',{})):
        raise ValueError('Unsupported EdgeGuard model')
    return model

def export_predictions(predictions,path):
    if not predictions: raise ValueError('No predictions to export')
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for row in predictions for k in row))
    with open(path,'w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');writer.writeheader();writer.writerows(predictions)
