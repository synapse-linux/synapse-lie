# SPDX-License-Identifier: MIT
"""Materialize the bounded state-view access variant; never edit pristine Gufo."""
import hashlib
import json
from pathlib import Path
import shutil

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def expected(root):
    manifest=json.loads((root/'third_party/gufo-source.json').read_text())
    path=root/'adapters/gufo-state/access-edits.json'
    edits=json.loads(path.read_text())
    if edits['source_pin']!='f783fedb9bea2ec7de941f6da4e02f4a4596b29e':
        raise ValueError('state access source pin mismatch')
    changed={}
    for edit in edits['edits']:
        name=edit['path'];source=root/'.deps/gufo-f783fedb'/name
        if name not in changed:
            if sha(source)!=manifest['files'][name]:raise ValueError('pristine source drift: '+name)
            changed[name]=source.read_text()
        if changed[name].count(edit['old'])!=1:raise ValueError('state access edit mismatch: '+name)
        changed[name]=changed[name].replace(edit['old'],edit['new'])
    files=dict(manifest['files'])
    for name,data in changed.items():files[name]=hashlib.sha256(data.encode()).hexdigest()
    return files,changed

def materialize(root,label):
    files,changed=expected(root);source=root/'.deps'/('gufo-state-access-'+label)
    source.mkdir()
    pristine=root/'.deps/gufo-f783fedb'
    manifest=json.loads((root/'third_party/gufo-source.json').read_text())
    for name,old in manifest['files'].items():
        p=pristine/name
        if p.is_symlink() or sha(p)!=old:raise ValueError('pristine source drift: '+name)
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        if name in changed:target.write_text(changed[name])
        else:shutil.copy2(p,target)
        if sha(target)!=files[name]:raise ValueError('materialization mismatch: '+name)
    return source,files
