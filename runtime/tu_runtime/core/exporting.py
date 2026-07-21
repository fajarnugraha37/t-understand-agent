from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

import yaml

from .analysis import ID_RE
from .contracts import ContractValidator
from .discovery import _canonical_digest
from .documentation import DocumentationManager
from .errors import TUnderstandError
from .io import atomic_write_text, atomic_write_yaml, load_yaml, sha256_file, utc_now


PROFILES=("plain-markdown","github-markdown","mintlify-mdx","docusaurus-mdx","mkdocs-markdown")


class ExportManager:
    def __init__(self, project_root:Path, context_root:Path):
        self.project_root=project_root; self.context_root=context_root.resolve()
        self.documentation=DocumentationManager(project_root,context_root); self.contracts=ContractValidator(project_root)

    @property
    def root(self): return self.context_root/'documentation'/'exports'
    @property
    def reports_root(self): return self.context_root/'reports'/'exports'
    def _dir(self,export_id):
        if not ID_RE.fullmatch(export_id): raise TUnderstandError('EXP-ID-001','export_id must match canonical ID pattern')
        return self.root/export_id

    def create(self,export_id:str,docset_id:str,profile:str)->dict[str,Any]:
        if profile not in PROFILES: raise TUnderstandError('EXP-PROFILE-001',f'Unsupported export profile: {profile}')
        final=self._dir(export_id)
        if final.exists(): raise TUnderstandError('EXP-ID-002',f'Export already exists and is immutable: {export_id}')
        if self.documentation.validate(docset_id)['status']!='PASS': raise TUnderstandError('EXP-INPUT-001','Documentation validation failed')
        docset=self.documentation.show(docset_id); source=self.documentation._dir(docset_id)
        temp=self.root/f'.{export_id}.{uuid.uuid4().hex}.tmp'; temp.mkdir(parents=True)
        try:
            content=temp/'site'; content.mkdir()
            docs=[]
            for d in docset['documents']:
                src=source/d['path']; rel=Path(d['path']).relative_to('docs')
                if profile in {'mintlify-mdx','docusaurus-mdx'}: rel=rel.with_suffix('.mdx')
                dest=content/rel; dest.parent.mkdir(parents=True,exist_ok=True)
                text=src.read_text(encoding='utf-8')
                if profile=='github-markdown': text=self._github(text,rel)
                elif profile=='mintlify-mdx': text=self._mdx(text,'mintlify')
                elif profile=='docusaurus-mdx': text=self._mdx(text,'docusaurus')
                atomic_write_text(dest,text); docs.append((d,rel,dest))
            self._profile_files(content,profile,docset,docs)
            files=[]
            for p in sorted(x for x in content.rglob('*') if x.is_file()): files.append({'path':p.relative_to(temp).as_posix(),'sha256':sha256_file(p)})
            source_digest=_canonical_digest({'docset_id':docset_id,'manifest_sha256':sha256_file(source/'documentation-manifest.yaml'),'documents':[(d['path'],d['sha256']) for d in docset['documents']]})
            base={'schema_id':'https://t-understand.dev/schemas/export-manifest.schema.json','schema_version':'1.0.0','export_id':export_id,'docset_id':docset_id,'profile':profile,'status':'VALID','files':files,'source_digest':source_digest,'generated_at':utc_now()}
            manifest={**base,'content_digest':_canonical_digest(base)}; self.contracts.validate('export-manifest',manifest); atomic_write_yaml(temp/'export-manifest.yaml',manifest)
            os.replace(temp,final)
            report=self.validate(export_id)
            if report['status']!='PASS': raise TUnderstandError('EXP-VERIFY-001','Export validation failed')
        except Exception:
            shutil.rmtree(temp, ignore_errors=True)
            if final.exists():
                shutil.rmtree(final, ignore_errors=True)
            raise
        return self.show(export_id)

    @staticmethod
    def _github(text,rel):
        return text + f"\n---\n\n_Generated GitHub profile: `{rel.as_posix()}`._\n"
    @staticmethod
    def _mdx(text,kind):
        # canonical markdown is deliberately MDX-safe; only add a generated marker.
        return text + f"\n<!-- t-understand {kind} export; semantic content unchanged -->\n"

    def _profile_files(self,content,profile,docset,docs):
        pages=[rel.with_suffix('').as_posix() for _,rel,_ in docs]
        if profile=='plain-markdown':
            atomic_write_text(content/'SUMMARY.md','# Documentation\n\n'+'\n'.join(f'- [{d["document_id"]}]({rel.as_posix()})' for d,rel,_ in docs)+'\n')
        elif profile=='github-markdown':
            atomic_write_text(content/'README.md','# Documentation index\n\n'+'\n'.join(f'- [{d["document_id"]}]({rel.as_posix()})' for d,rel,_ in docs)+'\n')
        elif profile=='mintlify-mdx':
            nav=[]
            for group in load_yaml(self.documentation._dir(docset['docset_id'])/'information-architecture.yaml')['navigation']:
                nav.append({'group':group['group'],'pages':group['pages']})
            atomic_write_text(content/'docs.json',json.dumps({'$schema':'https://mintlify.com/docs.json','name':f"{docset['application_id']} Documentation",'theme':'mint','navigation':{'groups':nav}},indent=2)+'\n')
        elif profile=='docusaurus-mdx':
            tree={}
            for page in pages:
                group=page.split('/')[0] if '/' in page else 'overview'; tree.setdefault(group,[]).append(page)
            atomic_write_text(content/'sidebars.js','module.exports = '+json.dumps({'docs':[{'type':'category','label':k.title(),'items':v} for k,v in sorted(tree.items())]},indent=2)+';\n')
        elif profile=='mkdocs-markdown':
            nav=[]
            for d,rel,_ in docs: nav.append({d['document_id'].replace('-',' ').title():rel.as_posix()})
            atomic_write_yaml(content/'mkdocs.yml',{'site_name':f"{docset['application_id']} Documentation",'docs_dir':'.','nav':nav})

    def show(self,export_id): return load_yaml(self._dir(export_id)/'export-manifest.yaml')
    def list(self):
        vals=[]
        if self.root.exists():
            for p in sorted(self.root.iterdir()):
                if p.is_dir() and (p/'export-manifest.yaml').exists(): vals.append(self.show(p.name))
        return {'exports':vals}

    def validate(self,export_id):
        errors=[]; checks=0
        try:
            m=self.show(export_id); self.contracts.validate('export-manifest',m); checks+=1
            if _canonical_digest({k:v for k,v in m.items() if k!='content_digest'})!=m['content_digest']: errors.append('export manifest digest mismatch')
            root=self._dir(export_id)
            for f in m['files']:
                p=root/f['path']; checks+=1
                if not p.exists() or sha256_file(p)!=f['sha256']: errors.append(f"{f['path']} checksum mismatch")
                elif p.suffix in {'.md','.mdx'}:
                    errors.extend(f"{f['path']}: {x}" for x in self._validate_markdown(p))
            expected={'plain-markdown':'site/SUMMARY.md','github-markdown':'site/README.md','mintlify-mdx':'site/docs.json','docusaurus-mdx':'site/sidebars.js','mkdocs-markdown':'site/mkdocs.yml'}[m['profile']]
            if not (root/expected).exists(): errors.append(f'missing profile configuration {expected}')
            if m['profile']=='mintlify-mdx':
                json.loads((root/'site/docs.json').read_text()); checks+=1
            if m['profile']=='mkdocs-markdown':
                load_yaml(root/'site/mkdocs.yml'); checks+=1
        except Exception as exc: errors.append(str(exc))
        report={'schema_id':'https://t-understand.dev/schemas/render-validation.schema.json','schema_version':'1.0.0','id':export_id,'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors,'generated_at':utc_now()}
        self.contracts.validate('render-validation',report); atomic_write_yaml(self.reports_root/export_id/'render-validation.yaml',report); return report

    @staticmethod
    def _validate_markdown(path):
        text=path.read_text(encoding='utf-8'); errors=[]
        if text.count('```')%2: errors.append('unbalanced fenced code blocks')
        if text.startswith('---') and text.count('---')<2: errors.append('unclosed front matter')
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
            if target.startswith(('http://','https://','#','mailto:')): continue
            clean=target.split('#',1)[0]
            if clean and not (path.parent/clean).resolve().exists(): errors.append(f'broken relative link {target}')
        return errors
