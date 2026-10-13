"""按已记录计划做本地剪辑；历史预演和完整动态计划均可用，不调用生成服务。"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import shutil
import subprocess

W = Path(__file__).resolve().parents[1]
P = W / 'production/film-v05'
OUT = W / 'media/exports/film-v05'
FF = shutil.which('ffmpeg')
PROBE = shutil.which('ffprobe')
parser = argparse.ArgumentParser()
parser.add_argument('--version', required=True, type=int)
parser.add_argument('--production', default='film-v05', choices=['film-v05', 'film-v06'])
parser.add_argument('--plan', default='editorial-plan.json', help='制作目录内的剪辑计划文件；保留历史默认计划，不互相覆盖。')
parser.add_argument('--output-dir', type=Path, help='复建到独立目录，视频及报告均写入此处，不改历史产物。')
args = parser.parse_args()
if not FF or not PROBE:
    parser.error('需要 PATH 中的 ffmpeg 和 ffprobe；本脚本不会安装依赖或提交付费生成。')
P = W / 'production' / args.production
OUT = args.output_dir.resolve() if args.output_dir else W / 'media/exports' / args.production
REPORT = OUT if args.output_dir else P
assert args.version > 0
version = f'v{args.version:02d}'
stem = f'whole-film-structure-{version}'
plan = json.loads((P / args.plan).read_text())
def output_path(path):
    """默认记录作品相对路径；独立复建目录保留绝对定位。"""
    return str(path.relative_to(W)) if path.is_relative_to(W) else str(path)
shots = plan['shots']
fps = plan['fps']
frames = sum(s['frames'] for s in shots)
duration = frames / fps
OUT.mkdir(parents=True, exist_ok=True)
final = OUT / f'{stem}.mp4'
if final.exists():
    raise FileExistsError('保留已有输出；修订请另建版本。')
command = [FF, '-hide_banner', '-loglevel', 'error', '-filter_complex_threads', '2']
graph = []
sources = []
for i, shot in enumerate(shots):
    path = W / shot['path']
    assert path.is_file(), path
    still = path.suffix.lower() in ('.jpg', '.png')
    if still:
        command += ['-loop', '1', '-framerate', str(fps)]
    command += ['-i', str(path)]
    start_frame = shot.get('source_start_frame', 0)
    filters = f'[{i}:v]fps={fps},trim=start_frame={start_frame}:end_frame={start_frame+shot["frames"]},setpts=PTS-STARTPTS'
    if 'crop' in shot:
        x, y, width, height = shot['crop']
        filters += f',crop=iw*{width}:ih*{height}:iw*{x}:ih*{y}'
    filters += ',scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,setsar=1,format=yuv420p,settb=1/24'
    filters += f'[v{i}]'
    graph.append(filters)
    sources.append({'path': shot['path'], 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
count = len(shots)
music = W / plan['music']
room_plan = plan['room_audio']
room = W / room_plan['path']
# 本机FFmpeg无drawtext滤镜；用独立字幕轨标明预演性质，保留可关闭性。
def timestamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
reveal_duration = shots[-1]['frames'] / fps
reveal_start = duration - reveal_duration
subtitle = OUT / f'{stem}.srt'
subtitle_entries = []
subtitle_cursor = 0
for i, shot in enumerate(shots):
    end = subtitle_cursor + shot['frames'] / fps
    if shot.get('review_label'):
        label = shot['review_label']
    elif shot['id'] == 'S006-reveal':
        label = '结构预演 · 原画显框'
    elif shot['id'] == 'S005-painting':
        label = '原画姿态落点 · 接镜待审'
    elif Path(shot['path']).suffix.lower() in ('.jpg', '.png'):
        label = '静帧占位 · 动作待拍'
    else:
        label = '动作样片 · 接镜待审'
    subtitle_entries.append(f'{i+1}\n{timestamp(subtitle_cursor)} --> {timestamp(end)}\n{label}\n')
    subtitle_cursor = end
subtitle.write_text('\n'.join(subtitle_entries))
command += ['-i', str(music), '-i', str(room), '-i', str(subtitle)]
graph.append(''.join(f'[v{i}]' for i in range(count)) + f'concat=n={count}:v=1:a=0[picture]')
delay = plan['music_start_seconds']
music_length = duration - delay
music_source_start = plan.get('music_source_start_seconds', 0)
# 乐句边界来自本地音源识别；保留连续原曲旧模式供历史方案重建。
segments = plan.get('music_segments')
if segments:
    assert len(segments) == 2
    crossfade = plan['music_crossfade_seconds']
    assert all(s['duration_seconds'] > crossfade for s in segments)
    assert abs(sum(s['duration_seconds'] for s in segments) - crossfade - music_length) < 1/fps
    graph.append(f'[{count}:a]asplit=2[score_source0][score_source1]')
    for i, segment in enumerate(segments):
        graph.append(f'[score_source{i}]atrim=start={segment["source_start_seconds"]}:duration={segment["duration_seconds"]},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[score_part{i}]')
    graph.append(f'[score_part0][score_part1]acrossfade=d={crossfade}:c1=qsin:c2=qsin[score_phrase]')
    score_input = '[score_phrase]'
else:
    graph.append(f'[{count}:a]atrim=start={music_source_start}:duration={music_length},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[score_phrase]')
    score_input = '[score_phrase]'
fade_in = plan.get('music_fade_in_seconds', 2.5)
fade_out = plan.get('music_fade_out_seconds', 2.5)
graph.append(f'{score_input}volume=0.65,afade=t=in:d={fade_in},afade=t=out:st={music_length-fade_out}:d={fade_out},adelay={round(delay*1000)}:all=1[score]')
# 餐厅声与当前选用服务素材对应；未校听前只作低音量声画预演。
graph.append(f'[{count+1}:a]atrim=start={room_plan["source_start_seconds"]}:duration={room_plan["duration_seconds"]},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,highpass=f=90,lowpass=f=5500,volume={room_plan["volume"]},afade=t=in:d=0.25,afade=t=out:st={room_plan["fade_out_start_seconds"]}:d={room_plan["fade_out_duration_seconds"]},apad,atrim=duration={duration}[room]')
graph.append('[score][room]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.89:level=false[mix]')
graph_file = OUT / f'{stem}.ffmpeg.txt'
graph_file.write_text(';\n'.join(graph))
subprocess.run(command + ['-filter_complex_script', str(graph_file), '-map', '[picture]', '-map', '[mix]', '-map', f'{count+2}:s:0', '-t', str(duration), '-r', str(fps), '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-c:s', 'mov_text', '-metadata:s:s:0', 'language=zho', '-disposition:s:0', 'default', '-movflags', '+faststart', str(final)], check=True)
probe = json.loads(subprocess.check_output([PROBE, '-v', 'error', '-count_frames', '-show_entries', 'stream=codec_type,width,height,nb_read_frames,sample_rate,channels:format=duration', '-of', 'json', str(final)]))
video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
assert int(video['nb_read_frames']) == frames
assert (video['width'], video['height']) == (1280, 720)
assert abs(float(probe['format']['duration']) - duration) < .05
assert any(s['codec_type'] == 'audio' and s['channels'] == 2 for s in probe['streams'])
subprocess.run([FF, '-v', 'error', '-i', str(final), '-f', 'null', '-'], check=True)
with (REPORT / f'editorial-timeline-{version}.csv').open('w', newline='') as f:
    writer = csv.writer(f, lineterminator='\n')
    writer.writerow(['shot', 'start_seconds', 'end_seconds', 'frames', 'source', 'purpose', 'planned_motion', 'join'])
    cursor = 0
    for s in shots:
        writer.writerow([s['id'], cursor/fps, (cursor+s['frames'])/fps, s['frames'], s['path'], s['purpose'], s['planned_motion'], s['join']])
        cursor += s['frames']
still_duration = sum(s['frames'] for s in shots if Path(s['path']).suffix.lower() in ('.jpg', '.png')) / fps
placeholder_duration = sum(s['frames'] for s in shots if Path(s['path']).suffix.lower() in ('.jpg', '.png') and s['id'] != 'S005-painting') / fps
report = {'output': output_path(final), 'sha256': hashlib.sha256(final.read_bytes()).hexdigest(), 'duration_seconds': duration, 'frames': frames, 'static_placeholder_seconds': placeholder_duration, 'original_painting_hold_seconds': still_duration-placeholder_duration, 'motion_sample_seconds': duration-still_duration-reveal_duration, 'original_wall_reveal_seconds': reveal_duration, 'probe': probe, 'full_decode': 'passed', 'music_listening_approved_by_user': plan.get('music_listening_approved', False), 'full_film_listening_verified': False, 'motion_verified': False, 'user_acceptance': False, 'sources': sources, 'limitations': plan.get('review_limitations', ['含静帧占位，未完成' if placeholder_duration else '完整动态剪辑候选；创作者审美结论另见交付记录', plan['music_note'], plan['audio_implementation_note']])}
(REPORT / f'editorial-render-{version}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
(REPORT / f'editorial-plan-{version}.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'output': str(final), 'duration_seconds': duration, 'frames': frames}, ensure_ascii=False))
