#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only audit of saved full-vocabulary F32 logits; no model execution."""
from pathlib import Path
import hashlib,importlib.util,json
import numpy as np


def main():
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('hc_analysis',root/'tools/analyze-q2-hc.py');hc=importlib.util.module_from_spec(spec);spec.loader.exec_module(hc)
    reference,_,meta=hc.read(root/'evidence/q2-explore-reference-r1','MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
    report={'analysis_source':'tools/analyze-q2-logits.py','analysis_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'Offline saved-logit audit only; no new inference or independent teacher. An additive logit offset cancels under softmax, but remaining probability differences are real. No thresholds or qualification verdicts change.','reference':meta,'arms':{}}
    for label in ['q2-hc-prefill-model-wmma-r1','q2-stack-model-r1','q2-iq2-pair-model-r1']:
     candidate,_,candidate_meta=hc.read(root/'evidence'/label,'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT');rows=[]
     for path in sorted(candidate.glob('*.f32')):
      ref=reference/path.name
      a=np.frombuffer(ref.read_bytes(),dtype='<f4').astype(np.float64);b=np.frombuffer(path.read_bytes(),dtype='<f4').astype(np.float64)
      assert a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all()
      d=b-a;offset=float(d.mean());raw=float(np.sqrt(np.mean(d*d)));residual=d-offset
      def log_softmax(v):
       v=v-v.max();return v-np.log(np.exp(v).sum())
      lp,lq=log_softmax(a),log_softmax(b);p,q=np.exp(lp),np.exp(lq)
      assert abs(p.sum()-1)<1e-12 and abs(q.sum()-1)<1e-12
      pa,qa=np.argsort(a)[::-1],np.argsort(b)[::-1];worst=int(np.argmax(abs(q-p)))
      rows.append({'name':path.name,'elements':a.size,'reference_sha256':hashlib.sha256(ref.read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'mean_logit_offset':offset,'raw_rmse':raw,'centered_rmse':float(np.sqrt(np.mean(residual*residual))),'constant_offset_fraction_of_squared_error':offset*offset/(raw*raw) if raw else 0.0,'maximum_absolute_logit_delta':float(abs(d).max()),'maximum_absolute_centered_delta':float(abs(residual).max()),'kl_reference_to_candidate':float(np.dot(p,lp-lq)),'total_variation':float(abs(q-p).sum()/2),'largest_probability_delta':float(abs(q-p).max()),'largest_probability_delta_token':worst,'reference_probability_at_largest_delta':float(p[worst]),'candidate_probability_at_largest_delta':float(q[worst]),'reference_argmax':int(pa[0]),'candidate_argmax':int(qa[0]),'reference_top1_probability':float(p[pa[0]]),'candidate_top1_probability':float(q[qa[0]]),'reference_top1_logit_margin':float(a[pa[0]]-a[pa[1]]),'candidate_top1_logit_margin':float(b[qa[0]]-b[qa[1]]),'topk_intersections':{str(k):len(set(pa[:k])&set(qa[:k])) for k in [5,10,100]}})
     report['arms'][label]={'meta':candidate_meta,'frontiers':rows}
    (root/'config/q2-logit-shift-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    for label,arm in report['arms'].items():
     print(label)
     for r in arm['frontiers']:
      if r['name'].startswith('pp2048-') and not r['name'].startswith('pp2048-0-'):continue
      print(json.dumps({k:r[k] for k in ['name','mean_logit_offset','raw_rmse','centered_rmse','constant_offset_fraction_of_squared_error','kl_reference_to_candidate','total_variation','largest_probability_delta','reference_top1_probability','candidate_top1_probability']}))


if __name__ == "__main__":
    main()
