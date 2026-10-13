"""将现有环境/显框素材与空间排演串成静音时间线；不生成新媒体资产。"""
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WORK = Path(__file__).resolve().parents[2]
OUT = WORK / 'media/previs/half-dance-v01'
FONT = '/System/Library/Fonts/STHeiti Medium.ttc'

# 此处的秒数是导演排演参数，既非已认可片长，也不是生成配置。
labels = [
    (0, 3, 'S001｜现有环境候选：服务动作'),
    (3, 6, 'S012｜她发起邀请：目光与伸手同框'),
    (6, 11, 'S013a｜行进与转身：身体带动裙摆'),
    (11, 13, 'S013b｜转身未完：切近她的反应'),
    (13, 15, 'S014｜门逐渐打开：她转向入口'),
    (15, 20, 'S003｜继续跨门：完整着装进入暖光'),
    (20, 23, 'S015｜侧向经过：保持行进方向'),
    (23, 27, 'S005｜披肩向后：右手到鬓边'),
    (27, 30, 'S006｜复用准确原画与显框'),
]
OUT.mkdir(parents=True, exist_ok=True)
warning = '仅为空间与切镜排演｜模型不表现步态、布料或人物美感'
graph = [
    '[0:v]trim=start=2.75:end=5.75,setpts=PTS-STARTPTS,fps=24,scale=960:540,setsar=1[a]',
    '[1:v]setpts=PTS-STARTPTS,setsar=1[b]',
    '[2:v]tpad=start_duration=0.25:start_mode=clone,trim=duration=3,setpts=PTS-STARTPTS,fps=24,scale=960:540,setsar=1[c]',
    '[a][b][c]concat=n=3:v=1:a=0[film]',
]
label_inputs = []
for index, (start, end, title) in enumerate(labels):
    # 复用项目既有的透明标签叠加方式；本机 ffmpeg 没有 drawtext。
    label = OUT / f'label-{index:02d}.png'
    im = Image.new('RGBA', (960, 540), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 960, 44), fill=(0, 0, 0, 190))
    draw.rectangle((0, 490, 960, 540), fill=(0, 0, 0, 190))
    draw.text((16, 12), warning, font=ImageFont.truetype(FONT, 19), fill='white')
    draw.text((16, 505), title, font=ImageFont.truetype(FONT, 22), fill='white')
    im.save(label)
    label_inputs += ['-loop', '1', '-i', str(label)]
    before = 'film' if index == 0 else f'labelled{index-1}'
    graph.append(f"[{before}][{index+3}:v]overlay=enable='gte(t,{start})*lt(t,{end})':shortest=1[labelled{index}]")
# 拼接末尾的时间戳取整可能丢一帧；只延续显框结尾，保证排演720帧。
graph.append('[labelled8]tpad=stop_mode=clone:stop_duration=0.083333,trim=end_frame=720[out]')
graphfile = OUT / 'assembly.ffmpeg.txt'
graphfile.write_text(';\n'.join(graph))
subprocess.run([
    'ffmpeg', '-hide_banner', '-loglevel', 'error', '-filter_complex_threads', '2', '-y',
    '-i', str(WORK / 'media/clips/film-v05/S001K_take01.mp4'),
    '-framerate', '24', '-start_number', '1', '-i', str(OUT / 'frames/frame_%04d.png'),
    '-i', str(WORK / 'media/exports/ending-v07/original-painting-to-wall.mp4'),
    *label_inputs,
    '-filter_complex_script', str(graphfile), '-map', '[out]', '-an', '-t', '30',
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart', str(OUT / 'whole-film-spatial-previs-v01.mp4'),
], check=True)
(OUT / 'assembly.json').write_text(json.dumps({
    'status': 'internal spatial draft, not a film candidate or generation reference',
    'seconds': 30, 'fps': 24, 'silent': True, 'labels': labels,
    'approved_duration': False, 'paid_generation_calls': 0,
}, ensure_ascii=False, indent=2) + '\n')
