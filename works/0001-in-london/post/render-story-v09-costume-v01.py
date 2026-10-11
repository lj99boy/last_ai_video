"""将已有动作板与片段排成无声分镜预演；不生成角色动作，不改写来源图片。"""
import hashlib
import json
import subprocess
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
OUT = WORK / 'media/exports/story-v09-costume-v01'
OUT.mkdir(parents=True, exist_ok=True)
BOARD = 'media/stills/V006-costume-spatial-v01.png'
# 每段时长来自当前预演的观看任务，可独立调整；总长是相加结果，不是填满指标。
SEGMENTS = [
    ('S001', 'media/stills/K001-restaurant-v01.png', 3, None, None),
    ('S002', 'media/clips/S002_take01.mp4', 3, None, 1),
    ('S007', BOARD, 2, 'crop=828:460:4:4', None),
    ('S008', BOARD, 4, 'crop=828:460:840:4', None),
    ('S003', BOARD, 5, 'crop=828:460:4:476', None),
    ('S004', 'media/stills/V007-costume-action-v01.png', 2, 'crop=828:460:840:4', None),
    ('S005a', 'media/stills/V007-costume-action-v01.png', 3, 'crop=828:460:4:476', None),
    ('S005b', BOARD, 6, 'crop=828:460:840:476', None),
    ('S006', 'media/exports/ending-v04/A-slow-reveal-fullbleed.mp4', 6, None, 0),
]
EXPECTED_DURATION = sum(segment[2] for segment in SEGMENTS)

records = []
timeline = 0
for shot, source, duration, crop, start in SEGMENTS:
    src = WORK / source
    assert src.is_file(), src
    dest = OUT / f'{shot}.mp4'
    args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y']
    if start is None:
        args += ['-loop', '1', '-framerate', '24']
    else:
        args += ['-ss', str(start)]
    args += ['-i', str(src)]
    filters = ([crop] if crop else []) + [
        'scale=1280:720:force_original_aspect_ratio=increase:out_range=tv:out_color_matrix=bt709',
        'crop=1280:720', 'setsar=1', 'fps=24', 'format=yuv420p',
        'setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709',
    ]
    args += ['-vf', ','.join(filters), '-t', str(duration), '-an', '-c:v',
             'libx264', '-preset', 'fast', '-crf', '19', '-color_range', 'tv',
             '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
             '-movflags', '+faststart', str(dest)]
    subprocess.run(args, check=True)
    records.append(dict(shot=shot, source=source, start_s=timeline, duration_s=duration,
                        evidence='held_storyboard_frame' if start is None else
                        ('existing_generated_motion' if shot == 'S002' else 'existing_local_composite'),
                        source_in_s=start, crop=crop))
    timeline += duration
assert timeline == EXPECTED_DURATION
listing = OUT / 'concat.txt'
listing.write_text(''.join(f"file '{shot}.mp4'\n" for shot, *_ in SEGMENTS))
output = OUT / 'story-v09-costume-v01-silent-animatic.mp4'
subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat',
                '-safe', '0', '-i', str(listing), '-c', 'copy', '-movflags', '+faststart', str(output)], check=True)
probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames',
                   '-show_entries', 'stream=codec_type,width,height,r_frame_rate,nb_read_frames:format=duration',
                   '-of', 'json', str(output)]))
assert len(probe['streams']) == 1 and probe['streams'][0]['codec_type'] == 'video'
assert int(probe['streams'][0]['nb_read_frames']) == EXPECTED_DURATION * 24
assert abs(float(probe['format']['duration']) - EXPECTED_DURATION) < .05
subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(output), '-f', 'null', '-'], check=True)
# 视频接触表用于检查剪辑取景、末帧和边缘，不重绘图片。
subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(output),
                '-vf', 'fps=1/3,scale=384:216,tile=4x3', '-frames:v', '1', str(OUT/'contact.jpg')], check=True)
report = dict(output=str(output.relative_to(WORK)), duration_s=EXPECTED_DURATION, audio='none',
              motion_generated_this_run=False, held_still_seconds=sum(duration for _, _, duration, _, start in SEGMENTS if start is None),
              sha256=hashlib.sha256(output.read_bytes()).hexdigest(), probe=probe, segments=records)
(WORK/'post/story-v09-costume-v01-render.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
