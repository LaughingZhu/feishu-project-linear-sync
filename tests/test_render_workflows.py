import importlib.util,json,subprocess,tempfile,unittest,sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/render_workflows.py'
KEYS=['source_key','title','node_name','linear_id','create_attempted','source_task_id','state','parent_name','parent_id']
def config():
 return {'table_name':'示例同步表','project_key':'demo-space','owner_key':'demo-owner','linear_team_id':'11111111-1111-4111-8111-111111111111','linear_assignee_id':'22222222-2222-4222-8222-222222222222','todo_state_id':'33333333-3333-4333-8333-333333333333','done_state_id':'44444444-4444-4444-8444-444444444444','canceled_state_id':'55555555-5555-4555-8555-555555555555','parent_url_prefix':'https://example.invalid/space/story/detail/','fields':{k:f'fldDemo{i}' for i,k in enumerate(KEYS)}}
class Tests(unittest.TestCase):
 def run_render(self,cfg,root,out='output'):
  f=root/'config.json';f.write_text(json.dumps(cfg));return subprocess.run([sys.executable,str(SCRIPT),'--config',str(f),'--out',str(root/out)],text=True,capture_output=True)
 def test_portable_graph_and_no_credentials(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);r=self.run_render(config(),root);self.assertEqual(r.returncode,0,r.stderr)
   a=json.loads((root/'output/task-inbound.json').read_text());b=json.loads((root/'output/task-outbound.json').read_text())
   self.assertEqual(len(a['steps']),22);self.assertEqual(len(b['steps']),27)
   trigger=next(n for n in a['steps'] if n['type']=='WebhookTrigger');sample=json.loads(trigger['data']['output_json'])
   self.assertEqual(sample['header']['operator'],'demo-owner');self.assertEqual(sample['payload']['project_key'],'demo-space')
   owner_gate=next(n for n in a['steps'] if n['id']=='branchDu8HIBiT');self.assertIn('demo-owner',json.dumps(owner_gate))
   create=next(n for n in a['steps'] if n['type']=='AddRecordAction');fields={v['field_name']:v['value'] for v in create['data']['field_values']};self.assertEqual(fields['Linear 创建已尝试'][0]['value'],False)
   for h in (n for n in b['steps'] if n['type']=='HTTPClientAction'):
    auth=next(x for x in h['data']['headers'] if x['key']=='Authorization');self.assertEqual(auth['value'][0]['value'],'YOUR_LINEAR_API_KEY')
    self.assertIn('fldDemo1',json.dumps(h));self.assertIn('11111111-1111-4111-8111-111111111111',json.dumps(h))
   self.assertNotIn('{{',json.dumps([a,b]));self.assertNotIn('webhook_url',trigger['data'])
   marker=root/'output/task-inbound.json';before=marker.read_bytes();retry=self.run_render(config(),root);self.assertNotEqual(retry.returncode,0);self.assertEqual(marker.read_bytes(),before)
 def test_invalid_configs_fail_without_output_or_secret_echo(self):
  variants=[]
  c=config();c['linear_team_id']='not-a-uuid';variants.append(c)
  c=config();c['done_state_id']=c['todo_state_id'];variants.append(c)
  c=config();c['fields']['title']=c['fields']['source_key'];variants.append(c)
  c=config();c['owner_key']='lin_api_PRIVATE_TEST_ONLY';variants.append(c)
  c=config();c['Authorization']='private-value';variants.append(c)
  c=config();c['parent_url_prefix']='https://user:private-value@example.invalid/';variants.append(c)
  variants.append(json.loads((ROOT/'assets/config.example.json').read_text()))
  for cfg in variants:
   with self.subTest(cfg_keys=list(cfg)),tempfile.TemporaryDirectory() as d:
    root=Path(d);r=self.run_render(cfg,root);self.assertNotEqual(r.returncode,0);self.assertFalse((root/'output').exists());self.assertNotIn('PRIVATE_TEST_ONLY',r.stderr);self.assertNotIn('private-value',r.stderr)

 def test_delete_routes_and_portable_options(self):
  spec=importlib.util.spec_from_file_location('renderer',SCRIPT);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  bodies=m.render(json.loads((ROOT/'assets/task-workflows.template.json').read_text()),config());nodes={n['id']:n for n in bodies['task-outbound']['steps']}
  for c in nodes['createOrUpdate']['data']['child_branch_list'][0]['condition']['conditions'][0]['conditions']:
   self.assertEqual(c['left_value']['extra_info']['table_name'],config()['table_name'])
  def check_options(v):
   if isinstance(v,dict):
    if v.get('value_type')=='option':self.assertNotIn('id',v['value']);self.assertTrue(v['value'].get('name'))
    for x in v.values():check_options(x)
   if isinstance(v,list):
    for x in v:check_options(x)
  check_options(bodies)
  def evaluate(c,values):
   if 'conditions' in c:
    xs=[evaluate(x,values) for x in c['conditions']];return all(xs) if c['conjunction']=='and' else any(xs)
   left=values.get(c['left_value']['value'].split('.')[-1]);op=c['operator']
   if op=='isEmpty':return left is None or left==''
   if op=='isNotEmpty':return left is not None and left!=''
   if op=='is':return left==c['right_value'][0]['value']
   raise AssertionError('unexpected operator '+op)
  def target(node,values):
   cases=node['data']['child_branch_list'];links=node['children']['links']
   for i,c in enumerate(cases):
    if evaluate(c['condition'],values):return links[i]['to']
   return links[-1]['to']
  def route(issue,attempted,state):
   values={'fldDemo3':issue,'fldDemo4':attempted,'fldDemo6':state};first=target(nodes['createOrUpdate'],values)
   return target(nodes[first],values) if first in ('createState','updateState') else first
  self.assertEqual(route(None,False,'已删除'),'skipDeletedCreate')
  self.assertNotEqual(nodes['skipDeletedCreate']['type'],'HTTPClientAction')
  self.assertEqual(route(None,True,'已删除'),'creationCheck')
  self.assertEqual(route(None,True,'未完成'),'creationCheck')
  self.assertEqual(route('existing-issue',True,'已删除'),'update1HTTP')
  self.assertEqual(route(None,False,'未完成'),'create2HTTP')


 def test_shareable_assets_have_no_live_tenant_values(self):
  patterns = {
   'static UUID': r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',
   'static field ID': r'\bfld[A-Za-z0-9]{6,}\b',
   'static option ID': r'\bopt[A-Za-z0-9]{6,}\b',
   'email': r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
   'tenant resource URL': r'https://[^/\s\"]+\.feishu\.cn/(?:wiki|base|docx)/',
  }
  for file in (ROOT/'assets').glob('*.json'):
   source=file.read_text()
   for label,pattern in patterns.items():
    self.assertFalse(bool(re.search(pattern,source)),file.name+': found '+label)

if __name__ == '__main__':
 unittest.main()
