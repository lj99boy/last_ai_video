from pathlib import Path
import subprocess,json,hashlib
from PIL import Image,ImageDraw,ImageFont
w=Path(__file__).resolve().parents[1]
p=w/'production/film-v06'; o=w/'media/exports/film-v06'
font=ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc',24)
labels=[('preview','剧情预演 · 非成片 · 衣料与接镜待审','lt(t,19.5)+gte(t,25)'),('ack','静帧占位 1/2 · 待拍：女主轻点头，转回前方','gte(t,19.5)*lt(t,22.5)'),('pass','静帧占位 2/2 · 待拍：女主继续走 · 本图位置仍需前移','gte(t,22.5)*lt(t,25)')]
cmd=['/opt/homebrew/bin/ffmpeg','-hide_banner','-loglevel','error','-filter_complex_threads','2','-i',str(o/'whole-film-structure-v01.mp4')]
graph=[]
for i,(name,label,enable) in enumerate(labels,1):
 im=Image.new('RGBA',(1280,720),(0,0,0,0)); draw=ImageDraw.Draw(im); draw.rectangle((0,0,1280,44),fill=(0,0,0,185)); draw.text((18,9),label,font=font,fill=(255,255,255,255)); target=o/f'review-label-{name}-v01.png'; im.save(target); cmd+=['-loop','1','-i',str(target)]; before='0:v' if i==1 else f'v{i-1}'; graph.append(f'[{before}][{i}:v]overlay=enable=\'{enable}\':shortest=1[v{i}]')
target=o/'whole-film-structure-v01-labeled.mp4'
assert not target.exists()
cmd+=['-filter_complex',';'.join(graph),'-map','[v3]','-map','0:a:0','-t',str(832/24),'-c:v','libx264','-preset','medium','-crf','19','-pix_fmt','yuv420p','-color_range','tv','-c:a','copy','-movflags','+faststart',str(target)]
subprocess.run(cmd,check=True)
probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-count_frames','-show_entries','stream=codec_type,width,height,nb_read_frames:format=duration','-of','json',str(target)]))
assert int(probe['streams'][0]['nb_read_frames'])==832
subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(target),'-f','null','-'],check=True)
report={'output':str(target.relative_to(w)),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'probe':probe,'full_decode':'passed','source':'media/exports/film-v06/whole-film-structure-v01.mp4','labels':labels,'purpose':'Permanent review labels make static placeholders explicit even in players ignoring subtitle tracks.','audio_peak_dbfs':-3.4,'audio_mean_dbfs':-15.5,'auditory_review':False,'normal_speed_motion_review':False,'creator_acceptance':False}
(p/'labeled-preview-v01.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(target)
