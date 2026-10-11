# last_ai_video

从一幅画或一个画面出发，共同创作故事短片的工作仓库。

名画解读、主题、故事与分镜由创作者和 Codex 共同讨论；生成工具执行已确定的镜头方案。以完成作品、保留表达与修改空间为目标。

## 目录

```text
docs/                    通用流程、工具选型与调研依据
templates/work/          新作品模板，复制后独立使用
works/                   作品索引与各作品目录
  0001-untitled/         第一部作品占位，尚未选题
    development/        解读、主题、故事
    preproduction/      视觉参考、分镜
    production/         素材清单、生成与费用记录
    post/               剪辑表、声音设计
    delivery/           定稿与交付说明
    media/              本地图片、视频、声音和工程文件
```

## 从这里开始

- [作品索引](works/README.md)
- [第一部作品](works/0001-untitled/README.md)
- [整体流程与分工](docs/workflow.md)
- [第一版工具选型](docs/tooling.md)
- [调研依据](docs/research.md)
- [仓库协作约定](AGENTS.md)

新作品从 `templates/work/` 复制到 `works/0002-short-name/`，更新作品 README 和索引。作品编号稳定，标题可随创作调整。

Git 保存文本、提示词、镜头表与素材索引。`media/` 中的原始素材、生成结果、剪辑工程和成片默认仅存本地，需要独立备份；GitHub 上看到目录不代表素材已上传。

## Git 身份

本仓库只使用公网 GitHub 账号 **lj99boy**。本地提交身份使用 `lj99boy` / `17543124+lj99boy@users.noreply.github.com`，仅设置仓库级配置，不修改全局身份。其他机器克隆后也需重新设置并核实，详见 [AGENTS.md](AGENTS.md)。
