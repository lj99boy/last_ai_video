"""开头入点试听：保留原曲起始顺序，不从主歌中间起播。"""
from pathlib import Path
import subprocess,json,hashlib
W=Path(__file__).resolve().parents[1]
FF='/opt/homebrew/bin/ffmpeg'
source=W/'media/audio/film-v03/young-and-beautiful-user-source.mp3'
room=W/'media/clips/film-v02/S001_take01.mp4'
out=W/'media/audio/film-v03/music-opening-C-preview.mp3'
audit=W/'media/audit/film-v03'
assert not out.exists(), '保留既有样片，修改时使用新版本名'
# 只检验15秒开头，不把预览末尾淡出当作影片结尾。
# 环境声来自既有餐厅镜头，不新生成或模拟歌曲。
graph=';'.join([
'[0:a]atrim=start=0:duration=13.8,asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,volume=-6dB,afade=t=in:st=0:d=3,adelay=1200:all=1[music]',
'[1:a]atrim=start=0:duration=5,asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,highpass=f=90,lowpass=f=6500,volume=0.22,afade=t=in:d=0.35,afade=t=out:st=2:d=3,apad=whole_dur=15[room]',
'[music][room]amix=inputs=2:duration=longest:normalize=0,atrim=duration=15,afade=t=out:st=14.4:d=0.6[a]'])
(audit/'music-opening-C-filter.txt').write_text(graph+'\n')
subprocess.run([FF,'-hide_banner','-loglevel','error','-i',str(source),'-i',str(room),'-filter_complex',graph,'-map','[a]','-vn','-c:a','libmp3lame','-b:a','192k',str(out)],check=True)
subprocess.run([FF,'-hide_banner','-loglevel','error','-i',str(out),'-f','null','-'],check=True)
r=subprocess.run([FF,'-hide_banner','-i',str(out),'-af','loudnorm=I=-17:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
(audit/'music-opening-C-loudness.txt').write_text(r.stderr)
s=r.stderr;m=json.loads(s[s.rfind('{'):s.rfind('}')+1]);assert float(m['input_tp']) < -1.5
meta={'id':'MUSICV03C_OPENING','status':'opening_only_preview_pending_user','file':{'path':str(out.relative_to(W)),'sha256':hashlib.sha256(out.read_bytes()).hexdigest()},'duration_seconds':15,'music_source_start_seconds':0,'music_source_duration_seconds':13.8,'music_timeline_start_seconds':1.2,'music_fade_in_seconds':3,'music_gain_db':-6,'room_source':str(room.relative_to(W)),'room_gain_linear':0.22,'room_fade_out_timeline_seconds':[2,5],'preview_only_fade_out_seconds':[14.4,15],'full_decode':'passed','measured_loudness':m,'full_audio_listening_verified':False,'picture_locked':False,'sources':[{'path':str(p.relative_to(W)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in [source,room]]}
(W/'production/film-v03/music-opening-C.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'output':str(out),'measured_I':m['input_i'],'true_peak':m['input_tp']},ensure_ascii=False))
