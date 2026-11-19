# 15｜Phase 0 执行看板（证据驱动）

Date: 2026-11-19  
Branch: `feat/phase0-benchmark-harness-20261119`  
Base: `a209278e7a0c6d9c163b464f24b0cdf32506bf58`（PR #1 蓝图分支）  
注意：本 PR 依赖 PR #1。PR #1 合并后应将 Phase 0 PR 目标基线改为 main/刷新分支，不得重复提交设计文档。

## 本次交付

- [x] 本地 CLI：验证授权案例、模型审批与模型权重文件 SHA256、真实 NVIDIA GPU 入口；不能无审核默默推理。
- [x] 上游模型 adapter 命令构造：EchoMimicV3-Flash、InfiniteTalk、Wan2.2-S2V，禁止 shell 拼接。
- [x] 真实 WAV 时长换算 Echo 帧数；ffprobe 对最终音轨、视频轨、实际时长做硬检查。
- [x] 本地 run receipt、失败标识与报告摘要，详细日志留在私有目录。
- [x] 盲评结构、严重畸变硬否决、低样本标记；不将单纯推理完成视为宝宝质量通过。
- [x] CPU-only 自动化单测和 GitHub Actions（结果需读取真实 Actions；不能凭代码存在宣称通过）。

## 必须完成的真实实测

| Gate | 需要的证据 | 当前 |
|---|---|---|
| G0 许可证 | 完整权重/底座/依赖/音色审核记录，商用地域与 API 使用许可 | PENDING REVIEW |
| G0 资源 | 可用 NVIDIA GPU、driver、CUDA、独立 Conda 环境、ffprobe、完整权重 manifest | NOT RUN |
| G1 时长 | 6/8/12 秒中文 WAV 三模型生成视频，验证 0.30 秒时长容差 | NOT RUN |
| G1 视觉 | ≥30 有授权照片；婴儿身份相似度、嘴型、眨眼、严重缺陷、盲评 | NOT RUN |
| G1 成本 | 冷/热推理耗时、GPU 专属显存峰值（目前仅采样系统显存）、失败重试摊销 | NOT RUN |
| G1 决策 | 统一分母、分层、Gate 规则以及独立复核人签字 | BLOCKED |

## 与原 Phase 0 计划的差异
本次完成的是 **Phase 0 工具和可重复的评测入口**，不是 30–50 张真实婴儿素材的实验结果，也没有 GPU 资源信息。接入本地 Pi/Codex 执行时必须提交脱敏运行报告和真实模型版本，才能选定生产模型或开始收费开发。

## 已发现的技术风险
1. EchoMimicV3-Flash 官方示例使用 81 帧@25fps（≈3.24 秒），脚本根据 `min(audio_frames, video_length)` 裁音频；要测 6–12 秒必须提高 `video_length` 并验证是否超显存及是否漂移。
2. 三种上游模型环境各自依赖冲突，需使用隔离 venv/Conda 或容器；本工具执行的是**当前 CLI Python 环境**下的对应源码入口。
3. 收到官方代码/脚本版本更新可能破坏输出命名约定；必须 pin 上游 Git commit 并保持回归测试。
4. 商用许可证不能只用仓库 license；底座/音频 encoder/预训练权重/TTS 声库需分别审核。
5. G1 “仍像自己的宝宝”需要家长盲评，不能直接由成人脸部相似度模型做自动放行。

## 首轮工程 CI 证据
- `https://github.com/1998x-stack/baby-joy/actions/runs/44484110106`
- Python 3.11，21 个 CPU-only unittest：PASS；编译检查与空报告 NOT_RUN 约束：PASS。
- 之后新增上游 Git revision 和显存采样测试，**最新提交需重新检查 CI**。
