# 多参考制作工具

`reference_pipeline.py` 的编译和常规执行使用 Python 标准库；仅验证PNG无损重编码时按需加载Pillow，缺库明确阻断该分支，原文件字节相同不依赖Pillow。默认 `compile` 纯本地；不调用即梦、不生成 UUID、不改执行账本，也不推断任何上传或积分许可。`inspect/quote/recover/download` 使用官方 CLI；`prepare/run` 另需逐项匹配的批准记录。仓库中的原450批准保留原文，工具不会自动将它改造成新资源包的批准。

## 历史作品包的离线诊断示例

> 本节示例需要第二作的本地执行目录，公开仓库里没有这些文件。干净克隆可以运行 `python3 -m unittest discover -s tests` 查看工具行为，测试只用内置的假数据和模拟 CLI。新作品使用时，把 `--work-root`、`--registry`、`--plan` 换成自己作品里的文件；数据格式见下文“数据约定”。

作品的当前方案与执行实况统一见制作资料入口（本地记录 `production/README.md`）、当前路线（本地记录 `production/current-route.json`）和执行政策（本地记录 `production/execution-policy.json`）。本工具文档不维护实时runtime、报价、生成次数或许可状态。2026-10-19早期整理中“前12秒输入未定、没有新runtime、云写关闭”的判断只描述当时，已由后续方案与批准更新，不能作为当前禁令。下面仅对旧reference-v01作纯本地历史诊断，不能将编译结果当成当前制作方案；显式退休或实际执行政策拒绝时仍须阻断。已完成事务及主机次数记录保留，换新方案不恢复旧次数。

在仓库根目录可检查历史包：

```sh
python3 tools/reference_pipeline.py compile \
  --work-root works/0002-zaporozhian-reply \
  --registry works/0002-zaporozhian-reply/production/reference-v01/registry.json \
  --plan works/0002-zaporozhian-reply/production/reference-v01/plan.json \
  --output /private/tmp/last-ai-video-reference-compiled.json
```

不传 `--segment` 编译整片；传入 plan 中一个 segment key 可单独检查。输出文件包含确定性的完整请求、别名/引用序号、完整 promptParts、资源/Element依赖与选中产物指纹、基准文件指纹及 blocking。命令行只显示安全摘要。

- `local_ready=true`：所需本地素材、审看声明和指纹一致；可能仍缺远端绑定。
- `executable=true`：编译没有阻断且为 generate 类型。它仍然不代表已获批准、当前服务端可用、价格已确认或动态效果通过。
- `reuse/local_edit` 始终不作为可运行视频节点。
- `planned_missing`、实际起态/端态缺失会明确列出，不会用占位节点或旧版本替代。

核心纯函数为 `compile_segment(registry, plan, segment_id, work_root, model_contract=None)`、`compare_readback(compiled, readback, target_id=None)`、`authorization_delta(compiled, approval, work_root, operations)`。职责/时代/年龄/mode冲突为显式错误；资源缺失可形成可审的 blocked 编译结果。

## 数据约定

registry 的 `assets` 和 plan 的 `segments` 均为字典。media含 `media_type,path,sha256,bytes,status,allowed_roles,forbidden_roles,characters,review,remote`；Element含 `kind=element,main,auxiliaries,voice`，绑定均为asset ID，主素材必须为媒体、辅助必须为image、voice必须为audio。Element不伪装成PNG。历史registry中的 `status=ready`只表示当时本地文件可取得，限定用途见review；不表示当前场景、构图、创作者接受或运行已就绪。当前参考职责另存，不将旧窄构图整幅自动迁移；缺失素材保持非ready。

本片离线编译只采用已定向核实的seedance_2.5、16:9、720p参数组合；`model_validation=offline_16x9_720p_profile_only`不表示当前在线契约已刷新。提供实际model契约可定向检验其余组合，run前始终重新查询。当前公开Element main契约未枚举媒体类型，本工具仅对image主素材放行；video/audio main保留计划但以`element_main_type_runtime_unverified`阻断，而不声称官方一定不支持。

2026-10-20起，新事务可在plan顶层显式固定实际官方`model find`文件：`"model_contract":{"path":"production/新事务/model-find.json","sha256":"文件SHA256"}`。路径相对作品根，支持官方成功envelope（`ok=true,data.items`）或直接`items`数据；编译核对同一份文件字节与SHA，所用模式必须明确提供ratio/resolution枚举和duration/count范围。`compile/compare/prepare/quote/run`统一生效，不需额外CLI参数；编译返回`model_validation=pinned_official_contract`及`model_contract_fingerprint`。仅在固定证据明确允许时可准备480p等请求，不将低分辨率预演强制为所有片段步骤。

固定路径及SHA进入新事务`semantic_hash`；修改文件直接拒绝，重固定新文件会改变语义指纹，不能继承旧批准。缺失/失败/畸形契约或缺少明确flag也拒绝。未加该字段的历史720p计划编译结构、语义hash及离线profile不变；直接API旧的`model_contract`参数仍可用于本地验证，但不可覆盖plan中的固定证据。固定文件不是官方签名或能力永久保证：`quote/run`仍各自重新查询当前官方契约，明确核验同一参数；价格、读回、审批、次数和积分上限均沿原门禁，不因低清方案放宽。此功能本地验证不代表实际低清报价、动态效果、或低清无重生成升级已实测。

remote为 `{"kind":"node|resource","id":"…","project_id":"…","selected_resource_id":"…"}`。媒体Node必须记录选中Resource，否则阻断执行。Element当前只支持Node身份。绑定显式返回 `resource` 时严格比较该对象，冲突或空对象不能用来源节点补救。2026-10-17实际CLI的Node绑定仅返回身份字段；此时只有来源Node成功、ID及类型正确、resources总数恰为1，且该唯一Resource成功、类型和ID均与已批准selected_resource一致，才能作为无歧义证据。多产物即使包含已批准ID仍阻断；缺来源、未就绪或错资源报 `selected_resource_unverified`。resource类型绑定缺内嵌Resource仍阻断。Element主图、辅助图和voice沿用同一规则，不借此放宽选中产物核验。

每段的 `references` 有序，每项声明 `asset_id,alias,roles,exclusions`。正文用 `[[ALIAS]]`；编译成官方 `{{node:…}}` 或 `{{res:…}}`。同一来源多职责合并引用序号；漏别名、重复别名、未使用别名、职责禁区冲突均拒绝。`identity_primary`、`costume_reference`、`identity_source`（以及identity/costume等同义职责）均验证当前段的角色时代和年龄，identity_source不是绕过年龄的后门。跨龄早期图可保留为衍生资产provenance/制作来源，不能直接当作当期人物外观。明确不详的配角年龄可在两侧均写null；缺少age字段或一侧已知另一侧不详仍报冲突。风格图出现晚年人物，不因忽略身份的风格用途被当作青年身份；prop_identity不属于人物身份职责。

正文中物理引用的首次出现次序必须与references声明一致；不一致时报 `reference_first_appearance_order_conflict`。官方CLI实测会按正文第一次出现解析槽序，`--ref A --ref B`不能强迫正文“先B后A”保持A/B槽序。需将references与正文的第一次引用顺序一起调整；不要更换职责来掩盖错序。该检查适用于全部mode，尤其不能在首尾帧模式静默交换帧位。重复引用同一物理来源不会新增槽位。

`baseline_files` 使用作品内相对路径到SHA256的字典。`timeline` 为 `{start_s,end_s}`。片段可选 `remote={node_id,update_id,submit_id}`；未提供时，受控 prepare 在任何云写前把稳定身份记入journal。`dependencies` 只接受 `[{"segment_id":"已存在片段ID","checks":["明确检查项"]}]`；说明文字放preflight_notes，不放runtime依赖。编译检查存在性、结构和依赖环；run核对真实下载输出SHA、origin resource及逐项审查，不能只写accepted=true。

生成的Node ID遵守当前官方命令的 `node_` 加10位小写Crockford Base32形态；不是任意长度UUID片段。真实binary本地测试也覆盖自动分配的新目标ID。

旧作品专用的preflight／G05／battle脚本已退休云变更入口，保留指纹和历史只读能力；即使旧JSON仍有当时的批准字段，也不能绕开当前政策。

## 批准与事务

工具接受单独的标准化批准合同。它必须由实际人类批准范围整理，不能凭已有预算、旧批准boolean或下例自行生成许可。下例故意为不可执行状态：

```json
{
  "schema_version": 1,
  "human_approved": false,
  "project_id": "目标项目UUID",
  "evidence": {"path": "production/实际批准证据.json", "sha256": "证据文件SHA256"},
  "operations": {
    "uploads": {"资产ID": "该媒体SHA256"},
    "elements": {"主体ID": "该主体dependency_fingerprints中的semantic_hash"},
    "drafts": {
      "片段ID": {
        "semantic_hash": "编译semantic_hash",
        "source_bindings": {"既有资产或Element闭包中的每个ID": "该项binding_hash"}
      }
    },
    "runs": {
      "片段ID": {
        "semantic_hash": "编译semantic_hash",
        "source_bindings": {"既有资产或Element闭包中的每个ID": "该项binding_hash"},
        "max_calls": 1,
        "credit_ceiling": 0
      }
    }
  },
  "max_total_credits": 0,
  "max_generation_calls": 0,
  "existing_credits_only": true,
  "automatic_retry_allowed": false,
  "topup_allowed": false,
  "publication_allowed": false
}
```

媒体上传按文件SHA授权，Element创建/编辑按主辅/音色依赖语义hash授权。视频草稿与运行除了当前整段semantic_hash，还必须分别用 `source_bindings` 冻结所有既有源（含Element及全部主/辅/音色闭包）的binding_hash。只写semantic_hash不能把不同Node/selected resource称作同一输入；批准草稿核价不等于批准run，也无需为保存草稿强迫提供runs授权。具体request_hash同时包含实际locator、selected source及完整生成请求，用于拒绝陈旧读回和报价。更换审查内容、资源、参数、时长、引用或Element依赖后，不能沿用旧请求就绪状态。

尚未上传的来源无法提前给出远端binding_hash。仅在本次原批准明确覆盖其文件SHA及使用该资源的片段semantic_hash时，允许由本轮稳定ID导入回执派生绑定：核对同一批准合同hash、原文件SHA/bytes、导入resource与选中resource，再在run前通过官方resource get/download检查实际文件。回执size及sha256必须严格等于下载文件的实际值；随后与已批准原文件比较。临时下载随后删除，不涉及生成消费。`journal.status=verified` 不能授权新来源；伪造该布尔或换成其他内容仍会阻断。新Element还要求明确的elements授权、全部孩子绑定已覆盖且实际subjectBindings完整一致。

2026-10-17实际导入PNG出现服务端无损重编码，文件SHA/bytes改变但逐RGBA像素完全相同。因此仅为image来源提供严格替代：双方均为8位RGB/RGBA PNG、单帧且同尺寸，非像素PNG块及Pillow元数据一致（覆盖ICC、色彩、EXIF方向），逐RGBA字节精确相等才通过。唯一已实测的例外是服务端省略非渲染来源签名caBX：允许原caBX保留在本地、下载caBX缺失，并审计双方块摘要；不主动修改媒体或删除签名。caBX内容变化、新增caBX、其他未知块或色彩/方向信息变化继续阻断。改1个像素、动画、多帧、调色板或其他格式均不放行；不使用感知相似度、缩放或容差。缺Pillow报 `exact_png_verification_requires_pillow`。journal的source_content_verification记录原与下载SHA/bytes、Resource及request hash；无损重编码另记method=exact_pixel_identity、dimensions、rgba_sha256、original_metadata/download_metadata及server_removed_chunks。原批准文件SHA、绑定和计划保持不变。

2026-10-17次数守卫补正：只在单份journal或工作根内计数，不能防止同批准换文件／复制目录后重新执行。工具按本机project与人类批准证据SHA，在用户级`~/.local/state/last-ai-video/reference-pipeline-authority/`保存权威记录；位置不由`--work-root`、state路径或工具副本决定。以flock先锁批准再锁journal，绑定唯一canonical work_root／state路径、标准化合同hash、随机nonce及单调次数／预留／目标身份；state软链接在读、锁、写前统一解析。换根借原账本、换state、删除后通过只读操作重建空账本、回退同nonce旧快照、复制批准证据路径或换合同均不能恢复额度；缺少原root绑定的旧权威记录也不能静默重绑。

权威记录同时保留已分配asset身份与尝试进度，旧快照不能删去未知上传再重提；恢复只查询原身份，允许经核实向verified前进。用量与身份先持久再落工作账本，崩溃导致两侧不一致时保守阻断，需要明确恢复，不自动清零。权威记录不在仓库内，应与原账本一并保留；同host换workroot及跨机器均需显式迁移。此为本机操作一致性守卫，不是账号级跨机器总账，也不声称抵御同时篡改所有本地证据。测试将hoststore隔离到临时目录，2026-10-17这次工具离线测试未为实际作品创建权威记录；后续实际批次已使用主机次数记录，不能用这句历史测试范围断言当前没有记录。

显式retired／superseded／rejected状态、execution_allowed=false或作品`production/execution-policy.json`拒绝云写时，编译不可executable，prepare／run在CLI前拒绝。paid_ready不是人类批准或执行政策。inspect／quote／recover／download保留只读能力。2026-10-17工具离线复核没有调用真实云操作；这项历史范围不表示后续作品未执行。旧交易不自动补nonce或迁移批准，原450、回执与账本保留；当前实际允许的操作、runtime及批准合同只读当前路线（本地记录 `production/current-route.json`）与执行政策（本地记录 `production/execution-policy.json`）。不得从旧执行政策快照、旧额度或工具文档恢复／否定当前许可；已耗尽旧事务不能重新提交。

命令共用 `--work-root --registry --plan --segment`。外部命令还需要 `--state <新事务账本路径>`、`--cli <当前官方binary路径>`；prepare/run提供 `--approval <实际批准合同>`。

| 命令 | 行为 |
| --- | --- |
| inspect | 只读来源、Element和目标节点，返回完整比较结果；不保存原始第三方响应 |
| compare | 用 `--readback <JSON>` 离线比较，必须有真实未截断的绑定/资源/promptParts字段 |
| prepare | 先检查全部已知授权差额，再上传/导入、必要Element创建/编辑、保存草稿；已有正确节点直接复用 |
| quote | 当前model契约、完整readback、当前draftVersion和quote一致后保存安全报价摘要 |
| run | 重做当前契约/readback/quote，逐段及累计限额检查，确认后再读回；once和最高积分在提交前落盘 |
| recover | 只查原submit ID或 `--asset <资产ID>` 的原导入身份，不自动重提、不释放未知预留 |
| download | `--output <作品内新相对路径>`，校验成功视频、bytes、SHA，不覆盖原始素材 |

node/Element来源发生变化时，先对照新资源包和批准差额；不为“修引用”重抽视频。CLI执行未知、超时、部分失败均保留原稳定身份；prepare/run不能靠再次调用自动重试。token只在内存传给官方 `node run --credit-token`，不进入journal、stdout或异常文本。API原始响应、provider payload、signed URL从不自动保存。

官方响应顶层的 `meta.requestId` 经字符和长度白名单检查后，累计保存至journal的 `cli_request_ids`，包括失败envelope的关联ID；多次保存与跨进程读取不会覆盖旧ID。只读查询也会在退出事务时更新这份本地审计，不产生云写入。不会保存meta的其他字段、嵌套provider标识或访问材料；无法解析响应或超时且未取得合法envelope时，不捏造关联ID。

## 官方CLI本地形态检查

以下为2026-10-17本地形态核验的历史示例，使用当时本片**已经导入**的F018/F020，检查多个有序ref与Element主辅参数的本地形态。`--dry-run`不联网、不保存、不核价、不运行；它不验证新资源包存在、权限、身份一致性、Element展开数量或动态效果。示例也不把这两张完整画面重新指定为最终人设资源。示例中的临时binary路径不保证仍存在，不是当前安装入口；真正需要执行时再按官方安装文档恢复并核对版本，不绕过CLI捏造HTTP。

```sh
/private/tmp/dreamina-canvas-battle-v02 node create video \
  --project-id 16df0e2a-bbb3-42b5-8bf5-68e813813e95 \
  --title reference-contract-local-check \
  --model seedance_2.5 --mode m2v --ratio 16:9 --resolution 720p --duration 5 --count 1 \
  --ref node:node_96caacc6ad --ref node:node_593bd6fa51 \
  --prompt '{{node:node_96caacc6ad}}作为环境资料，{{node:node_593bd6fa51}}仅供接触关系资料。' \
  --dry-run --format json --non-interactive

/private/tmp/dreamina-canvas-battle-v02 node create element \
  --project-id 16df0e2a-bbb3-42b5-8bf5-68e813813e95 \
  --main node_96caacc6ad --auxiliary node_593bd6fa51 \
  --title element-contract-local-check --dry-run --format json --non-interactive
```

Element不是必选项，当前服务端计数/计价以及实际身份/音色效果仍未由本片付费生成证明。多参考上限不是建议图数。

## 离线验证

```sh
CONSUL_HTTP_HOST=10.37.27.75 CONSUL_HTTP_PORT=2280 python3 -m unittest discover -s tests -p 'test_reference_pipeline.py' -v
CONSUL_HTTP_HOST=10.37.27.75 CONSUL_HTTP_PORT=2280 python3 -O -m unittest discover -s tests -p 'test_reference_pipeline.py' -v
```

测试主要用FakeCLI；若已安装当前临时官方binary，会额外运行两次纯本地`--dry-run`核对正文首次出现与槽序，不接账号、不写即梦、不核价或消费，缺binary则明确skip该项。覆盖多引用/Element主辅音色与变更、角色时代/职责、首尾模式、完整读回、真实CLI无内嵌Resource形态的唯一来源核验、显式冲突与多产物歧义拒绝、明确授权差额、unknown和原ID只读恢复、预算与once、异常脱敏及优化Python门禁。PNG精确像素测试需使用已含Pillow的Python；缺库时明确skip这些测试，不能称该分支已验证。本地通过与云端/原速成片验收分别记录。
