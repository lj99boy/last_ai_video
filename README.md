# last_ai_video

从一幅画或一个画面出发，与 Codex 共同创作故事短片的工作仓库。名画解读、主题、故事与分镜由创作者和 Codex 共同讨论；生成工具执行已确定的镜头方案。

仓库分三层。**做新作品只需要第一层**；第二层是具体作品，第三层只用于追溯。

## 1. 能力层：现在怎样做

| 何时读 | 文件 |
| --- | --- |
| 开工、每个阶段开始时 | [制作经验入口](docs/production-lessons.md)：六个时机各自要问的问题，链接到具体案例 |
| 准备付费生成前 | [当前执行平台](docs/execution-platform.md)：即梦 CLI、授权方式、已观察到的入口条件 |
| 安排分工与阶段 | [整体流程与分工](docs/workflow.md) |
| 设计故事、镜头与表演 | [画作到故事制作方法](docs/painting-to-story-playbook.md)、[导演检查表](docs/directing-review.md) |
| 组织参考素材与段落 | [参考驱动的制作](docs/reference-production.md)、[参考流水线工具](tools/README-reference-pipeline.md) |
| 开新作品 | [作品模板](templates/work/README.md)，其中[一页制作卡](templates/work/preproduction/production-readiness.md)记录每轮短结论 |

代理协作规则见 [AGENTS.md](AGENTS.md)。制作中的关键决定由 [制作检查点 Skill](.agents/skills/production-checkpoint/SKILL.md) 触发对应检查（Codex 中可用 `$production-checkpoint` 显式调用）。

## 2. 作品层：做过什么

[作品索引](works/README.md)列出每部作品的状态。每部作品的 README 顶部只保留一份当前状态。

| 作品 | 状态 | 公开内容 |
| --- | --- | --- |
| [0002 列宾《回信》](works/0002-zaporozhian-reply/README.md) | 125.5 秒 V44 完整候选，未定稿、未发布 | 当前状态、故事、[制作复盘](works/0002-zaporozhian-reply/delivery/retrospective-2026-10-29.md)（L01–L12 案例）；完整执行目录和媒体只在本地 |
| [0001《在伦敦》→《偷来半支舞》](works/0001-in-london/README.md) | v03 已交付并收束，未发布 | 完整文本记录与[复盘](works/0001-in-london/delivery/retrospective-2026-10-13.md)；媒体只在本地 |

## 3. 归档层：当时怎样判断

[docs/history/](docs/history/README.md) 保存带日期的调查、旧平台（LibTV）的费用与操作记录、按日期的实践记录。作品目录里带版本号的过程文件同样属于历史。这些文件里的“当前”“下一步”只指当时。

## 检查

```sh
python3 tools/check_repository.py           # 链接、CSV 表头、JSON/Python 语法、本机路径
python3 -m unittest discover -s tests       # 参考流水线工具
```

只依赖 Python 标准库。恢复首作本地媒体后，可加 `--media` 核对 v03 素材指纹，见[本地重建说明](works/0001-in-london/delivery/reproduce-v03.md)。

Git 只保存文本、提示词、镜头表、脚本与素材索引。原始素材、生成结果、剪辑工程和成片默认只存本地；GitHub 上看到 `media/` 目录不代表素材已上传。
