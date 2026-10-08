# SPDX-License-Identifier: MIT
import ast,contextlib,importlib.util,io,sys
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
spec=importlib.util.spec_from_file_location('remote',root/'tools/q2-remote.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rejected=0
for mode,variant,flags in [('compressed-cache-check','qualified',[]),('cpu','compressed-cache',[]),('q2-counting-compressed-cache','compressed-cache',[]),('q2-counting-ssm-fixed-bounds','compressed-cache',[])]+[('compressed-cache-check','compressed-cache',[f]) for f in ('--detach','--rebuild-mmq','--native-curve','--point-only')]:
 with patch.object(sys,'argv',['q2-remote.py',mode,'q2-compressed-cache-check-local','--source-variant',variant,*flags]),patch.object(Path,'mkdir',side_effect=AssertionError('Unwanted staging')),patch.object(m.subprocess,'run',side_effect=AssertionError('Unwanted child')),contextlib.redirect_stderr(io.StringIO()):
  try:m.main()
  except SystemExit as e:assert e.code==2;rejected+=1
  else:raise AssertionError('Accepted invalid launch')
for mode,flags in [('compressed-cache-check',[]),('q2-counting-compressed-cache',['--rebuild-mmq'])]:
 with patch.object(sys,'argv',['q2-remote.py',mode,'q2-compressed-cache-check-local','--source-variant','compressed-cache',*flags]),patch.object(Path,'mkdir',side_effect=RuntimeError('staging')),patch.object(m.subprocess,'run',side_effect=AssertionError('Unwanted child')):
  try:m.main()
  except RuntimeError as e:assert str(e)=='staging'
  else:raise AssertionError('Valid route failed to stage')
context={'mode':'compressed-cache-check','mixed_mode':False}
for node in ast.walk(ast.parse((root/'tools/q2-runner.py').read_text())):
 if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('hc_mode','hc_target','counting_mode'):
  context[node.targets[0].id]=eval(compile(ast.Expression(node.value),'<runner>','eval'),{},context)
assert context['hc_mode'] and context['hc_target']=='q2_compressed_cache' and not context['counting_mode']
print('Eight invalid routes rejected, two valid routes stage, component target isolated.')
