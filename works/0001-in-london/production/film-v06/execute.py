"""通过官方CLI执行已在plan.json登记的单次成片任务；记录先于副作用，不自动重试。"""
import argparse,hashlib,json,subprocess
from pathlib import Path
W=Path(__file__).resolve().parents[2]
P=Path(__file__).resolve().parent
A=W/'media/audit/film-v06';A.mkdir(parents=True,exist_ok=True)
CLI='/Users/bytedance/.libtv/libtv';PROJECT='6b6cccb8f0d5497881f0058650000fb2'
args=argparse.ArgumentParser();args.add_argument('shot');args.add_argument('--run',action='store_true');args.add_argument('--existing-inputs-only',action='store_true');opts=args.parse_args()
spec=json.loads((P/'plan.json').read_text())[opts.shot]
# 本地在线schema快照先校验模式与图片数量，避免用猜测的API模式名建节点。
schema_files={'Seedance 2.5（样片模式）':'seedance-draft-schema.json','Seedance 2.5':'seedance-standard-schema.json'}
if spec['settings']['model'] in schema_files:
 schema=json.loads((P/schema_files[spec['settings']['model']]).read_text())['schema']
 modes=schema['properties']['modeType']['items']
 mode=spec['settings']['modeType'];assert mode in modes, f'Unsupported mode: {mode}'
 lo,hi=modes[mode]
 # 视频编辑以视频为底片，图片只提供材质指导；不能把视频误计为图片。
 if mode=='videoEdit2video':
  assert lo<=len(spec.get('videos',[]))<=hi, 'Source video count does not match edit mode'
  assert len(spec.get('images',[]))<=schema['properties']['modeType']['videoEdit2videoConfig']['imageMaxWithVideo']
 else:
  assert lo<=len(spec.get('images',[]))<=hi, 'Reference count does not match mode'
state_path=P/f'{opts.shot}-execution.json'
if state_path.exists():
 state=json.loads(state_path.read_text())
else:state={'shot':opts.shot,'authorization':'User active goal: produce complete film with audio using existing workflow; no recharge/subscription','createAttempted':False,'runAttempted':False,'estimatedCredits':None,'actualCredits':None,'actualCNY':None,'inputs':[]}
# 审批要求明确禁传文件时，只复用平台已有引用；缺一项即退出。
if opts.existing_inputs_only:
 assert [x['path']for x in state['inputs']]==spec.get('images',[]), 'Upload prohibited: existing inputs incomplete'
def save():state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
def call(label,cmd):
 raw=A/f'{opts.shot}-{label}.json'
 with raw.open('w') as out:subprocess.run([CLI]+cmd,stdout=out,check=True)
 return json.loads(raw.read_text())
# 已尝试创建但没有收到ID时不能盲目再创建；需读画布确定实际状态。
if not state.get('nodeId'):
 if state['createAttempted']:raise SystemExit('Ambiguous creation: inspect canvas, do not repeat.')
 for i,rel in enumerate(spec.get('images',[])):
  if i<len(state['inputs']):continue
  f=W/rel;assert f.exists(),f
  u=call(f'upload-{i}',['upload',f'成片v06 {opts.shot} 参考{i+1}','-p',PROJECT,'-f',str(f),'--x',str(10500+i*500),'--y',str(spec['y'])])
  state['inputs'].append({'nodeId':u['nodeKey'],'path':rel,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()});save()
 state['videos']=spec.get('videos',[])
 text=(P/spec['prompt']).read_text()
 refs=state.get('videos',[])+state['inputs']
 if refs:text='\n'.join('{{Node '+x['nodeId']+'}}'for x in refs)+'\n'+text
 cmd=['node','--x','11600','--y',str(spec['y']),'create',f'成片v06 {opts.shot} 单次待运行','-p',PROJECT,'-t',spec.get('type','video'),'--prompt',text]
 for x in refs:cmd+=['--left',x['nodeId']]
 for k,v in spec['settings'].items():cmd+=['-s',f'{k}={str(v).lower() if isinstance(v,bool) else v}']
 state['createAttempted']=True;save()
 d=call('create',cmd);state['nodeId']=d.get('newNodeKey') or d['nodeKey'];save()
r=call('readback',['node',state['nodeId'],'-p',PROJECT]);params=r['data']['params']
state['readback']={k:params[k]for k in ['model','modeType','count','settings','advancedSettings','imageListOrder','videoListOrder']if k in params}
desired=(P/spec['prompt']).read_text().strip()
actual=params.get('prompt','')
state['configuredPromptMatches']=desired in actual
state['readbackPrompt']=actual
assert state['configuredPromptMatches'], 'Prompt readback mismatch: inspect before spending credits'
save();print(json.dumps({'shot':opts.shot,'nodeId':state['nodeId'],'configured':state['readback']},ensure_ascii=False),flush=True)
if not opts.run:raise SystemExit(0)
# 创作者已否决的起帧必须更换并重新审查，不能只因之后开放了预算就误运行。
if state.get('holdReason'):
 raise SystemExit('Creative hold: '+state['holdReason'])
# 报价与全片预算未核对前，不再消耗会员积分。
gate=json.loads((P/'budget-gate.json').read_text())
if not gate['paid_generation_enabled']:
 raise SystemExit('Paid generation stopped: '+gate['reason'])
# 临时开放也只允许已核价的这一镜，防止其他任务沿用同一开关。
assert opts.shot in gate.get('allowed_shots', []), 'Shot not in scoped spending authorization'
quote=state.get('estimatedCredits')
assert isinstance(quote,(int,float)) and 0 < quote <= gate['max_single_run_credits'], 'Missing or excessive quote'
if state['runAttempted']:raise SystemExit('Run already attempted; inspect existing result, never auto retry.')
if spec.get('type','video')=='video':
 assert params['count']==1
 assert params['model']==spec['settings']['model']
 assert params['modeType']==spec['settings']['modeType']
 for key in ['duration','ratio','resolution','enableSound']:
  assert params['settings'][key]==spec['settings'][key], f'Configuration changed: {key}'
 assert params.get('imageListOrder')==[x['nodeId']for x in state['inputs']]
 assert params.get('videoListOrder',[])==[x['nodeId']for x in state.get('videos',[])]
 for item in state['inputs']+state.get('videos',[]):
  assert hashlib.sha256((W/item['path']).read_bytes()).hexdigest()==item['sha256'], 'Input changed after configuration'
state['runAttempted']=True;state['status']='running';save()
r=call('run',['node',state['nodeId'],'-p',PROJECT,'--run'])
state['taskId']=r.get('taskId');state['platformStatus']=r.get('status');state['status']='platform_returned';save()
if r.get('status')!=2:raise SystemExit('Not successful: inspect result, no retry.')
urls=r.get('data',{}).get('url');assert urls,'No media returned'
u=urls[0]if isinstance(urls,list)else urls
if isinstance(u,dict):u=u['url']
dest=W/spec['output'];dest.parent.mkdir(parents=True,exist_ok=True)
subprocess.run(['/usr/bin/curl','--fail','--location','--silent','--show-error','--output',str(dest),u],check=True)
state['output']=spec['output'];state['sha256']=hashlib.sha256(dest.read_bytes()).hexdigest()
state['probe']=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-count_frames','-show_entries','stream=codec_type,width,height,r_frame_rate,nb_read_frames,sample_rate,channels:format=duration','-of','json',str(dest)]))
subprocess.run(['/opt/homebrew/bin/ffmpeg','-hide_banner','-loglevel','error','-i',str(dest),'-f','null','-'],check=True)
state['fullDecode']='passed';state['status']='completed_pending_artistic_review';save()
print(json.dumps({'shot':opts.shot,'completed':True,'output':spec['output'],'taskId':state['taskId'],'probe':state['probe']},ensure_ascii=False),flush=True)
