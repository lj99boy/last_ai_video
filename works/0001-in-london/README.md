# 0001 · 在伦敦（来源画作；短片片名待定）

> **最新 film-v04 制作中，未完成**：S003F首尾帧样片因披肩动作反向被用户否决。最新要求是以回原画的尾帧为标准倒推动作；ending-v06直接从原始照片里的画面退回墙上，取消AI仿画溶解，已渲染无声结尾组件，动态相接尚未验证。已核实余额92积分；报价已归档，新付费执行关闭，追加100元/1500积分的资金决定等待用户答复。入场覆肩候选arrival03与末镜起止帧已备齐，下一步动态验证依赖资金决定。见[本轮记录](production/film-v04/review.md)、[剩余制作与预算](production/film-v04/remaining-production-plan.md)。

> film-v03 历史：首个有声审看片已收到四项修订反馈，尚未定稿。正在改运镜/接镜、原画胸花与帽发；已归档用户提供的《Young and Beautiful》原版；41.5秒候选因开头突兀撤下，新增15秒前奏入场试听C。见[本轮方案与实际进度](production/film-v03/revision-plan.md)。

> 首片历史记录：35.5秒完整有声审看片已输出，未定稿、未发布。采用回溯早期参考后的film-v02素材，上一轮密集碎点视觉版本已撤下。见[成片与限制](production/film-v02/review.md)。

- 顺序：餐厅与专业服务→窗外/门外→女主完整登场→目光/松手→鬓边姿态→无黑边回墙。
- 文件：`media/exports/film-v01/in-london-first-film-with-audio.mp4`；1280×720、24fps、双声道音轨。
- 音乐、原生环境声已混音；全解码、帧数、音轨、边缘信号与响度检查通过。真人听感与审美待用户审阅。
- 已知限制：部分窗边/木饰面仍有碎亮纹理；衣装肩部新增装饰与回画时的身份/帽形变化仍需评议，不算定装完成。
- [剪辑表](post/film-v01-edit.csv) / [渲染脚本](post/render-film-v01.py) / [质检](production/film-v02/final-qc.json) / [经验](../../docs/paint-texture-review-2026-10-12.md)。
- 此次完整片推进：12次视频与1次音乐生成；无充值、新订阅或自动重试，实际积分未知。此前6次试拍保留历史。
- 更新：2026-10-12。

## 先读这里

1. [当前整体提案 v0.9](development/proposal-v0.9.md)：空间、动作与切点依据；[v0.8](development/story-assessment-v0.8.md)保留故事调研；[v0.4](development/proposal-v0.4.md)保留历史。
2. [画作考据与观察](development/research.md)：证据、解读、虚构分开。
3. [创作简报](development/brief.md) / [故事版本](development/story.md)。
4. [视觉设定](preproduction/visual-bible.md) / [分镜表](preproduction/shots.csv)。
5. [试拍与成本计划](production/test-plan.md) / [当前执行意图](production/prompts-v0.9.md)。
6. [素材清单](production/manifest.csv) / [生成记录](production/runs.csv)。
7. [当前剪辑表](post/film-v01-edit.csv) / [声音设计历史](post/sound.md) / [交付](delivery/README.md)。
8. [决策与推进记录](development/decisions.md)。
9. [V001 首张探索板与自检](production/V001-review.md)。
10. [R002 正视参考处理](production/R002-review.md) / [CLI 接入与画布](production/libtv-connection.md)。
11. [回墙 A/B 预演与自检](post/ending-preview-v02.md)。
12. [最新关键帧与无黑边结尾](production/keyframes-v01-review.md)。
13. [首批运动试拍与前14秒粗剪](production/motion-test-review-v01.md)。
14. [导演修订讨论稿 v0.5](development/directing-revision-v0.5.md)：对沉闷的诊断、学习来源和低成本对照计划。
15. [情节与表演探索 v0.6](development/emotional-story-v0.6.md)：三个微事件候选、画风取舍与最小验证。
16. [v0.7四格与自检](production/visual-study-v07-review.md)：V003当前候选；V002撤回主题仅归档。
17. [故事感复核 v0.8](development/story-assessment-v0.8.md)：扩展案例调研、叙事缺口与披肩微事件；用户同意继续验证。
18. [V004与30秒预演自检](production/visual-study-v08-review.md)：上一版动作测试与未解决问题。
19. [V005与当前整体预演自检](production/visual-study-v09-review.md)：窗外—门槛—餐厅；时长由内容决定。

20. [服装回溯修正](production/costume-correction-v01.md)：原作优先，保留新镜头，同步修正空间板与动作板。

21. [逐镜运镜方案v01](preproduction/camera-plan-v01.md)：起止构图、路径、停点与试拍顺序；[来源研究](../../docs/camera-research-2026-10-12.md)。

22. [独立起帧与CLI草稿自检](production/camera-keyframes-v01-review.md)：K00303、K005A01；T04/T05各5秒配置，未运行。

23. [运镜试拍结果与诊断粗剪](production/camera-motion-review-v01.md)：历史运镜试拍；平台完成与动作验收分开。

## 当前下一步

已收到整片反馈，按film-v03修订人物造型、运镜与接镜，并校听原版歌曲选段；不把旧首片交付为最终定稿。具体问题和验证范围见[成片审查](production/film-v02/review.md)。以下旧版预演入口均保留历史，不代表当前采用。

## 本地素材与原始参考

用户上传的 8064×6048 原图已原样保存为 `media/references/R001-user-photo-original.jpg`，指纹见 [来源记录](production/source-asset.json)。原始本地文件未裁切、未修复，已作为来源素材上传 LibTV；未上传 GitHub，媒体需独立备份。AI 正视编辑另存 R002，不覆盖原片。

此前[列宾视频](https://www.xiaohongshu.com/explore/6ab3cf5a0000000012035c3e)仅作为“从画面扩展故事”的效果参考，本作品有独立的主题、节奏与结尾。
