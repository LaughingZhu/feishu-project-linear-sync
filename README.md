# 飞书项目 → Linear Sync Skill

团队继续在飞书项目维护需求和缺陷，通过飞书多维表格把指定负责人要处理的事项同步到 Linear，无需额外部署中转服务。

这是供 AI 编程助手使用的 **Skill 与工作流参考模板**。助手可以帮助配置、排查和恢复同步；skill 本身不启动后台服务，也不自动操作线上账号。

```mermaid
flowchart LR
    F[飞书项目] -->|事件通知| B[飞书多维表格]
    B -->|创建或更新 Issue| L[Linear]
    L -. 可选展示 .-> O[Orca]
```

## 能做什么

| 场景 | 能力 |
|---|---|
| 配置同步 | 梳理账号映射、负责人筛选、字段、来源验证和状态映射 |
| 需求节点子任务 | 提供入表/出表模板，支持创建、改名、完成/回滚和删除处理 |
| 缺陷 | 提供配置与排查指引，按真实缺陷事件样本适配 |
| 漏同步排查 | 从源端规则、事件、Base 记录、HTTP 结果追到 Linear 回写 |
| 安全补同步 | 按原来源 ID 查已有 Issue，再决定回填、更新或受控重试 |

**缺陷的经办人、报告人和创建人是不同字段。** 规则按经办人筛选时，本人报告的缺陷也可能不满足条件。创建后补填经办人，不会重放那条创建规则。

## 安装与使用

### Codex

```bash
git clone https://github.com/LaughingZhu/feishu-project-linear-sync.git \
  "$HOME/.codex/skills/feishu-project-linear-sync"
```

目标目录已存在时，先比较本地版本，不要直接覆盖。技能列表未刷新时，重新打开会话。

也可以下载仓库 ZIP，将整个文件夹命名为 `feishu-project-linear-sync`，放入技能目录。其他支持 `SKILL.md` 的客户端按其安装规则使用；`agents/openai.yaml` 是 Codex 的可选界面元信息。

```text
使用 $feishu-project-linear-sync，帮我配置飞书项目到 Linear 的同步，
只处理指定负责人创建时负责的需求子任务。
```

```text
使用 $feishu-project-linear-sync，排查这条缺陷为什么没同步。
先只读检查，不修改经办人或创建 Issue。
```

```text
使用 $feishu-project-linear-sync，核对这条任务是否已在 Linear 创建，
再按原来源 ID 补同步，避免重复建单。
```

## 准备自己的环境

需要可访问的飞书项目空间、多维表格、目标 Linear Team 和账号，以及相应读写权限与可用运行配额。飞书用户 Key 和 Linear 成员 UUID 要分别解析，不能直接互换。

优先使用当前可用的连接器或 CLI；环境中有 `lark-base`、`meegle`、`orca-linear` 等技能时可配合使用，没有时可使用已登录网页。**Orca 是可选展示入口，不是同步依赖。**

## 离线生成子任务工作流

渲染器仅需 Python 3.9+ 标准库，不联网、不读取凭证、不操作线上系统。在仓库目录执行：

```bash
mkdir -p ../feishu-sync-local
cp assets/config.example.json ../feishu-sync-local/config.local.json
```

把仓库外的 `config.local.json` 中所有 `SET_ME` 替换为当前环境参数：

| 参数 | 内容 |
|---|---|
| `table_name` | 已创建的目标表名 |
| `project_key`、`owner_key` | 来源空间 Key、目标负责人的项目用户 Key |
| `linear_team_id`、`linear_assignee_id` | 当前 Linear Team 与成员 UUID |
| `todo_state_id`、`done_state_id`、`canceled_state_id` | 当前 Team 的三个状态 UUID |
| `parent_url_prefix` | 从真实父需求页面确认的 HTTPS 前缀，末尾保留 `/` |
| `fields` | 九个字段别名到目标表实际字段 ID 的映射 |

完整列名和类型见 [字段契约](references/field-contract.md)。模板按列名筛选、赋值，按字段 ID 引用输出。列名不同时也要适配模板，不能只替换 ID。

```bash
python3 scripts/render_workflows.py \
  --config ../feishu-sync-local/config.local.json \
  --out ../feishu-sync-local/draft-001
```

输出目录必须尚不存在。生成的 `task-inbound.json`、`task-outbound.json` 分别是入表和出表请求 body，仍包含凭证占位符，**不能直接启用**。

按当前 Base schema 检查输出，在授权环境中安全配置凭证，先保存停用草稿，再按 [配置指引](references/setup.md) 验收。示例事件的 ID、标题和时间戳都是合成数据，不能直接用于真实回放。

单选项按名称绑定，没有携带原表选项 ID；目标表需预先创建契约中的选项。共享模板为 22 个入表节点、27 个出表节点，已完成离线验证，仍需在使用者自己的租户验收。

## 保持的行为

- **沿用同一个 Issue**：按来源空间、类型和 ID 定位映射，有 Linear ID 时更新它。
- **不盲目重试创建**：创建已尝试但 ID 未回写时，先查 Linear，进入待核对。
- **删除保留映射**：已有 ID 时转 Canceled；无 ID 且从未尝试创建的删除只保留删除标记，不新建已取消的 Issue。
- **负责人变化先暂停**：保守暂停涉及变更的已入表任务，核对后人工恢复，不自动为后来转入的任务补建。

## 脱敏与分享

模板只保留参数标记、凭证占位符和合成事件，没有内置作者的空间、表格、人员、Team、状态 UUID 或真实 Webhook 地址。工作流内部节点 ID 仅用于连接图，不是可访问线上资源的地址或账号凭证。

真实参数、线上工作流导出、日志和凭证应保存在仓库外。`.gitignore` 排除了常见本地配置和渲染产物，但不能保护已跟踪文件中后来填入的密钥；提交前仍应检查暂存区。

`YOUR_LINEAR_API_KEY`、`YOUR_FEISHU_BODY_TOKEN` 仅表示待配置位置。不要把 Token 写进 README、issue、截图或聊天消息。启用公开 Webhook 前核对来源验证方式；不要为了重试关闭校验或放宽为所有人的任务。

提交时也请核对 Git 作者邮箱，避免把不希望公开的工作邮箱写进提交历史。

## 本地验证

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

测试覆盖参数化图结构、字段上下文、选项 ID 清理、凭证占位符、错误参数拒绝、输出不覆盖，以及正常创建、删除和创建结果不确定的分支。分享检查会检查模板中的静态租户 UUID、字段/选项 ID、邮箱和租户资源链接。

这些是离线检查，不能证明线上授权、事件发送、动态 JSON 转义或回写成功。真实联调用 `[TEST 同步验证]` 任务，分别核对源事件、Base 记录、HTTP/GraphQL 结果、Linear ID 与实际启用状态。

## 当前边界

- 单向同步，标题和完成状态以飞书项目为准，不反向覆盖飞书。
- 可参数化 JSON 仅用于需求节点子任务，缺陷需适配真实 payload。
- 默认同步创建时已由目标用户负责的任务，不自动导入存量或后来转入的任务。
- 一份配置绑定一个目标负责人和一个 Linear 成员/Team。多人默认独立表/流程，共享表需重新设计隔离与唯一键。
- 未配置排期、估分、优先级同步，不会自动执行开发。
- 不提供跨系统事务、严格并发唯一性或已发出请求的取消保证。

## 文件导航

| 文件 | 用途 |
|---|---|
| [SKILL.md](SKILL.md) | 助手入口和执行约束 |
| [配置指引](references/setup.md) | 参数、事件、工具选择与启用 |
| [字段契约](references/field-contract.md) | 默认表结构与字段别名 |
| [排查指引](references/diagnose.md) | 按来源 ID 定位漏同步 |
| [恢复指引](references/recovery.md) | 补录、回填与受控重试 |
| [参数示例](assets/config.example.json) | 不含凭证的配置结构 |
| [工作流模板](assets/task-workflows.template.json) | 入表与出表参考图 |
| [渲染器](scripts/render_workflows.py) | 生成待配置凭证的请求 body |
