# 差旅报销审核 Agent 工程审计报告

- 审计日期：2026-09-11
- 项目根目录：仓库根目录
- Git 基线：`cd9a9658a1e60bad8bb9a8dcc7e2f725e68661b4`
审计方式：目录扫描、代码审阅、OpenAPI 检查、只读数据库检查、依赖检查、自动化测试、远程 CI 状态核对。

> 本报告只做调查、判断和建议。审计期间没有修改业务代码、规则、数据库数据或配置。工作区在审计开始前已有 `README.md`、`docs/demo_script.md`、`docs/interview_talking_points.md` 三处未提交文档修改，本报告保留并不覆盖这些修改。

## 1. Executive Summary

### 1.1 一句话结论

当前项目不是自然语言行程规划、订票或旅行推荐助手，而是一个 **企业差旅报销数据录入、规则检索、确定性合规审核和报告归档的后端 MVP**。

它已经形成可运行主链路：

```text
结构化行程/费用/凭证
  -> SQLite
  -> 关键词检索 Markdown 规则
  -> 固定六步 Agent 工作流
  -> 确定性审核引擎
  -> JSON 审核报告持久化与查询
```

项目具备 FastAPI、SQLAlchemy、Pydantic、SQLite、测试隔离、pytest 和 GitHub Actions，已超出“单文件教程 Demo”；但规则文档、RAG 证据和执行代码未形成单一事实源，部分规则语义实现不准确，Agent 也没有 LLM、动态规划或标准 Tool Calling。因此当前等级是：

> **可演示的 MVP，尚未达到可作为主打项目的 Resume-ready 水平。**

现在可以写入简历，但必须准确描述为“确定性工作流 Agent / 报销审核 MVP”，不应描述为“基于大模型的智能差旅助手”或“多工具自主 Agent”。

### 1.2 最重要判断

- 当前最值得保留：确定性审核引擎与 Agent 编排分离、规则 ID 可追踪、报告可持久化、测试数据库隔离。
- 当前最大风险：Markdown 规则只用于检索展示，真正决策仍由 `audit_engine.py` 中的硬编码决定，两者已经存在语义偏差。
- 当前语言不是瓶颈：Python + FastAPI 与该项目的 Agent、RAG、API 和快速验证需求匹配，不建议为了简历整体换语言。
- 当前没有 P0 启动阻断问题；主要问题集中在 P1 正确性、契约、幂等性与上线安全边界。
- 下一阶段不应先接 LLM；应先把规则一致性、金额模型、API 契约、评测集和可观测性补齐。

## 2. Project Overview

### 2.1 简化目录树与职责

```text
travel-reimbursement-agent/
├── app/
│   ├── main.py              # FastAPI 生命周期、路由和 HTTP 异常映射
│   ├── config.py            # 环境变量、数据库和规则文件路径
│   ├── database.py          # SQLAlchemy Engine、Session 和建表
│   ├── models.py            # Trip/Expense/Receipt/AuditReport ORM
│   ├── schemas.py           # 行程、费用、凭证和报告 Pydantic 模型
│   ├── crud.py              # 数据库读写
│   ├── rag.py               # Markdown 规则切分与关键词检索
│   ├── audit_engine.py      # 确定性审核和状态聚合
│   ├── agent.py             # 固定六步编排与执行轨迹
│   └── reporting.py         # 报告 JSON 解析与 API 格式化
├── data/
│   ├── rules/               # 10 条 Markdown 企业报销规则
│   ├── mock/                # 1 个行程、6 笔费用、5 张凭证
│   └── reimbursement.db     # 本地 SQLite 运行数据，Git 忽略
├── scripts/
│   ├── seed_mock_data.py    # 重置并导入演示数据，有数据副作用
│   └── demo_walkthrough_check.py # 重置数据并跑主链路，有数据副作用
├── tests/                   # pytest，使用临时 SQLite 文件
├── docs/                    # 架构、API、Demo、面试与本审计报告
├── .github/workflows/ci.yml # Python 3.11/3.12 CI
├── requirements.txt         # 运行依赖
├── requirements-dev.txt     # pytest/httpx 开发依赖
└── README.md                # 项目说明与演示入口
```

当前规模：`app/` 约 999 行 Python，`tests/` 约 256 行，`scripts/` 约 174 行；规模适合维持当前简单分层，不需要微服务化。

### 2.2 技术全景

| 项目 | 当前实现 | 判断 |
| --- | --- | --- |
| 编程语言 | Python | 合适 |
| Web/API | FastAPI + Uvicorn | 已形成 12 个业务路由 |
| 数据库 | SQLite + SQLAlchemy 2.x | MVP 可用，缺迁移和外键启用 |
| 数据校验 | Pydantic 2.x | CRUD 有模型，审核/检索响应缺模型 |
| Agent 框架 | 无 | 手写固定工作流，不是框架套壳 |
| LLM/模型调用 | 无 | 不产生 Token 或模型成本 |
| Prompt | 无 | 不存在 Prompt 工程 |
| Tool/Function Calling | 普通 Python 函数调用 | 没有标准 Tool Schema 或模型选择工具 |
| RAG | Markdown + 空格分词关键词计数 | 可演示，检索结果不参与最终规则执行 |
| Memory | 无 | 无会话状态、短期或长期记忆 |
| MCP | 无 | 当前无必要 |
| Workflow | 固定六步同步流程 | 可运行、无无限循环风险 |
| 外部服务 | 无 | 无票务、地图、天气、OCR 或支付服务 |
| 前端 | 无 | 仅 Swagger/API |
| 配置 | pydantic-settings + `.env` 支持 | 路径稳健，`debug=True` 默认值不适合公网 |
| 测试 | pytest + FastAPI TestClient + 临时 SQLite | 14 项通过，覆盖率尚未测量 |
| CI/CD | GitHub Actions CI | 仅 CI，无 CD；Python 3.11/3.12 |
| 部署 | 无 Docker/Nginx/服务器清单 | 未形成可复现部署 |
| 日志/观测 | 无结构化日志、指标、Tracing | 明显缺口 |
| 文档 | README + 5 份 docs（含本报告） | 演示材料较完整 |

本地安装版本为 Python 3.13.4、FastAPI 0.136.1、SQLAlchemy 2.0.49、Pydantic 2.13.4。依赖文件只设置下限，没有锁定可复现版本。

## 3. Architecture

### 3.1 实际业务调用链

项目没有自然语言入口。真实 Agent 链路是：

```text
HTTP POST /agent/audit/trips/{trip_id}
  -> FastAPI 依赖注入 SQLAlchemy Session
  -> run_reimbursement_audit_agent()
     -> crud.get_trip()
     -> crud.list_expenses_by_trip()
     -> 对每笔费用按类别拼接固定关键词
     -> rule_rag.search() 返回最多 3 条规则证据
     -> audit_engine.audit_trip() 执行硬编码规则
     -> crud.create_audit_report() 提交 SQLite 事务
     -> build_final_decision() 生成固定文案
  -> Python dict JSON 响应
```

普通审核接口 `/audit/trips/{trip_id}` 会跳过规则检索和 Agent 轨迹，直接执行审核并落库。

### 3.2 Agent 类型判断

最准确分类是：

> **固定 Workflow Agent + 关键词 RAG 证据检索 + 确定性规则引擎。**

它不是 ReAct、Planner-Executor、动态 State Machine、Multi-Agent 或 LLM Tool Calling Agent。六个步骤是代码中固定顺序执行，不会根据上下文改变计划，也没有模型参与工具选择。

### 3.3 Agent 工程检查

| 检查项 | 状态 | 说明 |
| --- | --- | --- |
| Prompt | 不存在 | 无硬编码 Prompt、Prompt 过长或注入风险 |
| Tool Schema | 未实现 | CRUD/RAG/审核只是普通函数，不是可验证工具协议 |
| 输入输出结构化 | 部分 | 内部返回 dict；Agent API 无 Pydantic 响应模型 |
| 动态规划 | 未实现 | 流程固定，不能称自主规划 |
| 无限循环/max iterations | 无风险/不适用 | 没有模型循环 |
| timeout/retry/circuit breaker | 不适用 | 当前没有外部网络调用；未来接 API 后必须增加 |
| fallback | 部分缺失 | 缺数据时抛明确异常；RAG 或报告保存失败无降级 |
| 错误分类 | 部分 | 仅区分行程不存在和无费用；数据库/规则错误未分类 |
| 状态管理 | 部分 | 成功步骤存在内存列表，最终报告入库；失败轨迹不会返回或保存 |
| Context/Memory | 未实现 | 无多轮会话，不存在 context 膨胀 |
| Token/模型成本 | 不适用 | 当前模型调用次数和 Token 均为 0 |
| 重复调用 | 存在轻微冗余 | 相同类别的多笔费用会重复执行相似 RAG 查询 |
| Agent 过度设计 | 轻微命名风险 | 流程本身不复杂；若宣传为高级自主 Agent 会过度包装 |

### 3.4 “代码存在”与“链路完成”检查

| 能力 | 状态 | 真实证据与边界 |
| --- | --- | --- |
| 自然语言差旅需求 | 未完成 | API 只接收结构化 JSON |
| 出发地/目的地 | 部分完成 | ORM/API 可存储，未做自然语言解析或地理校验 |
| 日期理解 | 部分完成 | ISO 日期校验，未理解自然语言日期 |
| 行程规划 | 未完成 | 无路线、日程或约束求解 |
| 机票/火车票/酒店查询 | 未完成 | “住宿/交通”只是费用类别 |
| 天气/地图/路线 | 未完成 | 无外部 API |
| 预算约束 | 部分完成 | 有单笔金额阈值，无总预算或策略配置 |
| 企业差旅政策 | 部分完成 | Markdown/RAG 可用，但执行规则未完全对齐文档 |
| 审批 | 只有状态占位 | 有 NEEDS_REVIEW/REJECTED，无审批任务与操作记录 |
| 报销 | 已完成 MVP | 行程、费用、凭证录入与审核报告链路可运行 |
| 发票/凭证 | 部分完成 | 只存元数据，不上传、不 OCR、不验证真伪 |
| Agent 自动规划 | 未完成 | 固定六步，不动态规划 |
| 多工具调用 | 部分完成 | 编排多个内部函数，无标准工具抽象或 Function Calling |
| 多轮对话/上下文保持 | 未完成 | 无会话模型 |
| 结构化输出 | 部分完成 | JSON 字典可用，多个端点缺响应 Schema |
| RAG | 已完成基础版 | 10 个规则块可检索；结果仅作证据展示 |
| Memory | 未完成 | 无 |
| 外部 API | 未完成 | 无 |
| MCP | 未完成 | 无，当前也无必要 |
| Workflow/State Machine | 已完成基础版 | 固定六步同步工作流，不是通用状态机 |
| Human-in-the-loop | 只有语义占位 | 会标记人工复核，但没有任务领取、处理和回写闭环 |

## 4. Current Progress

| 模块 | 当前状态 | 完成度 | 证据 | 主要问题 |
| --- | --- | ---: | --- | --- |
| 用户交互 | Swagger/API | 30% | `app/main.py` | 无前端、CLI 交互或自然语言入口 |
| API | 基本可用 | 75% | 12 个业务路由 | 7 个路由 OpenAPI 响应 Schema 为空，缺分页/统一错误契约 |
| Agent Core | 固定编排可用 | 55% | `app/agent.py:99-161` | 无动态决策、失败轨迹、幂等性 |
| Prompt | 未实现 | 0% | 无 Prompt 文件/字符串 | 当前不应虚构该能力 |
| LLM | 未实现 | 0% | 无模型 SDK/调用 | 当前不是 LLM Agent |
| Tool Calling | 内部函数编排 | 25% | CRUD/RAG/audit 函数 | 无 Tool Schema、注册表和标准错误模型 |
| Workflow | 主链路可用 | 80% | 固定六步和测试 | 同步、固定、不可恢复 |
| 数据层 | MVP 可用 | 65% | 4 张表、CRUD | Float 金额、无迁移、SQLite FK 未启用 |
| 外部 API | 未实现 | 0% | 无 HTTP 客户端调用 | 无票务/天气/地图/OCR |
| Memory | 未实现 | 0% | 无会话表或状态存储 | 当前业务不必强行加入 |
| RAG | 基础可用 | 60% | `app/rag.py`、10 条规则测试 | 空格分词、简单计数、无评测、与执行引擎解耦 |
| 前端 | 未实现 | 0% | 无前端目录 | 面试 Demo 依赖 Swagger |
| 后端 | MVP 可用 | 70% | FastAPI/SQLAlchemy | 同步单机、契约与可靠性不足 |
| 异常处理 | 部分 | 50% | 404/400 与 JSON 解析兜底 | DB 异常、规则加载错误无统一分类 |
| 日志 | 基本未实现 | 10% | 仅脚本 `print` | 无 request_id、结构化日志和审计事件 |
| 测试 | 基础可用 | 60% | 14 tests | 无覆盖率、参数化规则矩阵、并发/幂等测试 |
| 安全 | 本地 Demo 边界 | 25% | `.env`/DB 已忽略 | 无认证授权、默认 debug、PII 明文、无速率限制 |
| 配置 | 基础可用 | 65% | `app/config.py` | debug 默认开启；无环境分层与启动校验 |
| 部署 | CI 已有，部署未做 | 25% | GitHub Actions | 无 Docker、健康探针部署、回滚或 CD |
| 文档 | 演示级较完整 | 80% | README、architecture、demo、API | 基线 README 尚未包含当前未提交的文档修复 |

### 总体完成度

分类：**MVP**。

理由：核心报销审核链路可运行、数据可持久化、错误结果可解释、已有自动化测试和 CI；但业务规则正确性、API 契约、幂等、观测、部署和评测尚不足以称“可用项目”或“Production-like”。

## 5. Agent Analysis

### 5.1 值得保留的控制边界

`app/agent.py` 负责编排，`app/audit_engine.py` 负责确定性合规判断，这个方向正确。报销合规不应由生成式模型直接决定；未来即使加入 LLM，也应只让 LLM 做意图解析、工具选择、信息补全提示或解释生成。

### 5.2 当前 Agent 的核心缺口

1. `retrieved_rules` 没有传给审核引擎，RAG 命中不会改变审核结果。
2. 每个类别的查询由 `build_rule_query_for_expense()` 硬编码，不能根据规则元数据自动构造。
3. “步骤”只是执行后追加的展示记录，不是可暂停、恢复或分支的状态机。
4. 失败时步骤列表随异常丢失，无法形成失败审计轨迹。
5. 同一 trip 重复调用会重复保存报告，没有 request key、版本号或去重策略。
6. 没有 Agent Evaluation 数据集，无法证明规则召回率、任务成功率或稳定性。

### 5.3 是否应该马上接 LLM

不应该。当前首先要解决确定性层的一致性与可测性。若规则执行本身不准确，加入 LLM 只会增加不可控性、成本和调试复杂度。

未来最小合理接入点是：

```text
自然语言费用说明
  -> LLM 输出受 Pydantic/JSON Schema 约束的类别与缺失字段
  -> 人工确认或置信度门槛
  -> 确定性规则引擎作最终判断
```

## 6. Engineering Audit

### 6.1 P0：严重问题

本轮未发现导致当前本地 MVP 无法启动、数据立即损坏或凭据泄漏的 P0 问题。若直接暴露到公网，“无认证 + `debug=True`”应升级为部署阻断项。

### 6.2 P1：重要问题

| Current Design | Problem | Proposed Design | Expected Benefit | Cost / Risk |
| --- | --- | --- | --- | --- |
| Markdown 用于 RAG，Python 代码独立硬编码规则 | 两套事实源已偏离；RAG 证据不能证明执行了该规则 | 建立类型化规则注册表；Markdown 作为说明或由同一结构化规则生成；每条执行结果记录规则版本 | 正确性、可追踪性和面试深度显著提升 | 中；需要规则契约和迁移测试 |
| `category in {交通, 市内出行}` 且金额大于 300 即标记 | `R-TRAFFIC-002` 是市内出行参考，城际高铁/机票可能被误报 | 区分 `INTERCITY_TRAFFIC` 与 `LOCAL_TRAFFIC`，或增加交通子类型 | 消除明显误报 | 低至中；需要数据字段和兼容策略 |
| 住宿整笔金额直接与 800 比较 | 文档定义“指定城市、每晚 800”，实现忽略城市与晚数 | 增加 `night_count`/入住退房信息并按目的地策略计算 | 规则语义与业务一致 | 中；涉及 schema/model/migration |
| API 在录入费用时拒绝行程外日期，Demo 直接写库制造异常 | 正常 API 用户无法提交该异常给审核引擎，演示链路不代表真实链路 | 明确边界：录入只做格式校验，合规性留给审核；或把该项从审核规则移到 API 校验并调整 Demo | 业务职责一致、端到端测试真实 | 低；需选择产品语义 |
| 金额使用 `Float` | 财务金额存在二进制浮点误差风险 | 使用 `Decimal` + SQL `Numeric(precision, scale)`，统一舍入策略 | 财务正确性和专业度 | 中；涉及迁移与序列化 |
| 多个审核/报告/RAG端点直接返回 dict | OpenAPI 中 7 个路由响应 Schema 为空，契约不可验证 | 为规则命中、审核项、报告、Agent step/final decision 定义 Pydantic 响应模型 | API 契约、客户端生成、测试质量提升 | 中；结构需要一次梳理 |
| 每次 POST 审核都创建新报告 | 重试会生成重复报告，缺乏幂等性和规则版本 | 增加 `audit_run_id` 或 `Idempotency-Key`，记录 trip 数据摘要与 rule_version | 支持安全重试和可审计历史 | 中；需要唯一约束 |
| SQLite Engine 未启用 FK pragma | 当前只读检查显示 `PRAGMA foreign_keys=0`，数据库不会强制引用完整性 | connect event 中启用外键；补迁移/删除测试 | 防止孤儿记录 | 低；需验证 reset 顺序 |
| 默认 `debug=True` 且无认证 | 公网部署可能暴露异常详情和所有员工报销数据 | 默认关闭 debug；部署前增加最小认证授权和环境校验 | 满足基本上线安全边界 | 中；本地 Demo 可保留显式开发配置 |

### 6.3 P2：一般优化

| 问题 | 证据 | 建议 |
| --- | --- | --- |
| Pydantic v1 风格 `class Config` | pytest 产生 4 个弃用 warning | 改用 `ConfigDict(from_attributes=True)` |
| ORM 映射风格混合 | `Column` 与 `Mapped/mapped_column` 混用 | 后续机械统一，不与业务改造混在一起 |
| 一对一关系表达不清 | `Expense.receipt.uselist=True`，`Receipt.expenses` 命名却是复数 | 双端统一 singular 并设置明确 `uselist=False`/级联 |
| 类型大量使用 `Any`/裸 `Dict` | audit、agent、reporting | 引入内部 dataclass/Pydantic DTO，不必引入新框架 |
| `main.py` 同时做路由、校验、格式化 | 约 302 行 | 在端点继续增长时按 trips/audit/rules 拆 router；现在不必大重构 |
| RAG 在 import 时全局加载 | `rule_rag = MarkdownRuleRag(...)` | 增加显式启动校验、规则版本/重载策略 |
| 中文检索要求空格分词 | `query.split()` | 先用规则别名和领域词表增强；有评测数据后再决定 BM25/embedding |
| 无结构化日志 | 无 `logging` 使用 | 增加 request_id、trip_id、audit_run_id、耗时和错误分类字段 |
| 依赖只设下限 | `requirements*.txt` | 发布时增加锁定/约束文件并由 CI 验证，避免不可复现升级 |
| 测试生命周期仍触发全局 `init_db()` | TestClient 执行应用 lifespan | 让 app factory 接收测试配置，彻底隔离正式 Engine |

### 6.4 规则覆盖差异

| 规则 | 执行状态 | 说明 |
| --- | --- | --- |
| R-GEN-001 | 已实现但链路冲突 | API 先拒绝异常日期，Mock 绕过 API |
| R-GEN-002 | 已实现 | 缺凭证统一按 high 处理 |
| R-GEN-003 | 已实现但正常 API 不可达 | Pydantic `gt=0` 已拦截 |
| R-TRAFFIC-001 | 未实现 | 未判断用途是否明确/与行程相关 |
| R-TRAFFIC-002 | 部分且可能误报 | 对全部“交通”套 300 元阈值 |
| R-HOTEL-001 | 部分实现 | 未处理城市和每晚金额 |
| R-HOTEL-002 | 未实现 | 未验证凭证类型/销售方 |
| R-MEAL-001 | 已实现 | 150 元单笔阈值 |
| R-MEAL-002 | 被通用规则部分覆盖 | 没有独立标记或有效性校验 |
| R-OTHER-001 | 已实现基础版 | 未判断描述清晰度与出差相关性 |

### 6.5 安全与可靠性边界

- 未发现 API Key、Token、私钥或密码硬编码。
- SQLAlchemy 参数化查询降低了 SQL 注入风险。
- `.env`、数据库和虚拟环境已被 Git 忽略。
- 无认证、授权、速率限制和数据隔离，不应直接公网开放。
- 员工姓名、部门和报销信息以明文 SQLite 保存，没有保留期或脱敏策略。
- 当前无外部 HTTP 调用，因此 timeout/retry/circuit breaker 不是现阶段缺陷；接入外部服务时才需要。
- 同步 FastAPI + SQLite 对当前小型 Demo 足够；盲目改 async 不会自动提升吞吐。

## 7. Language / Refactor Decision

| 方案 | Agent 生态 | Web/API | 并发 | 开发效率 | 性能 | 工程复杂度 | 求职价值 | 是否建议 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Python | 很强 | 很强 | I/O 场景足够 | 很高 | 当前足够 | 低 | AI/后端均高 | **保留** |
| Go | 一般 | 很强 | 很强 | 高 | 高 | 中 | 后端岗位较高 | 当前不换；未来仅适合独立高并发网关 |
| Java | 一般 | 很强 | 很强 | 中 | 高 | 中高 | 企业后端较高 | 当前规模不值得 |
| C++ | 弱 | 可做但成本高 | 强 | 低 | 很高 | 很高 | C++ 岗位高 | 不适合整体重构 |
| TypeScript/Node.js | 较强 | 很强 | I/O 场景强 | 高 | 足够 | 中 | 全栈/AI 应用较高 | 可替代但无迁移收益 |

### 结论

**不需要换语言。**

当前瓶颈是业务规则建模、事实源一致性、评测和可靠性，而不是 CPU 或运行时性能。整体换成 Go、Java、C++ 或 TypeScript 会重写大量已工作的 API/数据代码，却不会解决规则误报、RAG 与执行脱节、幂等和缺评测等核心问题。

若未来基准证明批量规则计算是 CPU 瓶颈，可以把纯规则求值器做成可独立 benchmark 的模块，再评估 Rust/C++ 扩展；在当前数据规模下没有工程依据。

## 8. Resume Readiness

### 8.1 面试官评分

| 岗位 | 评分 | 面试官判断 |
| --- | ---: | --- |
| C++ 后端 | 3/10 | 几乎没有 C++、系统编程、网络或性能证据，只能体现基础后端思维 |
| 通用后端 | 6/10 | API、ORM、测试、CI、异常状态和持久化链路完整；缺迁移、幂等、日志、部署和指标 |
| AI Agent | 5/10 | 有工作流和 RAG 边界意识，但没有 LLM、动态 Tool Calling、状态机或 Agent Eval |
| AI 应用 | 6/10 | 业务问题真实、结果可解释、不是 LangChain 套壳；但智能能力和真实数据链路较弱 |

### 8.2 是否可以写进简历

可以，但当前更适合作为第二项目或 MVP 版本，推荐描述：

> 基于 FastAPI、SQLAlchemy 与 Markdown 规则检索实现企业差旅报销审核 MVP；设计固定六步编排，将规则证据检索与确定性合规判断分离，并持久化可追踪 JSON 审核报告；使用临时 SQLite 测试隔离和 Python 3.11/3.12 CI 验证主链路。

不要写：

- “基于大模型自主规划”；
- “多 Agent 协作”；
- “调用多个外部工具”；
- “支持自然语言差旅规划”；
- “生产级高并发”；
- 未实际测量的准确率、QPS 或成本数字。

### 8.3 当前教程感来源

- 只有一套固定 Mock 场景，容易显得为预期结果定制。
- RAG 命中只展示，不约束执行结果。
- Agent 是固定函数顺序，缺少分支、恢复或评测。
- 无性能、正确率、覆盖率和失败恢复指标。
- 无可复现容器部署和线上观测。

## 9. Missing Capabilities

### 9.1 真正值得补充

1. **规则一致性与版本化**：提升正确性，是最高 ROI。
2. **结构化响应契约**：让 Agent/报告真正可验证。
3. **规则评测集**：从单个 Demo 变成可量化系统。
4. **金额与幂等性设计**：体现后端基本功。
5. **结构化日志与 request/audit ID**：支撑故障分析。
6. **Docker + 一条命令复现**：提升交付可信度。
7. **最小 Human-in-the-loop 闭环**：只有在规则正确性完成后再做。

### 9.2 暂时不值得加入

- Redis：当前没有跨实例状态、热点缓存或分布式锁需求。
- Kafka：没有异步事件吞吐或解耦需求。
- 微服务/Kubernetes：规模不足，只会增加运维表面积。
- MCP：当前内部工具少且同进程，普通接口足够。
- 向量数据库：只有 10 条规则，先建立检索评测再决定。
- 多 Agent：任务可以由一个确定性工作流完成。
- 长期 Memory：报销审核是以 trip/audit run 为边界的结构化任务，数据库状态优于聊天记忆。

## 10. Technical Highlights

### 10.1 确定性审核与编排解耦

- 当前实现：真实存在。
- 位置：`app/agent.py:99-161`、`app/audit_engine.py:52-175`。
- 难点：确保 Agent 负责编排、规则引擎负责可重复决策。
- 面试追问：为什么不让 LLM 决定合规？未来如何接 LLM？
- 不足：RAG 证据尚未成为规则执行输入，边界只完成一半。

### 10.2 六步可解释执行轨迹

- 当前实现：真实存在。
- 位置：`LOAD_TRIP` 到 `RETURN_FINAL_DECISION`。
- 难点：把数据加载、检索、审核、持久化和决策拆成可读步骤。
- 面试追问：失败后如何恢复？如何做幂等？为什么不使用状态机框架？
- 不足：步骤固定且只在成功响应中可见，失败轨迹不落库。

### 10.3 Markdown 规则切分与关键词检索

- 当前实现：真实存在，加载 10 个规则块。
- 位置：`app/rag.py:9-168`、`data/rules/company_travel_policy.md`。
- 难点：只识别规则标题，保留规则 ID、标题和正文，并支持中文关键词/编号检索。
- 面试追问：如何评估 Top-K？为什么不用 embedding？规则更新如何热加载？
- 不足：仅空格分词和词频计数，无同义词、元数据过滤、召回评测。

### 10.4 可追踪 JSON 报告持久化

- 当前实现：真实存在。
- 位置：`app/crud.py:77-126`、`app/reporting.py`。
- 难点：保存汇总、明细、规则 ID、异常标记，并支持详情/历史/最新查询。
- 面试追问：为什么存 JSON text？如何做 schema evolution？如何保证幂等？
- 不足：无 schema_version/rule_version，JSON 字段不可索引，重复审核会重复写入。

### 10.5 测试数据库隔离与 CI 矩阵

- 当前实现：真实存在。
- 位置：`tests/conftest.py`、`.github/workflows/ci.yml`。
- 难点：FastAPI dependency override 配合临时 SQLite，避免 pytest 污染演示数据。
- 面试追问：生命周期为什么仍可能接触全局 Engine？如何做集成测试？
- 不足：覆盖率未测，规则边界和失败路径不足；CI Actions 版本出现 Node.js 20 弃用 warning。

## 11. Metrics & Benchmark Plan

### 11.1 当前已有的可验证数字

| 指标 | 当前值 | 性质 |
| --- | ---: | --- |
| 自动化测试 | 14 passed | 本轮实测 |
| pytest warning | 4 | Pydantic 弃用提示 |
| 规则块 | 10 | 代码/测试实测 |
| Demo 费用 | 6 | Mock 数据 |
| Demo 凭证 | 5 | Mock 数据 |
| FastAPI 业务路由 | 12 | OpenAPI 实测 |
| CI Python 版本 | 3.11、3.12 | Workflow 配置与远程成功运行 |

这些是规模/交付指标，不等于准确率或性能指标。

### 11.2 当前尚未测量

- API P50/P95/P99 latency；
- 并发吞吐和错误率；
- 审核 decision accuracy / rule precision / recall；
- RAG Recall@K、MRR；
- Agent task success rate；
- 幂等重试重复报告率；
- 测试覆盖率；
- 外部接口失败恢复率；
- Token usage 和单次成本（当前无 LLM，因此应记为“不适用”，不是 0 成本宣传）。

### 11.3 建议 Benchmark 方法

1. 建立不少于 100 个匿名合成费用案例，每个案例标注期望规则 ID、flags 和最终状态。
2. 规则引擎指标：逐条规则计算 precision、recall、exact decision match，并单列边界值 `150/300/800`。
3. RAG 指标：对每条规则准备 5-10 个查询，测 Recall@1、Recall@3、MRR，并包含无空格中文、同义词和规则编号。
4. API 性能：固定 SQLite 数据集，预热后以 1/10/50 并发测试 `/rules/search`、报告查询和审核；记录 P50/P95、吞吐、错误率和硬件/版本。
5. 幂等测试：同一个 key 重试 10 次，只允许一个 audit run/report。
6. 覆盖率：引入 coverage 后按模块报告，不追求虚高总百分比，优先保证所有规则分支和错误路径。
7. 若未来接 LLM，再增加 schema-valid rate、tool-call success rate、平均 Tool Calls、Token 和成本；当前不要伪造。

## 12. Roadmap

### Phase 0：必须修（正确性与上线阻断）

| Priority | 工作项 | Difficulty | Expected Value | Resume Value | Estimated Scope | Files / Modules |
| --- | --- | --- | --- | --- | --- | --- |
| P0.1 | 定义规则单一事实源并补 10 条规则映射测试 | 中 | 极高 | 极高 | 2-3 天 | `audit_engine.py`、规则模型、tests |
| P0.2 | 修正交通分类、住宿每晚/城市和凭证有效性语义 | 中 | 极高 | 高 | 2-3 天 | schemas/models/rules/audit tests |
| P0.3 | 明确录入校验与审核规则边界 | 低 | 高 | 中 | 0.5-1 天 | `main.py`、API tests、Demo |
| P0.4 | 公网部署前关闭 debug 并增加最小认证边界 | 中 | 高 | 高 | 1-2 天 | config/security/API tests |

### Phase 1：让项目成为合格 MVP

| Priority | 工作项 | Difficulty | Expected Value | Resume Value | Estimated Scope | Files / Modules |
| --- | --- | --- | --- | --- | --- | --- |
| P1.1 | 金额改为 Decimal/Numeric，定义舍入策略 | 中 | 高 | 高 | 1-2 天 | models/schemas/migration/tests |
| P1.2 | 为 RAG、Audit、Agent、Report 增加响应模型 | 中 | 高 | 高 | 1-2 天 | schemas/main/tests |
| P1.3 | 增加 audit_run/rule_version 和幂等键 | 中高 | 高 | 极高 | 2-3 天 | models/crud/agent/API/tests |
| P1.4 | 启用 SQLite FK，增加 Alembic 迁移基线 | 中 | 高 | 高 | 1-2 天 | database/migrations/tests |
| P1.5 | 失败分类与事务边界统一 | 中 | 高 | 高 | 1-2 天 | crud/agent/main/tests |

### Phase 2：达到简历级

| Priority | 工作项 | Difficulty | Expected Value | Resume Value | Estimated Scope | Files / Modules |
| --- | --- | --- | --- | --- | --- | --- |
| P2.1 | 建立规则/RAG黄金评测集和指标脚本 | 中 | 极高 | 极高 | 2-4 天 | evals/data/tests/scripts |
| P2.2 | 覆盖率门槛、参数化边界测试、CI 更新 | 中 | 高 | 高 | 1-2 天 | tests/CI/dev deps |
| P2.3 | request_id、结构化日志、审核耗时指标 | 中 | 高 | 高 | 1-2 天 | middleware/agent/logging |
| P2.4 | Docker 化并验证一条命令启动 | 低中 | 高 | 高 | 1 天 | Dockerfile/compose/README |
| P2.5 | API load test 与可复现实验报告 | 中 | 高 | 极高 | 1-2 天 | benchmarks/docs |

### Phase 3：形成 1-3 个真正亮点

| Priority | 深化方向 | Difficulty | Expected Value | Resume Value | Estimated Scope | Files / Modules |
| --- | --- | --- | --- | --- | --- | --- |
| P3.1 | 可版本化 Policy-as-Data 执行器与解释链 | 高 | 极高 | 极高 | 1-2 周 | rules/compiler/evaluator/report |
| P3.2 | Human-in-the-loop 复核闭环与状态审计 | 中高 | 高 | 高 | 1 周 | models/API/workflow/tests |
| P3.3 | 受结构化约束的 LLM 分类/解释层 + Agent Eval | 高 | 高 | 极高（AI岗） | 1-2 周 | llm adapter/evals/config/tests |

不要同时展开三个方向。优先选择 P3.1；目标 AI Agent 岗再选择 P3.3；目标通用后端岗可选择 P3.2。

## 13. Interview Questions

建议准备以下 10-20 分钟追问：

1. 为什么报销合规必须由确定性引擎而不是 LLM 决定？
2. 既然 RAG 不参与决策，它的业务价值是什么？如何避免检索证据与执行规则不一致？
3. 为什么当前系统可以称 Workflow Agent，但不能称 ReAct Agent？
4. 交通 300 元规则如何区分机票、高铁和市内打车？
5. 住宿 800 元/晚需要哪些字段才能准确审核？
6. 为什么财务金额不应该使用 Float？
7. 同一审核请求重试后如何避免生成重复报告？
8. 如何设计 rule_version 和 audit_run，保证历史报告可复现？
9. 临时 SQLite 测试如何隔离正式数据库？当前 lifespan 还有什么隐患？
10. 如何定义 Agent task success rate，而不是只展示一次成功 Demo？
11. 什么时候关键词检索足够，什么时候才值得使用 embedding？
12. SQLite 何时需要替换为 PostgreSQL？迁移依据是什么？
13. 若接入 OCR/票务 API，timeout、retry 和 circuit breaker 分别放在哪里？
14. 为什么当前不需要 Redis、Kafka、MCP 或多 Agent？
15. 如何让失败执行轨迹也可追踪，并支持人工复核？

## 14. Final Recommendation

### A. 当前项目是什么水平？

**MVP**。它有完整后端主链路、测试和 CI，但正确性模型、契约、评测、观测和部署不足，尚非 Resume-ready 主打项目，更不是 Production-like。

### B. 当前最值得保留的设计是什么？

保留“Agent 编排、RAG 证据、确定性审核、报告持久化”分层，以及测试数据库隔离。尤其应坚持确定性引擎对合规结果拥有最终权威。

### C. 当前最应该删除或简化的设计是什么？

不需要删除核心模块。应简化“高级 Agent”叙事：把固定六步准确称为 workflow，避免把普通函数调用包装成自主 Tool Calling。代码层面应删除重复的规则事实源，而不是删除 RAG 或审核引擎。

### D. 是否需要换语言？

**不需要。** 当前语言不是项目核心瓶颈，不建议为了简历而换语言。

### E. 如果只能再开发 7 天，ROI 最高的 5 件事

1. 修正规则执行偏差，建立 10 条规则的参数化黄金测试集。
2. 为金额使用 Decimal/Numeric，并补边界值测试。
3. 增加审核/Agent/RAG/report Pydantic 响应模型和 OpenAPI 契约测试。
4. 增加 audit_run/rule_version/幂等设计，并验证重复请求。
5. 输出覆盖率、RAG Recall@K、规则准确率和 API P95 的可复现实测报告；余量用于 Docker 化。

### F. 按求职方向调整

#### AI Agent 岗位

先做规则/RAG评测与结构化 Tool 接口，再增加一个受 JSON Schema 约束的 LLM 分类或解释步骤；重点展示失败回退、Agent Eval、Token/成本和确定性护栏。不要直接上多 Agent。

#### 通用后端岗位

优先做 Decimal、迁移、幂等、事务、认证、结构化日志、Docker、负载测试和 PostgreSQL 迁移条件；Agent 只作为业务工作流背景。

#### C++ 后端岗位

把本项目作为辅助项目，突出规则引擎、数据契约、测试和 benchmark。更建议另准备一个真正体现 C++ 网络/并发/性能的主项目；只有 benchmark 证明规则批处理是瓶颈时，才把纯规则求值器局部改成 C++ 并提供 Python 绑定及性能对比。

## 15. Verification Record

本轮实际执行结果：

- `python -m compileall -q app tests`：通过。
- `python -m pip check`：`No broken requirements found.`
- `python -m pytest -q`：`14 passed, 4 warnings in 0.53s`。
- OpenAPI：12 个业务路由；7 个路由成功响应 Schema 为空。
- SQLite 只读检查：4 张表，数据量为 1 trip、6 expenses、5 receipts、1 audit report；`PRAGMA foreign_keys=0`。
- 敏感关键字扫描：无命中。
- ruff、mypy、pyright、bandit、coverage：当前环境未安装，因此未执行，也未临时增加依赖。
- Demo walkthrough：本轮未执行，因为脚本会调用 `reset_database_data()` 并修改正式本地数据库；已有 pytest 主链路验证通过。
- 远程 GitHub Actions：基线 `cd9a965` 的 CI #1 状态为 Success，Python 3.11/3.12 两个任务完成；页面显示 Actions 运行时弃用 warning。

## 16. 最终行动建议

建议下一轮只启动一个小范围改造：

```text
Current Design
  Markdown 规则 + 硬编码审核规则并存

Problem
  证据与执行可能不一致，已有交通/住宿语义偏差

Proposed Design
  定义类型化、可版本化的规则注册表，并为 10 条规则建立黄金测试

Expected Benefit
  先解决正确性，再为 RAG、LLM、评测和简历指标建立可信基础

Cost / Risk
  约 2-3 天；需要谨慎定义兼容字段，不应与数据库大迁移同时进行
```

完成该项并获得评测结果后，再决定是否进入响应模型、Decimal、幂等和部署工程化。不要从增加 LLM、向量数据库或微服务开始。
