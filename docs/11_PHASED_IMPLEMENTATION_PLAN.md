# 11｜Phased Spec & Execution Plan（可交给 Pi/Codex）

## 实施纪律
独立分支、单一主题 PR、小步提交、先复现/建立失败测试再修复。每阶段需保存证据：运行命令、环境/模型版本、测试结果、截图或脱敏日志、失败案例、已知风险与回滚方案。**NOT RUN 不得称 PASS**；没有完整的授权与适用许可，不能用真实儿童素材进行训练或公开 Demo。

## Phase 0 — 真实模型可行性（先做）
1. 审核 EchoMimicV3-Flash / InfiniteTalk / Wan2.2-S2V / CosyVoice 的代码、权重、底座模型及依赖许可证；归档 revision、hash 和允许的商用场景。
2. 建立带授权的 baby benchmark，准备不进入 Git 的素材、TTS 文件、模型输入 manifest；可先用可再分发的合成/授权图调通脚本，但正式评测必须基于真正获得监护人授权的婴儿照片。
3. 在真实 GPU 运行相同输入，记录显存峰值、冷/热延迟、失败率、口型/相似度盲评结果。
4. 做初步 Baby-Aware 低动作参数对照，形成 `benchmarks/reports/<date>.md`。
5. Gate：许可证可用、相似度与成功率达到实验可接受范围，否则暂停下游实装。

**PR-0**：model-adapters 接口、benchmark CLI/报告、模型许可锁定和可重现实验说明；不应包含任何私有权重/儿童媒体。

## Phase 1 — 可运行后端（mock 推理先验收）
1. 初始化 `services/api` FastAPI + settings + 健康检查；Postgres Alembic migrations；Redis/Celery；Object storage 接口。
2. 身份：wx.login code2Session 通过可替换的 WeChatClient（单测 Mock）取得 openid；签内部短期 token；consent/policy 表；每项 GET/DELETE 强制 user scope。
3. 图片上传：分段/流式限制、安全解码、私有上传、READY/REJECTED；无外部 image_url。
4. POST /jobs 幂等、配额、事务 Outbox、job state/attempt、任务轮询、取消、删除。
5. 使用明确 mock fixture 的模型适配器串通：TTS→生成→QC→FFmpeg→download；P0 真模型通过后再切换。
6. 写 OpenAPI 和单元/集成/故障注入测试，CI 运行不需要 GPU。

**PR-1**：api + migrations + auth/consent + upload；**PR-2**：任务状态机、outbox、worker、对象生命周期；**PR-3**：mock pipeline + e2e + 监控。

## Phase 2 — 微信原生小程序闭环
1. 初始化 `apps/miniprogram` TypeScript 工程，页面路由和开发/体验环境配置；不包含生产 AppSecret。
2. 完成隐私引导与登录、图片选择/上传、祝福模板和音色、创建任务、任务列表和轮询、视频预览/下载/保存、删除入口。
3. 完整状态：等待、上传中、照片不合格、排队、处理中、超时、失败可重试、完成、已删除；保持重入恢复。
4. 真机 iOS/Android 网络切换、相册权限、合法域名、系统存储不足和小程序退后台恢复。
5. Gate：端到端真实设备验收录像与脱敏日志，未满足不上体验版对外开放。

**PR-4**：小程序页面 + API client 合约测试；**PR-5**：真机硬化与体验版运维文档。

## Phase 3 — 真实 GPU + 质量门禁
1. 根据 Phase 0 最佳模型建立独立 Docker gpu-worker（模型热加载、版本固定、无公网入口）；TTS 适配器；GPU 并发槽。
2. 将真实模型接到统一 pipeline；结果逐项完成 ffprobe/QC；严格限制最大等待时间和 GPU 重试预算。
3. 依实际失败模式做模型回退、低动作 Baby-Aware motion profiles；建立每次生成失败原因分布。
4. 进行分层婴儿家长盲评，审查伦理/许可/合规；满足质量和成本门槛才考虑商用。

**PR-6**：真实 worker + 运行配置和推理测量；**PR-7**：QC + 评测报告 + 质量阈值。

## Phase 4 — 合规运营与有限上线
1. 隐私告知/儿童信息处理规则/监护人同意的法律审核；AI 合成显式/隐式标识；举报/客服/删除 SLA；小程序审核及部署地区应履行的资质/备案确认。
2. 红队越权/上传安全/提示词和长文本/数据保留/对象 ACL/退款等（支付上线时）审核。
3. 生产监控、备份恢复、容量、资源上限、回滚、运维 Runbook；按照有限白名单/邀请码分批用户上线。
4. 基于真实用户反馈决定是否做支付、私密分享和更多场景，避免过度投入。

## 首轮里程碑与 Done 标准
- M0 许可证+授权数据+真实 GPU 基线（否则 NO-GO）
- M1 后端 mock E2E 真实运行（登录/权限/上传/生产/取消/删除/恢复/故障注入）
- M2 小程序双平台真机 E2E（上传、后台恢复、相册保存、隐私授权）
- M3 真实 GPU 验收与盲评（含失败样本统计）
- M4 法律/微信/安全及运维放行

## Agent 提交格式
每 PR 必须附：`Scope | Base SHA | Changed files | Tests(command/result) | NOT RUN | Metrics | Security/Privacy impact | Gotchas updated | Rollback | Open risks`。
禁止未经用户要求直接合并主分支；不得修改历史 migration；不得为过 CI 删除失败测试。参见 [AGENT_HANDOFF.md](AGENT_HANDOFF.md)。
