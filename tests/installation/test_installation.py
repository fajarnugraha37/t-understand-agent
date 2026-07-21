from __future__ import annotations
import json,tempfile,unittest
from unittest import mock
from pathlib import Path
import yaml
from tu_runtime.core.installation import InstallationManager,PLATFORMS
ROOT=Path(__file__).resolve().parents[2]
class InstallationTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.context=self.base/'context';self.context.mkdir();self.m=InstallationManager(ROOT,self.context)
 def tearDown(self):self.tmp.cleanup()
 def test_all_platform_packages_validate(self):
  for i,p in enumerate(PLATFORMS):
   pid=f'INST-PKG-{i}';doc=self.m.package(pid,p);self.assertEqual(doc['platform'],p);self.assertEqual(self.m.validate_package(pid)['status'],'PASS')
 def test_install_doctor_idempotency_and_uninstall(self):
  self.m.package('INST-PKG-A','opencode');target=self.base/'tool-config';r=self.m.install('INST-A','INST-PKG-A',target);self.assertEqual(r['status'],'INSTALLED');self.assertEqual(self.m.doctor(target)['status'],'PASS');self.assertEqual(self.m.install('INST-A','INST-PKG-A',target)['install_id'],'INST-A');self.assertEqual(self.m.uninstall(target)['status'],'UNINSTALLED');self.assertFalse((target/'.t-understand-install').exists())
 def test_unmanaged_conflict_requires_force_and_is_restored(self):
  self.m.package('INST-PKG-B','cursor');target=self.base/'cursor';(target/'rules').mkdir(parents=True);existing=target/'rules/t-understand.mdc';existing.write_text('original')
  with self.assertRaises(Exception):self.m.install('INST-B','INST-PKG-B',target)
  self.m.install('INST-B','INST-PKG-B',target,True);self.m.uninstall(target);self.assertEqual(existing.read_text(),'original')
 def test_registered_source_target_is_rejected(self):
  source=self.base/'source';source.mkdir();(self.context/'workspace.local.yaml').write_text(yaml.safe_dump({'repositories':{'repo':{'path':str(source)}}}))
  self.m.package('INST-PKG-C','codex')
  with self.assertRaises(Exception):self.m.install('INST-C','INST-PKG-C',source/'config')
 def test_modified_managed_file_blocks_uninstall(self):
  self.m.package('INST-PKG-D','claude-code');target=self.base/'claude';self.m.install('INST-D','INST-PKG-D',target);manifest=yaml.safe_load((target/'.t-understand-install/install-manifest.yaml').read_text());p=target/manifest['files'][0]['path'];p.write_text(p.read_text()+'changed')
  self.assertEqual(self.m.doctor(target)['status'],'FAIL')
  with self.assertRaises(Exception):self.m.uninstall(target)
  self.assertEqual(self.m.uninstall(target,True)['status'],'UNINSTALLED')
 def test_all_skill_names_are_tu_namespaced(self):
  for skill in ROOT.joinpath('skills').rglob('SKILL.md'):
   front=yaml.safe_load(skill.read_text().split('---',2)[1]);self.assertTrue(skill.parent.name.startswith('tu-'));self.assertEqual(front['name'],skill.parent.name)
  aggregate=ROOT/'adapters/codex/tu-understand/SKILL.md';front=yaml.safe_load(aggregate.read_text().split('---',2)[1]);self.assertEqual(front['name'],'tu-understand');self.assertFalse((ROOT/'adapters/codex/t-understand').exists())
 def test_platform_permission_profiles_have_no_ask_fallback(self):
  generated={}
  for i,platform in enumerate(PLATFORMS):
   pid=f'INST-PERM-{i}';self.m.package(pid,platform);payload=self.context/'platform-packages'/pid/'payload';generated[platform]=payload
   for file in payload.rglob('*'):
    if file.is_file() and 't-understand-engine' not in file.relative_to(payload).parts:self.assertNotIn('bash: ask',file.read_text(errors='ignore'));self.assertNotIn('"ask"',file.read_text(errors='ignore'))
  open_agent=(generated['opencode']/'agents/t-understand.md').read_text();self.assertIn("external_directory: deny",open_agent);self.assertIn('git status*: allow',open_agent);self.assertIn('gh *: deny',open_agent)
  claude=json.loads((generated['claude-code']/'settings.json').read_text());self.assertEqual(claude['permissions']['defaultMode'],'acceptEdits');self.assertIn('Bash(*)',claude['permissions']['allow']);self.assertIn('Bash(git commit:*)',claude['permissions']['deny'])
  cursor=json.loads((generated['cursor']/'cli-config.json').read_text());self.assertIn('Shell(*)',cursor['permissions']['allow']);self.assertIn('Shell(git commit)',cursor['permissions']['deny']);self.assertIn('Shell(gh)',cursor['permissions']['deny'])
  codex=generated['codex'];self.assertTrue((codex/'skills/tu-understand/SKILL.md').exists());self.assertFalse((codex/'skills/t-understand/SKILL.md').exists());profile=(codex/'tu-understand.config.toml').read_text();self.assertIn('approval_policy = "never"',profile);self.assertIn('sandbox_mode = "workspace-write"',profile);rules=(codex/'rules/tu-understand.rules').read_text();self.assertIn('pattern = ["gh"]',rules);self.assertIn('pattern = ["git", "commit"]',rules)
 def test_json_permission_config_merges_without_force_and_restores(self):
  self.m.package('INST-PKG-MERGE','claude-code');target=self.base/'claude-merge';target.mkdir();original={'theme':'dark','permissions':{'allow':['CustomTool']}};(target/'settings.json').write_text(json.dumps(original,indent=2)+'\n')
  self.m.install('INST-MERGE','INST-PKG-MERGE',target);merged=json.loads((target/'settings.json').read_text());self.assertEqual(merged['theme'],'dark');self.assertIn('CustomTool',merged['permissions']['allow']);self.assertIn('Bash(*)',merged['permissions']['allow']);self.assertEqual(self.m.doctor(target)['status'],'PASS')
  self.m.uninstall(target);self.assertEqual(json.loads((target/'settings.json').read_text()),original)
 def test_force_replaces_existing_managed_install(self):
  self.m.package('INST-PKG-OLD','opencode');target=self.base/'replace';self.m.install('INST-OLD','INST-PKG-OLD',target)
  managed=target/'AGENTS.md';managed.write_text(managed.read_text()+' locally modified')
  self.m.package('INST-PKG-NEW','opencode')
  with self.assertRaises(Exception):self.m.install('INST-NEW','INST-PKG-NEW',target)
  replaced=self.m.install('INST-NEW','INST-PKG-NEW',target,True);self.assertEqual(replaced['install_id'],'INST-NEW');self.assertEqual(self.m.doctor(target)['status'],'PASS');self.assertNotIn('locally modified',managed.read_text())
 def test_agent_native_platform_install_generates_ids_and_packages_engine(self):
  target=self.base/'opencode-global'
  result=self.m.install_platform('opencode',target)
  self.assertEqual(result['platform'],'opencode');self.assertTrue(result['install_id'].startswith('INST-OPENCODE'));self.assertTrue((target/'t-understand-engine/agent_runtime.py').is_file());self.assertTrue((target/'t-understand-engine/runtime/tu_runtime/cli.py').is_file());self.assertEqual(self.m.doctor_platform('opencode',target)['status'],'PASS')
  # Force is an explicit replacement path, including managed installations.
  (target/'AGENTS.md').write_text('tampered')
  replaced=self.m.install_platform('opencode',target,True);self.assertEqual(replaced['status'],'INSTALLED');self.assertEqual(self.m.doctor_platform('opencode',target)['status'],'PASS')
 def test_install_wrappers_are_simple_and_force_capable(self):
  ps=(ROOT/'bin/install.ps1').read_text();sh=(ROOT/'bin/install.sh').read_text()
  self.assertIn("[string]$Target",ps);self.assertIn('[switch]$Force',ps);self.assertNotIn('ContextRoot',ps);self.assertIn("platform-install','--platform',$Target",ps)
  self.assertIn('[--force]',sh);self.assertNotIn('CONTEXT_ROOT',sh);self.assertIn('platform-install --platform',sh)
 def test_root_agent_hides_internal_context_and_cli_from_humans(self):
  root=(ROOT/'agents/t-understand/AGENT.md').read_text()
  self.assertIn('Human interaction contract',root);self.assertIn('Never require the human',root);self.assertIn('<workspace>/.t-understand/',root);self.assertIn('Generate stable operation IDs automatically',root)

