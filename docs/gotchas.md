# Gotchas / Known Issues & Evidence

> 当前为设计阶段。这里记录已经观察到的事实、待验证条件和后续实测发现；不要把“未运行”填成“通过”。

| ID | 状态 | 观察 / 风险 | 证据 | 后续动作 |
|---|---|---|---|---|
| G-000 | CONFIRMED | baby-joy 初始化时仓库为空 | GitHub API `contents` 返回 This repository is empty，2026-11-19 | 初始化 README，文档独立 PR |
| G-001 | NOT RUN | 真实 GPU 推理未验证 | 尚无服务器/权重/日志 | Phase 0 实测 3 个模型的真实婴儿短句 |
| G-002 | NOT RUN | 微信小程序 iOS/Android 真机登录和上传未验证 | 尚无小程序 AppID、体验版和合法域名 | Phase 2 真机 E2E |
| G-003 | NOT RUN | SQL 草案及 OpenAPI 尚未接入真实项目 | 仅文档原型 | 创建 Alembic schema 并做数据库和合约验证 |
| G-004 | PENDING REVIEW | 各模型权重/底座/音色商业许可证未完成端到端核查 | GitHub repo license 只证明仓库标签 | 填入 model-approval 审查表 |
| G-005 | PENDING REVIEW | 儿童数据处理、AI 标识和可能的备案/平台审核适用性需主体判断 | 合规来源见 docs/09 | 上线前法律和平台审核 |

## 新 Gotcha 模板

```markdown
### G-XXX <title>
- Date / Environment / Commit:
- Status: CONFIRMED / PENDING / FIXED / NOT RUN
- Reproduction:
- Expected / Actual:
- Evidence (redacted logs or test artifact):
- Root cause:
- Remediation:
- Regression test:
- Related PR / ADR:
```

| G-006 | CONFIRMED | EchoMimicV3-Flash 官方 run_flash.sh 默认 81 帧 @25fps；infer_flash.py 按 video_length 截断输入语音 | 2026-11-19 核查上游 run_flash.sh 和 infer_flash.py | Phase0 按 WAV 帧长调整 video_length，ffprobe 校验；真实 6/8/12 秒 GPU 仍 NOT RUN |
| G-007 | NOT RUN | 三个视频模型的真实 checkpoint、输出文件名与可用 GPU 尚未端到端检查 | Phase0 CLI 和单测仅提供参数合同 | 按 docs/15 和 phase0/README 在合法私有环境实测 |
| G-008 | PENDING REVIEW | 研究运行审批 JSON 当前仅为人工声明，不能替代正式版权/未成年人数据审查 | G0 尚无由实际权利人/审核人签发的批准材料 | 人工复核原始许可、权重链、儿童照片授权后运行 |
