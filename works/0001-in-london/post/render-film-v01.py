"""首个完整有声审看片：真实运动镜头 + 原画回墙；不重绘素材。"""
import csv, hashlib, json, re, subprocess
from pathlib import Path

W = Path(__file__).resolve().parents[1]
OUT = W / 'media/exports/film-v01'
OUT.mkdir(parents=True, exist_ok=True)
AUDIT = W / 'media/audit/film-v02'
FF = '/opt/homebrew/bin/ffmpeg'
PROBE = '/opt/homebrew/bin/ffprobe'
# 时长由读清空间、动作结束和收尾余韵决定；均为24fps整数帧。
shots = [
 ('S001', 0, 84, '餐厅与秩序'),
 ('S002', 6, 108, '落杯、松指、撤手'),
 ('S007', 12, 72, '窗内望向夜晚'),
 ('S008', 6, 96, '从街边走入门槛'),
 ('S003', 0, 120, '完整银裙、入场、停稳'),
 ('S004a', 0, 108, '目光、握点解除'),
 ('S005b', 0, 120, '手至鬓边、回到画中姿态'),
 ('S006', 0, 144, '缓退至原作与画框'),
]
duration = sum(s[2] for s in shots)/24
inputs=[]
for shot,_,_,_ in shots:
 inputs.append(W/('media/exports/ending-v04/A-slow-reveal-fullbleed.mp4' if shot=='S006' else f'media/clips/film-v02/{shot}_take01.mp4'))
music = W/'media/audio/film-v01/music-original.mp3'
assert all(p.is_file() for p in inputs+[music])
graph=[]
for i,(shot,start,n,_) in enumerate(shots):
 start_s,secs=start/24,n/24
 graph.append(f'[{i}:v]trim=start_frame={start}:end_frame={start+n},setpts=PTS-STARTPTS,fps=24,scale=1280:720,setsar=1,format=yuv420p,settb=1/24[v{i}]')
 if shot!='S006':
  # 保留原生落杯、脚步、衣料与空间声，微淡入淡出避免切口爆音。
  gain=0.50 if shot=='S002' else 0.35
  graph.append(f'[{i}:a]atrim=start={start_s}:duration={secs},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,highpass=f=75,lowpass=f=7000,volume={gain},afade=t=in:d=0.08,afade=t=out:st={secs-0.15}:d=0.15[a{i}]')
 else:
  # 回画后餐厅空间声渐远，复用开场底噪尾段，不伪造新对白。
  graph.append(f'[0:a]atrim=start=1:duration=4,asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,highpass=f=90,lowpass=f=2200,volume=0.18,apad,atrim=duration={secs},afade=t=in:d=0.15,afade=t=out:st=0.5:d=3[a{i}]')
graph.append(''.join(f'[v{i}]'for i in range(len(shots)))+f'concat=n={len(shots)}:v=1:a=0[picture]')
graph.append(''.join(f'[a{i}]'for i in range(len(shots)))+f'concat=n={len(shots)}:v=0:a=1[ambience]')
graph.append(f'[8:a]atrim=duration={duration},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=0.88,afade=t=in:d=0.65,afade=t=out:st={duration-3}:d=3[score]')
graph.append('[score][ambience]amix=inputs=2:duration=first:normalize=0[mix]')
graph_file=OUT/'assembly.ffmpeg.txt';graph_file.write_text(';\n'.join(graph)+'\n')
base=[FF,'-hide_banner','-loglevel','error','-filter_complex_threads','2']
for p in inputs+[music]:base+=['-i',str(p)]
intermediate=OUT/'picture-and-mix.mkv'
final=OUT/'in-london-first-film-with-audio.mp4'
if intermediate.exists() or final.exists():raise FileExistsError('保留既有输出；用新目录修订，不静默覆盖。')
subprocess.run(base+['-filter_complex_script',str(graph_file),'-map','[picture]','-map','[mix]','-t',str(duration),'-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-c:a','pcm_s24le',str(intermediate)],check=True)
# 双遍响度处理；数值校验不能替代真人听感审阅。
scan=subprocess.run([FF,'-hide_banner','-i',str(intermediate),'-vn','-af','loudnorm=I=-17:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
(AUDIT/'mix-loudnorm-pass1.txt').write_text(scan.stderr)
m=json.loads(scan.stderr[scan.stderr.rfind('{'):scan.stderr.rfind('}')+1])
flt=f"loudnorm=I=-17:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true:print_format=json"
r=subprocess.run([FF,'-hide_banner','-i',str(intermediate),'-map','0:v','-map','0:a','-c:v','copy','-af',flt,'-ar','48000','-c:a','aac','-b:a','192k','-movflags','+faststart',str(final)],capture_output=True,text=True,check=True)
(AUDIT/'mix-loudnorm-pass2.txt').write_text(r.stderr)
probe=json.loads(subprocess.check_output([PROBE,'-v','error','-count_frames','-show_entries','stream=codec_name,codec_type,width,height,r_frame_rate,nb_read_frames,sample_rate,channels,duration:format=duration,size','-of','json',str(final)]))
subprocess.run([FF,'-hide_banner','-loglevel','error','-i',str(final),'-f','null','-'],check=True)
assert any(x['codec_type']=='audio'for x in probe['streams'])
vs=next(x for x in probe['streams']if x['codec_type']=='video')
assert (vs['width'],vs['height'],int(vs['nb_read_frames']))==(1280,720,sum(x[2]for x in shots))
with (W/'post/film-v01-edit.csv').open('w',newline='')as f:
 writer=csv.writer(f,lineterminator='\n');writer.writerow(['shot','input','source_start_frame','frames','timeline_start_seconds','purpose'])
 t=0
 for row,path in zip(shots,inputs):
  shot,start,n,purpose=row;writer.writerow([shot,str(path.relative_to(W)),start,n,t,purpose]);t+=n/24
meta={'output':str(final.relative_to(W)),'sha256':hashlib.sha256(final.read_bytes()).hexdigest(),'duration_seconds':duration,'fps':24,'audio':True,'probe':probe,'full_decode':'passed','sound':'Generated original instrumental + generated native ambience/foley; no separately recorded voiceover','human_listening_acceptance':False,'user_artistic_acceptance':False,'source_files':[{'path':str(x.relative_to(W)),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()}for x in inputs+[music]],'loudness_pass1':m}
(W/'post/film-v01-render.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'output':str(final),'duration':duration,'probe':probe},ensure_ascii=False),flush=True)
