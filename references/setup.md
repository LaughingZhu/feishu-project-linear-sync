# 配置同步

## 收集当前环境，不复制作者的资源

确认用户选择的对象（缺陷、需求节点子任务）、筛选角色（负责人/经办人、报告人、创建人等）、是否包括后来转入与历史存量、是否允许测试建单。默认参考模板只支持创建时指定负责人。

| 参数 | 获取方式 |
|---|---|
| 飞书项目空间 Key、类型 Key | 读取真实工作项/规则，不把网址里的空间短名当作 Key |
| 目标飞书用户 Key | 用真实工作项的经办人/负责人或当前项目身份解析；与飞书通讯录 open_id 可能不同 |
| Base token、表 ID、列名及字段 ID | 解析目标 URL，再读取表结构；Wiki token 不能代替 Base token |
| Linear Team、成员 UUID、状态 UUID | 当前连接器/API 查询；通过明确账号信息匹配飞书人员，不能按名字模糊取第一个 |
| 飞书链接前缀 | 从可访问的真实父需求 URL 提取；不要宣称能直达子任务，除非实际验证 |
| 安全凭证 | 使用者在授权的安全界面/凭证存储中提供，不能放在共享配置或命令行参数中 |

有现成链路先确认现状，别复制旧流程后忘记改表、字段 ID、Team、成员或触发条件。当前正式配置与网页草稿可能不同，部署后回读正式版本，刷新页面确认；避免后续误保存旧草稿。

## 多人复用的边界

一份参数配置绑定一个飞书负责人和一个 Linear 成员/Team。多人各自使用时，默认各自建立独立表和工作流。共享一张表前，先决定同一来源对应一个共享 Issue，还是每个负责人各有一个 Issue；后一种必须把用户/目标范围纳入唯一键和所有查找条件。不能把第一个人的 assignee UUID 和个人筛选规则直接复用给所有人。现成任务模板没有实现多租户共享表的隔离。

## 原生链路

飞书项目事件 → Base Webhook 入表流程 → Base 记录变更出表流程 → Linear。无需额外部署中转服务；仍依赖飞书与 Linear 的 SaaS、权限、套餐和运行配额。

- 优先使用授权连接器/CLI。当前可用的 Base shortcut 可包括 `+url-resolve`、`+field-list`、`+workflow-get/create/update/enable/disable`，先看本机 `--help` 和 schema。
- 更新流程前先 get，`PUT` 可能全量替换；保留无关标题、节点与凭证，不能把缺失 steps 的更新当作补丁。
- 生成的两份 JSON 是请求 body，需分别创建或修改目标流程；不要把外层模板字典作为请求 body。更新后是否需要重新启用/发布，以当前工具和运行日志为准。
- 配置凭证时避免输出 Authorization、Webhook 地址和请求体 Token。只读接口也可能返回明文凭证，输出摘要或先在内存脱敏。不要为了方便复制其他人的凭证。
- 独立创建停用草稿，先把字段和判断条件配置完整。测试/启用只在用户授权范围内进行。公开 Webhook 需先核对可用来源验证机制；若源端不能发 Bearer 头，可评估高熵请求体 Token、固定空间/事件校验及平台支持的其他保护，不能提供固定弱口令默认值。

## 缺陷入表：先核对经办人

通常监听 `WorkitemCreateEvent`，校验空间、类型和来源 Token。来源 ID、标题、经办人、描述在真实 payload 中可能分散在 fields 数组，必须抓取/读取当前样本并按字段 Key 或 alias 匹配，不能依赖数组位置。

如果源端通知规则已经准确过滤“经办人包含指定用户”，可在入表端保留来源和去重验证。仅检查 header.operator 会错误地筛选创建者；只检查报告人会放入他人负责的缺陷。

单选状态在模板中按名称匹配，不携带原表 option ID。目标表需预先创建契约中的唯一选项名；不同命名应先适配，当前产品若强制需要选项 ID，则读取目标表后再绑定。

**本包没有可直接套用的缺陷 workflow JSON**：事件结构与任务不同，应依据真实缺陷样本和当前 Base schema 构建。先跑通用户真正需要的最小字段；关联需求名、所属系统有值则附加，无值则省略。只有关联 ID 时不要伪造名称；无只读 OpenAPI 权限时保留 ID/来源链接即可。

## 需求节点子任务模板

来源必须是节点下的具体子任务，不是整条需求，也不是飞书独立待办 Task 产品。

| 事件 | 典型数据 | 处理 |
|---|---|---|
| TaskCreateEvent | task_id/name、work_item_id/name、relate_state_id/name、created_at、api_owners_schedule.owners | 遍历负责人；匹配目标 Key 后去重、入表 |
| TaskUpdateEvent | task_id、task_name、updated_at | 仅更新已入表且有效任务的名称；不要假定此事件总含完整负责人 |
| TaskStatusEvent | task_id、cur_status、updated_at | 映射已核验状态，未知值跳过，不覆盖标题 |
| TaskDeleteEvent | task_id、updated_at | 标记删除，更新 Linear 为 Canceled，保留映射 |
| WorkitemPersonAssignedEvent | 父工作项信息、updated_at、task_owners[] | 找具体任务 ID；保守暂停相关已入表任务 |

参考模板在 2026-10 的样本中使用状态 1=未完成、2=已完成。实际配置时先对真实未完成/完成任务核验；不能直接推广到所有工作项和所有空间。

模板使用字段名作记录筛选和赋值，使用实际字段 ID 引用出表触发器的字段输出；这两种引用都要正确。九个 `fields` 别名见字段契约。

父需求类型在样本里是 `story`，实际类型可不同。output_json 只是完整输出 schema 样例，其中任务 ID 1001、需求 ID 101、时间戳等都是假数据，不是待回放事件。真实测试应从新测试任务产生。

平台/CLI 曾拒绝 JSON 数组 `containsAny`、嵌套循环的叶子引用以及 Switch/Loop 下的 IfElse；参考使用 Switch 和保守负责人暂停。先核对当前 schema、验证响应；不要把历史限制当作永久能力。判断涉及本次人员变更的具体 task_id，不能因为同一父需求其他任务换人就暂停全部子任务。

## Linear 出表

- 原生 HTTP POST `https://api.linear.app/graphql`，请求体中使用 GraphQL variables，避免拼接到 query 中。
- 个人 API Key 与 OAuth access token 的 Authorization 形式不同，按当前官方文档和凭证种类配置，不能统一强加 Bearer。
- 已删除、无 ID 且未尝试创建时，只保留删除标记并停止同步，不新建 Canceled Issue；已尝试但无 ID 的删除仍进入待核对。无 ID 且未尝试创建的有效任务才进入新建分支；发送前写尝试标记。已有 ID 走 `issueUpdate`，保留用户开发描述，仅更新授权字段。
- 新建可带 teamId、assigneeId、标题、状态和来源上下文；状态 UUID 来自当前 Team。成功要求 HTTP/GraphQL 业务成功、真实 issue.id 与回写一致。
- 确认原生 Raw JSON 节点是否已经转义动态字段。用引号、反斜杠、换行验证一次，不要重复手工转义。历史配置中未使用排查时增加的 JSON 转义公式字段。
- 400 时检查实际发送的 JSON 和 Content-Type。标准 HTTP JSON 请求应有正确 Content-Type；本次历史案例使用节点原生 JSON 处理并移除冲突的手填头后成功，不能推广成“请求不能带 Content-Type”。

官方资料入口（实施时核对最新内容）：
- 飞书项目 Webhook：https://www.feishu.cn/content/49fq0rvm
- Base HTTP 请求：https://www.feishu.cn/hc/en-US/articles/410063847664-use-base-to-automate-the-sending-of-http-requests
- Linear GraphQL：https://linear.app/developers/graphql

模板中的 YOUR_LINEAR_API_KEY 是五个 HTTP 节点的凭证占位符，全部需安全配置；YOUR_FEISHU_BODY_TOKEN 是入站校验值，必须与源端通知设置一致。schema 示例的 sample-only 仅用于描述字段，不是认证值。
