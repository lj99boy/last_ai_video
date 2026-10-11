"""用现有静帧渲染回墙剪辑预演；不调用模型、不重绘来源图片。"""
import json
import subprocess
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
OUT = WORK / 'media/exports/ending-v04'
OUT.mkdir(parents=True, exist_ok=True)
PHOTO = WORK / 'media/references/R001-user-photo-original.jpg'
PAINTING = WORK / 'media/references/R002-front-painting-ai-v01.png'
WALL = WORK / 'media/references/P006-wall-extension-ai-v02.png'
FPS, WIDTH, HEIGHT = 24, 1280, 720


def solve(matrix, values):
    """小型线性方程求解，仅计算视频透视参数，不处理图像像素。"""
    a = [list(row) + [value] for row, value in zip(matrix, values)]
    for col in range(len(a)):
        pivot = max(range(col, len(a)), key=lambda row: abs(a[row][col]))
        a[col], a[pivot] = a[pivot], a[col]
        divisor = a[col][col]
        if abs(divisor) < 1e-10:
            raise ValueError('画作四角退化，不能计算透视')
        a[col] = [value / divisor for value in a[col]]
        for row in range(len(a)):
            if row != col:
                factor = a[row][col]
                a[row] = [x - factor * y for x, y in zip(a[row], a[col])]
    return [row[-1] for row in a]


# 手动观察原片四角，坐标以 1824×1368 查看图为基准；不是测绘结果。
# 先将原片等比缩至 960×720，再居中置于 1280×720 视频画布。
corners = [(214, 219), (1544, 158), (222, 1082), (1527, 1133)]
source = [(160 + x * 960 / 1824, y * 720 / 1368) for x, y in corners]
# 起点为更近的满幅画中取景，随后退至完整画框；全程不拉伸人物。
target = [(0, -40), (1280, -40), (0, 720 * 1280 / 1080 - 40), (1280, 720 * 1280 / 1080 - 40)]
matrix, values = [], []
for (x, y), (u, v) in zip(source, target):
    matrix += [[x, y, 1, 0, 0, 0, -u*x, -u*y],
               [0, 0, 0, x, y, 1, -v*x, -v*y]]
    values += [u, v]
h = solve(matrix, values)


def transform(x, y):
    denominator = h[6]*x + h[7]*y + 1
    return ((h[0]*x+h[1]*y+h[2])/denominator,
            (h[3]*x+h[4]*y+h[5])/denominator)


full = [(0, 0), (WIDTH, 0), (0, HEIGHT), (WIDTH, HEIGHT)]
start = [transform(x, y) for x, y in full]
# 1.6–4.8 秒从正视画面退到原始展厅照片；两端速度为零。
u = 'clip((on/24-1.6)/3.2,0,1)'
ease = f'(({u})*({u})*(3-2*({u})))'
coords = []
for i, (a, b) in enumerate(zip(start, full)):
    for axis, pos in [('x', 0), ('y', 1)]:
        coords.append(f"{axis}{i}='{a[pos]:.9f}+({b[pos]-a[pos]:.9f})*{ease}'")
perspective = 'perspective=' + ':'.join(coords) + ':sense=destination:eval=frame:interpolation=cubic'


def render(name, graph):
    output = OUT / (name + '.mp4')
    if output.exists():
        raise FileExistsError(f'保留已有版本，请换输出目录：{output}')
    graph_file = OUT / (name + '.ffmpeg.txt')
    graph_file.write_text(graph)
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-filter_complex_threads', '2',
        '-i', str(PHOTO), '-i', str(PAINTING), '-i', str(WALL), '-filter_complex_script', str(graph_file),
        '-map', '[out]', '-t', '6', '-r', str(FPS), '-an', '-c:v', 'libx264',
        '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
        str(output)], check=True)
    print(output, flush=True)


# 只用 AI 扩展图的两侧墙面；中央画作与金框始终叠回真实来源照片；画外展签区域不纳入。
# 原片边缘柔化仅涉及墙面，以缓和生成墙面与真实照明的接缝。
photo = '[0:v]scale=960:720,setsar=1,loop=loop=-1:size=1:start=0,setpts=N/(24*TB),fps=24,format=yuva444p'
wall = '[2:v]scale=1280:720,setsar=1,loop=loop=-1:size=1:start=0,setpts=N/(24*TB),fps=24,format=yuv444p'
painting = '[1:v]scale=1280:-2,crop=1280:720:0:40,setsar=1,loop=loop=-1:size=1:start=0,setpts=N/(24*TB),fps=24'

render('A-slow-reveal-fullbleed', ';'.join([
    wall+'[wall]',
    photo+",geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':a='255*clip(min(X/60,(868-X)/7),0,1)'[original]",
    '[wall][original]overlay=x=160:y=0:shortest=1:format=auto,format=yuv444p,'+perspective+'[base]',
    painting+',format=yuva420p,fade=t=out:st=1.1:d=0.4:alpha=1[front]',
    '[base][front]overlay=shortest=1:format=auto,format=yuv420p[out]']))

(OUT/'render-metadata.json').write_text(json.dumps({
    'duration_seconds': 6, 'fps': FPS, 'size': [WIDTH, HEIGHT], 'audio': False,
    'inputs': ['R001', 'R002', 'P006'], 'kind': 'static_image_editing_previsualization',
    'painting_corners_observed_at_1824x1368': corners,
    'limitations': ['K005人物落点尚不存在，R002仅作替身', '无人物运动、声音和整片上下文',
                    '两侧墙面AI扩展，中央原画和画框覆盖;画外展签移除；开头近景允许裁切，末端保留完整画框', '起始3:2为近似比例，不是原作尺寸考证']
}, ensure_ascii=False, indent=2)+'\n')
