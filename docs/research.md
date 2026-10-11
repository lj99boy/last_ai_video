# 调研依据

整理于 2026-10-11。以下是公开证据索引，不是我们已完成的模型测评。没有足够证据证明某个平台对所有名画叙事最优。

| 来源 | 类型 | 可借鉴内容与限制 |
| --- | --- | --- |
| [Art Awakens 制作方公告](https://fremantle.com/news/imaginae-studios-announces-debut-project-art-awakens) | 制作方一手资料 | 名画情绪世界扩展为短片的实际项目 |
| [Art Awakens 导演访谈](https://runway.com/customers/how-fremantle-is-bringing-the-worlds-greatest-artworks-to-life-with-runway) | 厂商客户访谈 | 概念→图片→视频，选帧继续生成；不能据此证明 Runway 优于其他模型 |
| [长期创作复盘](https://www.reddit.com/r/aifilmmaking/comments/1v7hm7e/everything_ive_learned_after_1_year_of_ai/) | 创作者自述 | 面部、全身、服装、状态、场景应有明确参考，各参考各司其职 |
| [分镜图约100次实验](https://www.reddit.com/r/aivideomaking/comments/1vps8pb/after_100_tests_these_are_the_things_that/) | 产品开发者自述及讨论 | 人物一致、镜头多样性、宫格布局是不同问题；统计不可当作通用成功率 |
| [可灵主体库指南](https://kling.ai/quickstart/klingai-element-library-3-user-guide) | 官方文档 | 多角度主体参考；平台接入不一定暴露全部原生能力 |
| [Nano Banana Pro 提示指南](https://blog.google/products-and-platforms/products/gemini/prompting-tips-nano-banana-pro/) | 官方文档 | 为参考图指定人物、姿态、背景等角色；不保证绝对一致 |
| [LibTV 官网](https://www.liblib.tv/) | 官方产品与会员页面 | 2026-10-10核查月付与额度，购买前仍需刷新 |
| [LibTV Plugin](https://www.liblib.tv/plugin) / [分发仓库](https://github.com/liblib-ai/marketplace) | 官方接入文档 | Codex Plugin 与 OAuth；本项目尚未接通 |
| [旧版提示词改写 issue](https://github.com/libtv-labs/libtv-skills/issues/12) | 用户附输入/输出的反馈 | 2026-05-20提出，核查时仍 Open；只说明旧会话接口报告，不直接外推新版插件 |
| [LibTV 实操体验](https://elsewhere.news/zh/crossing/libtv) | 带产品推广内容的媒体实操 | 参考引用与片段重拍，非独立横向基准 |
| [OiiOii CLI](https://www.npmjs.com/package/@oiioii/cli) | 软件包文档 | 生成、任务和积分命令；本地未验证 |
| [MOMENTS 制作复盘](https://huggingface.co/datasets/Cseti/ComfyUI-Workflows/blob/main/posts/2026-03-30-moments-short-film/README.md) | 作者作品与工作流 | 开源生图/动画后仍有局部修复和剪辑环节，不等于首片总成本最低 |
| [Comfy MCP](https://github.com/Comfy-Org/comfy-mcp) | 官方项目 | 工作流运行与任务管理，标注 beta；本地尚未接入 |
| [Runway 套餐](https://runway.com/pricing) | 官方价格 | 月付和年付折算不同；功能与额度按账户核验 |
| [剪映专业版](https://www.jianying.com/web/professional) | 官方产品 | 可视剪辑入口，不代表全部功能免费或有稳定自动化 API |

## 首轮测试建议

同一角色的两个景别静帧，加一个情绪镜头与一个动作镜头。先比较参考一致性，再对照 Kling 3.0 与 Seedance 2.0 的有效视频、重试与总消耗，最后导入剪辑工具验证闭环。尚未授权或执行付费测试。

记录原始输入、模型和参数、实际输出、费用、缺陷和选用原因，允许结论推翻当前工具候选。
