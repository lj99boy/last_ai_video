# last_ai_video

从一幅画或一个画面出发，共同创作故事短片的工作仓库。

名画解读、主题、故事与分镜由创作者和 Codex 共同讨论；生成工具执行已确定的镜头方案。以完成作品、保留表达与修改空间为目标。

## 目录

```text
docs/                    通用流程、工具选型与调研依据
templates/work/          新作品模板，复制后独立使用
works/                   作品索引与各作品目录
  0001-in-london/        首作：《在伦敦》延展短片《偷来半支舞》
    development/        解读、主题、故事
    preproduction/      视觉参考、分镜
    production/         素材清单、生成与费用记录
    post/               剪辑表、声音设计
    delivery/           定稿与交付说明
    media/              本地图片、视频、声音和工程文件
```

## 从这里开始

- [作品索引](works/README.md)
- [第一部作品](works/0001-in-london/README.md)
- [整体流程与分工](docs/workflow.md)
- [画作到故事：当前制作方法](docs/painting-to-story-playbook.md) / [首作完整复盘](works/0001-in-london/delivery/retrospective-2026-10-13.md)
- [工具费用与操作记录](docs/libtv-costs-and-operations.md)
- [创作实践记录](docs/practice-notes.md)
- [导演方法公开调研](docs/directing-research-2026-10-11.md) / [导演检查表](docs/directing-review.md)
- [仓库协作约定](AGENTS.md)

历史资料：[早期工具调研](docs/tooling.md)、[调研依据](docs/research.md)、[列宾参考短片画面复核](docs/reference-repin-screen-review-2026-10-12.md)。这些记录保留当时的判断，当前制作请从上面的作品与方法入口开始。

## 实际使用

1. 新作品：复制 [作品模板](templates/work/README.md) 到一个未使用的作品目录，例如 `works/0002-short-name/`；填写创作简报和一页制作卡，再登记作品索引。
2. 查看首作：v03 已交付，制作记录与复盘已归档；成片说明和已知问题见[作品入口](works/0001-in-london/README.md)。
3. 检查仓库：运行 `python3 tools/check_repository.py`。恢复本地媒体后可加 `--media` 核对 v03 素材指纹；步骤见[本地重建说明](works/0001-in-london/delivery/reproduce-v03.md)。

检查脚本仅依赖 Python 标准库。媒体重建需要 FFmpeg 及原始文件，具体依赖与命令见重建说明。

Git 保存文本、提示词、镜头表与素材索引。`media/` 中的原始素材、生成结果、剪辑工程和成片默认仅存本地，需要独立备份；GitHub 上看到目录不代表素材已上传。
