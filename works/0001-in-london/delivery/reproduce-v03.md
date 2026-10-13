# v03本地恢复与重建

本页对应本轮收束的《偷来半支舞》v03。所有命令从仓库根目录运行，只做本地文件检查和剪辑，不调用LibTV、不生成新人物、不消费积分。

## Git能恢复什么

克隆仓库即可阅读故事、复盘、提示词、实际剪辑参数和费用证据，也能复制模板开始新作品。媒体和账户状态没有随Git上传，不能仅凭克隆重新得到视频。

从自己保存的媒体副本恢复到 `works/0001-in-london/media/`。本仓库尚未登记已验证的独立备份位置；找不到原素材时应先寻找备份，不直接运行历史生成脚本。

[媒体指纹清单](media-manifest-v03.json)记录6个剪辑必需输入、3个进一步复建用原始输入和1个既有成片。路径均相对于作品根目录，包含字节数与SHA-256。最低输入为：

| 作品相对路径 | 用途 |
| --- | --- |
| `media/clips/film-v05/S001K_take01.mp4` | 开场服务及环境声音 |
| `media/clips/film-v06/whole-film-A-v02_take01-original.mp4` | 原速邀请、舞步、表情 |
| `media/clips/film-v06/whole-film-B-v03_take01-painting-join.mp4` | 入场、先遮后露、抬手与短转画 |
| `media/previs/half-dance-v01/ending-first.png` | 准确原画接点 |
| `media/exports/ending-v08/original-painting-to-wall.mp4` | 4.625秒准确原画显框 |
| `media/audio/film-v03/young-and-beautiful-user-source.mp3` | 用户指定原曲源文件 |

这份最小清单只够重建最终剪辑；继续修改人物和参考仍需完整 `media/` 档案。音乐等源文件的权利状态不由指纹或Git克隆改变。

## 依赖与检查

- Python 3.9或更新版本，主剪辑路径只使用标准库。
- PATH中可用的FFmpeg及ffprobe，支持libx264、AAC、mov_text、所用视频/音频滤镜。本机验证版本记录见[仓库验证记录](repository-check-2026-10-13.md)，不保证不同版本逐字节一致。
- 历史三维排演另外需要Blender、Pillow和字体；它是研究记录，不是重建v03的前置步骤。

```sh
python3 tools/check_repository.py
python3 tools/check_repository.py --media
```

第一条验证Git文本、JSON、CSV、Python语法及非媒体本地链接；缺少不随Git分发的媒体不算文本仓库错误。第二条要求6个剪辑输入存在且指纹一致；可选归档素材若存在也核对指纹，不会下载或重建。

## 重建完整剪辑

输出目录应为空或尚未存在。指定独立目录使视频和新报告均离开历史制作目录，已有输出不会被覆盖。

```sh
python3 works/0001-in-london/post/render-editorial-v05.py \
  --production film-v06 --plan whole-film-v03-editorial.json \
  --version 3 --output-dir /tmp/in-london-v03-rebuild

ffmpeg -n -hide_banner -loglevel error \
  -i /tmp/in-london-v03-rebuild/whole-film-structure-v03.mp4 \
  -map 0:v:0 -map 0:a:0 -c copy -sn -map_metadata -1 -movflags +faststart \
  /tmp/in-london-v03-rebuild/in-london-half-dance-v03.mp4
```

第一步根据真实剪辑计划重建，并检查760帧、1280×720、双声道及完整解码；内部审查字幕为独立可移除轨。第二步保留视频和音频、去掉审查字幕，得到干净MP4。重建不重新验收美术，也不代表1080P或已发布。

## 可选：从更原始输入重做局部后期

如果缺少处理过的B，但持有原始B及 `ending-first.png`，先恢复原始输入，再执行以下命令。`-n`禁止覆盖；该处理只复现已交付短转画，不产生新动作。

```sh
ffmpeg -n -hide_banner -loglevel error -filter_complex_threads 2 \
  -i works/0001-in-london/media/clips/film-v06/whole-film-B-v03_take01.mp4 \
  -loop 1 -framerate 24 -i works/0001-in-london/media/previs/half-dance-v01/ending-first.png \
  -filter_complex '[0:v]trim=end_frame=288,setpts=PTS-STARTPTS,format=yuv420p[b];[1:v]format=yuva420p,fade=t=in:st=11.75:d=0.208333333:alpha=1[p];[b][p]overlay=shortest=1:format=auto,format=yuv420p[out]' \
  -map '[out]' -frames:v 288 -r 24 -an -c:v libx264 -crf 18 -preset medium -movflags +faststart \
  works/0001-in-london/media/clips/film-v06/whole-film-B-v03_take01-painting-join.mp4
```

如果缺少显框视频，但持有原始展厅照片和侧墙扩展图，可运行 `python3 works/0001-in-london/post/render-ending-original-v08.py`。它输出 `media/exports/ending-v08/`，已存在则拒绝覆盖。更换FFmpeg版本可能改变编码指纹，应另记来源和技术检查结果，不能静默改旧指纹来使检查通过。

历史 `production/**/execute.py`、节点UUID、提示词和旧授权是生产证据，不是恢复素材命令。它们可能上传、创建节点或消费积分，不用于这份本地重建流程。
