# Baby Joy — 用一张照片，留下一段家庭的快乐

> 微信小程序 + 统一 API + 服务器异步生产：上传婴儿照片、选择祝福语、生成带童趣语音与表情的短视频。

**当前状态：设计阶段（2026-11-19）；未实现、未部署、未完成模型实测或法律审核。**

## MVP 边界

- **终端**：仅微信小程序（原生小程序 TypeScript，非 Web/H5 双端）。
- **生产链路**：小程序只调用 HTTPS API；后端负责授权、存储、TTS、GPU 视频生成、质量检测、FFmpeg 合成与私密交付；禁止把模型密钥或 GPU 推理放进小程序。
- **主要用户**：上传并授权的父母/法定监护人；爷爷奶奶是作品的主要接收者（MVP 不赋予非监护人上传并生成权限）。
- **首批场景**：亲情祝福、生日、节日；单张照片、单人、中文模板化文案、6–12 秒竖屏 MP4。
- **隐私默认值**：不公开、不用于模型训练；儿童肖像必须取得相应监护人授权；可主动删除；输出包含 AI 生成标识。
- **策略**：Phase 0 先验证“仍像宝宝 + 口型自然”，再建设面向真实用户的闭环；默认内部测试不等于公开上线。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [00 决策摘要](docs/00_EXECUTIVE_PLAN.md) | 关键决策、阶段门禁、成本和风险 |
| [01 产品 PRD](docs/01_PRODUCT_PRD.md) | 角色、旅程、范围、指标、验收 |
| [02 小程序 UX](docs/02_MINIPROGRAM_UX.md) | 页面、交互、弱网、分享和无障碍 |
| [03 系统架构](docs/03_SYSTEM_ARCHITECTURE.md) | 服务、信任边界、部署拓扑、关键时序 |
| [04 API 契约](docs/04_API_CONTRACT.md) | 微信登录、授权、上传、创建任务和下载 |
| [05 数据模型](docs/05_DATABASE_SCHEMA.md) | 表、约束、幂等与迁移 |
| [06 工作流](docs/06_JOB_ORCHESTRATION.md) | 状态机、事务 Outbox、恢复与故障处理 |
| [07 媒体管线](docs/07_MEDIA_PIPELINE.md) | 图片、TTS、GPU、QC、后期和输出 |
| [08 模型评测](docs/08_MODEL_EVALUATION.md) | Baby benchmark、评估指标、实验决策 |
| [09 安全合规](docs/09_SECURITY_PRIVACY_COMPLIANCE.md) | 监护人授权、儿童信息、威胁模型与删除 |
| [10 部署运维](docs/10_DEPLOYMENT_OPERATIONS.md) | Compose、GPU、日志指标、备份和容量 |
| [11 分阶段计划](docs/11_PHASED_IMPLEMENTATION_PLAN.md) | Phase 0–4、迭代任务和 DoD |
| [12 测试策略](docs/12_TEST_STRATEGY.md) | 合约/单测/集成/弱网/真机/验收 |
| [13 开源依赖](docs/13_OSS_LICENSE_RESEARCH.md) | GitHub 模型候选和许可证核验 |
| [14 ADR 与风险](docs/14_ADR_RISK_REGISTER.md) | 架构决策和风险闭环 |
| [Agent 交接](docs/AGENT_HANDOFF.md) | Codex/Pi 工作约定 |
| [Gotchas](docs/gotchas.md) | 已知问题与证据 |
| [OpenAPI 草案](specs/openapi.yaml) | 设计契约；尚未通过部署验证 |
| [SQL 初始草案](specs/001_initial.sql) | 数据模型原型；上线前需迁移审核 |

## 实施约定

按照 [Phase 计划](docs/11_PHASED_IMPLEMENTATION_PLAN.md) 依次建 PR；每个 PR 提供运行命令、实测结果、失败记录和回滚路径。不得把文档中的目标指标写成已达到的结果。模型许可证、微信平台政策及适用法律须在上线前重新核查。
