# Agent Handoff · Baby Joy

## 目的
本仓库交付的是**微信小程序 + API + 后端统一 GPU 生产**的可实施蓝图，现阶段非已运行产品。建议后续由本地 Codex/Pi Agent 逐阶段实现，仍须尊重用户儿童信息保护与发布限制。

## 每次执行第一步
1. 读取 README、00、03、04、05、06、07、09、11、12、13、14 和 gotchas。
2. 检查 `git status`, `git branch -vv`, `git log -5`, 远程 PR 与 CI；确认 base SHA，禁止覆盖他人本地修改。
3. 写简短 implementation plan，将每个需求映射到相应 API、schema、测试和可验证门槛。
4. Phase 0 先判断真实 GPU/模型权重和监护授权素材是否就绪；缺失时采用 Mock 模型进行业务工程验证，但 **不得标记真实 GPU 验收通过**。

## 编码与仓库约定
```text
apps/miniprogram/         原生微信小程序 TS
services/api/             FastAPI
services/workers/         CPU/队列/视频生成适配器
packages/contracts/       OpenAPI generated client & shared schemas
infra/                    Compose、Nginx、监控（未实现）
specs/                    设计契约与初始 SQL 草案（需迁移框架接管）
benchmarks/               脱敏实验 manifest 与报告
docs/                     ADR、需求、运维、gotchas
```
不得提交 `.env`、AppSecret、儿童照片/视频、声纹、私有模型权重、签名下载 URL、真实用户日志。每个业务操作都要验证 user scope、监护授权和最小数据收集。

## 实施优先级
P0：模型许可+真实样本实验；后端安全骨架、存储/授权/幂等/状态机；微信真机流程。
P1：Baby-Aware QC、可观测性、取消删除竞争条件、成本/吞吐。
P2：支付、复杂分享、多人、长期纪念故事（须另行评估）。

## 必须执行的验收
- 单元与 OpenAPI contract；Alembic 新建/升级/回滚；真实 Postgres/Redis/Object Store 集成；队列重复投递和 worker 故障恢复；跨用户 IDOR；删除数据/对象/缓存；小程序真机 iOS + Android；
- GPU 模型测试记录原始命令、运行环境、模型修订、合法授权和抽样结果；没有硬件时 `NOT RUN`。
- 任意失败均记录到 docs/gotchas.md：复现步骤、日志/错误、根因、修复、回归测试、状态。
- 不人为编造测试结果，不弱化安全约束，不绕过 CI，不删除失败的测试；有歧义以 API 的不变量和儿童隐私原则优先。

## PR 模板
```text
Title:
Base SHA / Branch:
Scope:
Files changed:
Assumptions / ADR changes:
Commands actually run:
PASS:
FAIL:
NOT RUN:
Real GPU / WeChat device evidence:
Performance / quality metrics:
Security & privacy impact:
Migration & rollback:
Gotchas updated:
Open risks:
```
每个 PR 保持独立，需审核后合并。用户没有要求直接合并时，不自动 merge。

## 技术路线决策规则
不要一开始微调婴儿专用视频模型或接支付；先完成真实输入的婴儿基线、许可证确认与基本业务服务。若性能或质量劣于验收阈值，更新风险登记并提出替代路线，不允许“Demo 成功＝产品就绪”。
