"""分阶段生成原曲结构候选；每段检验实际时长，避免解码成功但时间戳异常。"""
from pathlib import Path
import hashlib,json,subprocess
W=Path(__file__).resolve().parents[1]
F='/opt/homebrew/bin/ffmpeg';PROBE='/opt/homebrew/bin/ffprobe'
P=W/'production/film-v04';A=W/'media/audio/film-v04';A.mkdir(parents=True,exist_ok=True)
original=W/'media/audio/film-v03/young-and-beautiful-user-source.mp3'
room=W/'media/clips/film-v02/S001_take01.mp4'
commands=[]
def probe(path,expected):
 data=json.loads(subprocess.check_output([PROBE,'-v','error','-show_entries','format=duration:stream=codec_type,start_time,sample_rate,channels','-of','json',str(path)]))
 assert abs(float(data['format']['duration'])-expected)<0.08,(path,data)
 for s in data['streams']:
  assert abs(float(s.get('start_time',0)))<0.08,(path,data)
 return data
def render(args,out,seconds):
 cmd=[F,'-hide_banner','-loglevel','error',*args,'-map_metadata','-1',str(out)]
 commands.append(cmd)
 if not out.exists():subprocess.run(cmd,check=True)
 return probe(out,seconds)
# 以采样数重建连续时间轴；保持原曲内容，不修改音高和速度。
source=A/'music-E-source.wav'
render(['-i',str(original),'-map','0:a:0','-vn','-af','asetpts=N/SR/TB,aresample=48000','-c:a','pcm_s24le'],source,236.069646)
intro=A/'music-E-intro.wav';theme=A/'music-E-theme.wav';join=A/'music-E-join.wav'
render(['-i',str(source),'-af','atrim=start=0:end=8.5,asetpts=N/SR/TB','-c:a','pcm_s24le'],intro,8.5)
render(['-i',str(source),'-af','atrim=start=48.5:end=81.5,asetpts=N/SR/TB','-c:a','pcm_s24le'],theme,33)
render(['-i',str(intro),'-i',str(theme),'-filter_complex','[0:a][1:a]acrossfade=d=1.6:c1=qsin:c2=qsin,asetpts=N/SR/TB[a]','-map','[a]','-c:a','pcm_s24le'],join,39.9)
# 单独检查音乐铺底，再叠加既有空间声；不把数值验证称为乐句校听。
bed=A/'music-E-bed.wav'
render(['-i',str(join),'-af','volume=-4dB,afade=t=in:d=3,afade=t=out:st=35.9:d=4,adelay=1200:all=1,asetpts=N/SR/TB','-c:a','pcm_s24le'],bed,41.1)
room_bed=A/'music-E-room.wav'
render(['-i',str(room),'-map','0:a:0','-vn','-af','atrim=duration=5,asetpts=N/SR/TB,aresample=48000,highpass=f=90,lowpass=f=6500,volume=0.22,afade=t=in:d=0.35,afade=t=out:st=2:d=3,apad=whole_dur=41.1','-c:a','pcm_s24le'],room_bed,41.1)
out=A/'music-structure-E-preview.m4a'
info=render(['-i',str(bed),'-i',str(room_bed),'-filter_complex','[0:a][1:a]amix=inputs=2:duration=longest:normalize=0,asetpts=N/SR/TB[a]','-map','[a]','-c:a','aac','-b:a','256k'],out,41.1)
subprocess.run([F,'-v','error','-i',str(out),'-f','null','-'],check=True)
r=subprocess.run([F,'-hide_banner','-i',str(out),'-af','loudnorm=I=-17:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
s=r.stderr;m=json.loads(s[s.rfind('{'):s.rfind('}')+1])
assert float(m['input_tp']) < -1.5,m
assert -30 < float(m['input_i']) < -8,m
meta={'status':'whole_score_candidate_pending_listening_and_picture','output':str(out.relative_to(W)),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'duration_seconds':41.1,'segments':[[0,8.5],[48.5,81.5]],'crossfade_seconds':1.6,'music_start_seconds':1.2,'fade_in_seconds':3,'fade_out_seconds':4,'probe':info,'loudness':m,'full_decode':'passed','listening_verified':False,'picture_locked':False,'sources':[{'path':str(x.relative_to(W)),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()}for x in [original,room]],'limitations':['乐句边界仅为候选，需实际校听','时长服务剪辑，此版不锁定影片时长','D/D2输出时间戳异常，已拒绝，不向用户交付']}
(P/'music-structure-E.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
(W/'media/audit/film-v04/music-E-commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'output':str(out),'duration':41.1,'I':m['input_i'],'true_peak':m['input_tp']},ensure_ascii=False))
