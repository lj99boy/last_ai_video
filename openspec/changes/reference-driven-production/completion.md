# 本次交付与需求核对

2026-10-17时点说明：下表为首次本地重建交付时的证据快照，原78秒／1060／450未执行均已成为历史。当前作品以作品当前入口（本地记录 `production/README.md`）为准，后续一致性与次数边界复核见tasks第4节；旧表不授予当前执行或消费权限。

首次交付记录：本次目标是设计和开发合理使用多参考能力的整片流程、资源与策略；本地重建完成。后续真实视频和完整成片制作属于作品继续推进，不以本地实现冒称动态效果通过。

| 需求 | 实际证据 | 验证边界 |
| --- | --- | --- |
| 行动/观看任务先行，全片覆盖 | [通用流程](../../../docs/reference-production.md)、实际14段plan（本地记录 `production/reference-v01/plan.json`）、20行导演/镜表/视角/后期同步 | 0—78连续、20节拍恰一次；观看段非生成配额 |
| 参考分工与实际资源 | registry（本地记录 `production/reference-v01/registry.json`）、新P0实物记录（本地记录 `production/reference-v01/asset-generation.json`）、D实物（本地记录 `production/reference-v01/D-blocking-review.md`） | 33资源含来源/缺口/可选，17现有媒体指纹核对；三身份+空车+D实看；其余按后续使用补 |
| 多参考/Element工具实现 | [源码](../../../tools/reference_pipeline.py)、[说明](../../../tools/README-reference-pipeline.md)、[40测试](../../../tests/test_reference_pipeline.py) | 标准库、小工具，无云服务；普通/-O均40通过；实际CLI只本地dry-run |
| 完整读回和接口合同 | 本地multi/Element（本地记录 `production/reference-v01/local-cli-dry-run.json`）、真实排序证据（本地记录 `production/reference-v01/local-cli-order-contract.json`） | 模拟故障+官方local语法；无新增实际上传/Element/核价/生成 |
| 批准与消费保留 | 迁移（本地记录 `production/reference-v01/migration.json`）、不可变保护（本地记录 `production/reference-v01/historical-protection.json`）、实际差额（本地记录 `production/reference-v01/authorization-delta.json`） | 1060历史账本/原450保留；旧2上传4写90/144价run0；新5资料未上传，旧价不适用 |
| 独立复核与诚实状态 | 实际导演/美术复核（本地记录 `production/reference-v01/independent-review.md`）、工具复核（本地记录 `production/reference-v01/execution-review.md`）、综合验证（本地记录 `production/reference-v01/validation.json`） | 两类复核通过；P2排序已修；受力/活人感/原速声画/成片接受仍待真实作品 |

保留取舍：A宽仅2项、C接回4项、D承重6项，都是本段信息需要；不强制Element、三视图、每镜图或全片重拍；不重复使用带晚年人物的F006整图作通用style；不赌C末帧产D。原画群体从47秒在场、两秒愤慨、五秒群笑、完整金框墙及自然俄语/双语字幕不变。

根AGENTS已覆盖引用职责、实际输入一致性、累计成本和不可自动扩大批准，无需将本片具体规则加入通用协作约定。原始媒体、字幕、批准和回执保留。当前本地变更未提交/推送，无发布。


## 2026-10-17 当前链复核补充

当前设计统一68秒／战斗3+2+2+6及长车营；复核记录（本地记录 `production/cinema-reset-v01/consistency-audit-20261017.md`）与验证结果（本地记录 `production/cinema-reset-v01/consistency-validation-20261017.json`）为本次证据。旧表保持首次交付时点，不再承担当前运行指令。

当前入口、导演／视觉／年代／场面／声音、plan和三CSV已对齐；234个审计前历史／源文件、32份逐字快照指纹保留。主音源原为Milena而非Piper，已纠正并独立测量两套17段原WAV；仅证明1x装槽，不称原生声音或演技通过。旧冻结period-v02的接手前漂移单列，不改旧合同hash。

新增执行守卫阻断退休计划、同一批准换根／账本、旧快照遗失unknown上传等路径；canonical原root／state与asset身份进度进入本机权威记录。普通与-O各67项：66实际通过、1项官方本地dry-run在本轮runner跳过；独立复核四项原复现与新增13项Fake两模式全过，无剩余阻断项。旧事务不自动迁移，历史只读仍可用。

本轮新增图片、视频、上传、云写与积分均0，历史累计1438不变。新环境、缓坎、正式请求及整片实际声画仍待制作／验收；当前无新增执行权，未提交／推送或发布。

## 2026-10-19 历史云入口退休补漏

本节仅追加本次执行安全收口，不回改上方阶段结论。文档整理发现旧preflight-v01/v02、battle-v01、G05及continuation的云封装仍可依旧批准调用；battle-v02虽已有命令行main退休检查，导入后直接调用call/prepare/run仍缺封锁。已在7份原有脚本的调用封装与本地预留前补显式政策及永久退休门，python -O不移除。政策缺失、畸形或关闭先拒绝；未来政策开放也不恢复历史写事务，新事务只走reference_pipeline。只读查询/原任务恢复/下载、纯输入指纹和明确的本地node dry-run保留；资源上传不能凭dry-run文字绕过。

7份修改前源代码以不可执行的.py.txt精确保存在原件与SHA清单（本地记录 `production/documentation-consolidation-20261019/legacy-cloud-guard-backups.json`），215份原批准、账本、报价及读回等JSON由修改前指纹（本地记录 `production/documentation-consolidation-20261019/legacy-evidence-before-guard.json`）保护，字节未改。守卫是历史执行后的追加修复，不冒称历史提交时已有这些检查。

离线安全测试（本地 `tests/test_retired_cloud_entrypoints.py`，依赖未公开的第二作旧脚本，未随仓库发布）普通和-O各8组通过：7个旧入口的写操作在CLI前拒绝、提前阻止本地状态更改、只读和本地dry-run仍可用，两版原输入指纹仍匹配冻结报价。独立复核指出main可能先initialize后拒绝，已将preflight-v01的assets/save/edit、v02的assets/edit、G05 run、continuation run-one检查前移到initialize及开锁之前；直接main在缺state时不调用initialize、不创建UUID、不写账本/锁/其他新文件。显式init、离线dry-run及历史只读功能保持。另实跑v02离线完整核验（输出到临时目录）仍通过8来源/11草稿，属于10月16日旧回执的本地重放，不是当前核价或运行准入。复核证据见验证记录（本地记录 `production/documentation-consolidation-20261019/legacy-cloud-guard-validation.json`）。本次没有真实云CLI、上传、生成、核价、余额查询、充值或发布；当前创作入口与运行权限仍以作品目录为准。

## 2026-10-20 固定官方模型契约

新事务可通过plan中的`model_contract.path/sha256`固定已取得的官方model find证据，按明确flags支持480p等新参数；不传字段仍只允许离线16:9/720p。固定证据进入语义指纹；prepare/quote/run共用编译，quote/run继续实时核验官方能力。正文、来源、年龄、审批、次数、最高积分和原ID恢复门禁不变。未修改任何旧作品请求、批准、账本或媒体。

[工具测试](../../../tests/test_reference_pipeline.py)普通及`python -O`各75项通过，含8项新增：480p准备/核价/单次运行Fake链、无合同拒绝、SHA篡改/文件缺失/参数覆盖拒绝、重固定使旧批准失效、缺flag/失败envelope拒绝、实时撤回480p或缺flag时在confirm之前停止，以及旧720p指纹兼容。测试使用临时hoststore，不操作真实账号。实际旧AB请求本地复编译仍为semantic `1dc24ad435c44e391ccb3656135dfbb3f51c5a573730eb75e49b2bc1341c23a9`、request `be8e884264724dd69857b92e90370c50444839bbeb7b6d258465d289aee4b54b`。严格OpenSpec及Python语法检查通过。本补丁自身没有云调用、核价、余额查询或生成，不声明实际480p计价、动态效果或升级能力已验证。
