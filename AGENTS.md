# 协作约定

## 推进基准

- 本工作目录和对应 GitHub 仓库是资料与推进记录的基准。每次继续工作先读取仓库现状、作品记录和 Git 状态，不把聊天中的旧结论当作当前状态。
- 将已确认的创作决策、工具验证结果、进度与下一步写回对应文档；具体作品记录保存在该作品目录。
- 汇报时区分本地变更、本地提交与已同步远端的提交。推送失败或认证未完成时明确标注未同步，不把本地完成说成远端完成。

## Git 身份与远端

- 仅使用公网 GitHub 账号 `lj99boy` 与 `lj99boy/last_ai_video` 交互。禁止使用公司内网账号、邮箱、SSH 密钥或公司 Git 远端。
- 每次远端写入前核实实际认证账号；设置 `user.name` 不等于完成 GitHub 认证。连接器需用 profile/login 接口核实，CLI 需核实实际 GitHub 登录身份。
- 每个新克隆设置仓库级身份：

  ```sh
  git config --local user.name lj99boy
  git config --local user.email 17543124+lj99boy@users.noreply.github.com
  git config --local user.useConfigOnly true
  git config --local commit.gpgsign false
  git config --local credential.helper ''
  git config --local credential.https://github.com.username lj99boy
  git config --local credential.https://github.com.useHttpPath true
  ```

- 用 `git var GIT_AUTHOR_IDENT`、`git var GIT_COMMITTER_IDENT`、`git remote -v` 检查有效配置。发现环境变量覆盖身份或远端 URL 改写时先纠正；不沿用不明认证方式。
- 不修改全局 Git 身份。上述配置清空继承的凭据助手，后续如需 CLI 推送，单独建立并验证 lj99boy 的公网认证；不要为了方便恢复公司凭据。
- 不提交密钥、令牌、账户配置、含鉴权参数的分享链接或公司内部资料。当前仓库为公开仓库。

## 创作与执行

- 解读、主题、故事、分镜由创作者与 Codex 共创。史实、作品解读和虚构情节分开记录。
- 生成工具执行已讨论的方案；不要自动重写主题、人物动机或结局。常规整理、参数配置与问题诊断可自主完成。
- 工具建议、官方宣称、第三方经验、账户接通、本机测试、付费生成实测分别记录，不混写成“已验证”。
- 当前新增创作工具预算为每月人民币 100 元以内，不含已有 Codex 订阅；预算约束不等于已授权订阅、付费生成或发布。复用会话中已有的明确授权，不重复询问。
- 先静帧预演，再试拍代表镜头，再制作全片。失败时先定位故事、图像、动作或剪辑问题，避免无依据重复生成。
- 成片是否定稿、是否发布由创作者决定。

## 文件与素材

- 通用方法放 `docs/`；作品内容放 `works/<编号>-<短名>/`；不把具体作品决策回填为所有作品的规则。
- 新作品复制 `templates/work/`，并更新 `works/README.md`。首片未选题时保持待定，不根据参考视频擅自确定题材。
- 镜号用 `S001`，候选用 `S001_take01`。保留已选和被替换版本，不覆盖原始素材。
- `media/` 默认被 Git 忽略。素材清单记录相对路径、用途、来源、模型与选用状态；需要跨机器协作时再决定备份或大文件存储方案。
- 模型权重、缓存、生成媒体和剪辑工程不直接进入普通 Git。工作流 JSON、字幕 SRT、剪辑 CSV 等文本文件可放在相应阶段目录。
- 文档变更检查链接、模板结构与 CSV 表头即可；不要为目录初始化引入应用框架或复杂测试系统。

## 重复性调查的复用

- 费用、工具能力、操作入口及失败处理先查 `docs/libtv-costs-and-operations.md`、`docs/practice-notes.md` 和作品执行记录，不重复已完成调查。
- 新事实记录适用条件、日期、来源与验证边界；模型/参数/权益变化、证据矛盾或实际扣费需要时，仅定向更新相关报价/余额。历史报价不等于当前扣费，未知值不要推算成已验证事实。
