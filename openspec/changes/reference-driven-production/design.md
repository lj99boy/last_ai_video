## Context

2026-10-17复核增补：下段及原Decisions记录首次工具交付时的78秒／1060积分／450未用状态，现已成为历史。当前作品是创作者认可的68秒设计、战斗3+2+2+6与草原长车营，实扣累计1438，原三次授权已耗尽。当前设计计划不是runtime输入；不得将旧reference-v01组合继续当当前权威。fake/local复现发现同一批准换state路径能重新计数，需将批准绑定权威账本并拒绝重置；显式退休状态须进入编译与写入守卫，而不依赖偶然的baseline SHA不匹配。实际旧交易、审批、请求和费用保持原字节，不通过重写历史来获得新执行权。此修订仅本地实现与测试，不联网、不上传、不消费。

当前78秒作品有20个节拍、跨三年代人物、1060历史视频积分和一次450积分战斗批准。F018/F020已上传，旧宽景/救援草稿报价90/144，未提交视频。当前原生m2v可有序混合引用，Element有主图/辅图/音色；实际角色隔离、权重和效果没有保证。独立审计位于作品的reference-rebuild系列文档。

## Goals / Non-Goals

目标：整片叙事先于素材，实际补齐当前欠缺资产；同一份有职责、年龄和指纹的输入贯通编译、读回、核价与安全执行。开发与资源准备均在本轮完成本地交付，不能只有一份建议。

不以本次流程开发承诺全片动态成功、不自动消费；不建立服务/数据库、不强制人设套图或Element、不重写既定故事。

## Decisions

1. 以作品`production/reference-v01/registry.json`和`plan.json`为权威新输入，保留CSV素材总账。registry使用`assets`字典，media字段：`media_type,path,sha256,bytes,status,allowed_roles,forbidden_roles,characters[{id,era,age}],review,remote`；Element字段：`main,auxiliaries,voice`均指向asset ID、`remote`及审查。远端locator采用`kind=node|resource,id,project_id,selected_resource_id`。缺图可登记状态但不得伪装ready。路径相对work root。
2. plan含`work_id,project_id,baseline_files,segments`字典；每段含`beat_ids,timeline,delivery=generate|reuse|local_edit,era,characters,viewing_task,camera_intent,mode,model,ratio,resolution,duration_seconds,prompt,references[{asset_id,alias,roles,exclusions}],acceptance`。正文用`[[ALIAS]]`占位，编译成官方`{{node:...}}`/`{{res:...}}`。重复相同物理引用合并index，冲突别名拒绝。reuse/local_edit不冒充可运行视频请求。
3. Python标准库小工具分离纯函数编译与CLI副作用。纯编译输出完整引用序列、promptParts、递归Element闭包、文件/基准指纹、语义hash、blocking问题、所需外部操作；未有remote仍可审本地组合但`executable=false`。CLI只执行白名单官方命令，所有事务stable ID先持久化，未知不重试。显式异常而非assert；token和带鉴权URL不写日志。
4. 批准记录不可变。450作为尚可用的旧范围，不把其布尔字段当新人设上传或Element授权。新组合输出实际delta；输入/时长/模型/Element内容变化使旧读回和报价失效。当前本地工具开发及图片制作不触发云写。设计变更后的正式云写/付费必须覆盖delta并重新核价。
5. 参考数量由缺失信息决定。当前P0仅三个1648清晰单人人设与空车结构；可复用的旧图保留限定职责。跨龄8身份标签建清单，未实际需要的多角度图不先买。F018只作世界/空车来源，F020只保接触证据；原画群体布局、关键受力、严肃群体起态仍需要关系验证。D独立设计起推关系，不依赖救援末帧恰好切到D。
6. 泛用方法更新docs/templates；本片规则留作品目录。所有20节拍有策略及明确缺口，不为每节拍强制单独生成。战斗是第一代表性正式场面，之后依据真实收益推进G05和群像。

## Risks / Trade-offs

- 语义职责无法阻断画面污染 → 实看资产，减少冲突来源；原速结果确认后才记录效果。
- 多引用/Element不保证价格更低 → 最终新配置定向核价，旧234不沿用。
- 生成单人身份可能漂移 → 对照青年来源骨相、年龄、服装单项审查，标记仅本地候选，不自称用户已认可。
- 事务未知导致保守占额 → 用原ID只读恢复，不新ID绕过once限制。

## Migration Plan

建立新入口；旧resume计划/批准/回执保留，旧executor增加明确退役门。新工具离线测试、官方本地dry-run、整片覆盖检查通过；当前状态标示本地完成与云端待验证。回滚时可切回历史方案资料，但不能清空发生事实或绕过现行授权。

## Open Questions

Element真实动态收益及具体计价待实际作品结果；不阻碍本地实现，不把它作为每镜必选。新增媒体/Element云写差额在具体素材完成后展示。

## 2026-10-20 固定模型契约补充

新plan可显式提供`model_contract={path,sha256}`，路径相对作品根，文件为实际官方model find数据或成功envelope。编译从同一份字节核验SHA并解析，要求所用模式明确枚举ratio/resolution及duration/count范围；不以缺少flag表示允许。该文件路径及SHA进入新增事务语义指纹，文件修改或重固定均不得沿用原批准。未提供字段的历史720p编译结果和语义指纹保持原形，不将480p硬编码为离线默认。prepare、quote、run统一调用纯编译，不需要绕开执行器；quote/run仍重新查询实时官方model find并明确核对所用flag。固定文件仅为本地审计证据，不替代实时能力、当前报价或人类消费批准。
