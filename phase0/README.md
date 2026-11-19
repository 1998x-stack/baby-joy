# Phase 0 — 可运行的本地模型评测框架

**状态：评测工具已实现；真实 GPU 推理、真实婴儿相似度、许可证正式审核仍为 NOT RUN / PENDING。**

## 目的与范围

只对获得监护人明确授权的儿童图片进行隔离环境评测。对比 EchoMimicV3-Flash、InfiniteTalk、Wan2.2-S2V；测量真实音视频时长、运行耗时与生成错误；通过匿名盲评录入身份保真度、动作、口型、连续性和情感。**真实照片、原始音频和模型输出不提交 Git，不进入公众可访问的 CI。**

这不是 API 生产 worker，不会下载模型或提供网络服务。依赖官方模型仓库、正式 checkpoint、GPU 环境和 `ffprobe` 由 Linux 操作员准备。

## 1. 必须具备的先决条件

1. NVIDIA GPU + `nvidia-smi`，CUDA 与 PyTorch 和各上游官方依赖兼容。
2. `ffprobe`，独立运行的 Linux 本地模型环境；EchoMimicV3 使用官方 `infer_flash.py`；InfiniteTalk 使用官方 `generate_infinitetalk.py`；Wan2.2 使用 `generate.py --task s2v-14B`。各模型复杂依赖最好独立虚拟环境；运行 CLI 的 Python 应当处于目标模型的独立环境。
3. 权重与底座模型均按供应方下载、核验签名/哈希和许可证。不要把任何未经审核的权重或不明声库投入商用。
4. **监护人授权的评测输入**：输入 JSONL 在受限目录，例如 `/srv/babyjoy-private/cases.jsonl`；授权记录保留在独立安全系统，不能仅凭单个 JSON 字段证明合法授权。
5. 每模型本地 config（从 `config/*.example.json` 拷贝并修改）以及经过审查人员签名流程生成的非 PENDING approval JSON。测试用例示例中的 `RESEARCH_APPROVED` 只是单测模拟，不代表实际许可批准。
6. 目前仅 checkpoint 列表中的文件会进行 sha256 比对；**正式研究前需完整覆盖底座、audio encoder、tokenizer 和 LoRA 等权重链**，否则只能认为“部分文件校验”。

## 2. 私密案例清单示例（不要提交）

```json
{"case_id":"anon001","image":"assets/photo01.jpg","audio":"audio/blessing01.wav","seed":43,"consent_reference":"internal-consent-id","consent_scope":"BENCHMARK_RESEARCH","consent_active":true}
```

字段 image/audio 是**相对于 private-root 的路径**，符号链接越界会被拒绝。音频为 0.4–12 秒 PCM WAV（当前工具不会自行 TTS）；case_id 是无身份含义的代号。使用者必须在每次实际运行前确认授权尚未撤回，且用途涵盖对应评测。MVP 最终文案 6/8/12 秒属于交付目标，Phase 0 可以先用更短音频测模型基础可用性，但不得用 3 秒结果宣称 8 秒成功。

## 3. CLI 示例

所有命令从仓库根目录执行；Python 标准库即可运行工具与单测，模型推理还需要各模型独立的大型依赖。

```bash
PYTHONPATH=phase0 python -m babyjoy_phase0.cli validate \
  --private-root /srv/babyjoy-private \
  --cases /srv/babyjoy-private/cases.jsonl

# 许可证、权重哈希和 NVIDIA GPU 的硬闸门。没有审核/权重时 exit 2。
PYTHONPATH=phase0 python -m babyjoy_phase0.cli preflight \
  --model echomimic_v3_flash \
  --config /srv/babyjoy-private/config/echo.json

# 真 GPU 推理，数据与日志只落地到 private-root/runs。
PYTHONPATH=phase0 python -m babyjoy_phase0.cli run \
  --private-root /srv/babyjoy-private \
  --cases /srv/babyjoy-private/cases.jsonl \
  --case-id anon001 \
  --model echomimic_v3_flash \
  --config /srv/babyjoy-private/config/echo.json \
  --output-root /srv/babyjoy-private/runs

PYTHONPATH=phase0 python -m babyjoy_phase0.cli report \
  --output-root /srv/babyjoy-private/runs

PYTHONPATH=phase0 python -m babyjoy_phase0.cli ratings \
  --ratings-file /srv/babyjoy-private/ratings.jsonl

PYTHONPATH=phase0 python -m unittest discover -s phase0/tests -v
```

### 重要：真实推理产物判定
- `status=COMPLETED` 仅表示官方脚本成功产出并通过 ffprobe + 音轨存在与时长误差≤0.30s 的**技术门禁**，不等于儿童脸部保真通过、许可证商用通过或产品上线通过。
- 失败输出及详细日志放在私有 run 目录，面向公众报告只显示聚合统计。
- 官方 EchoMimicV3-Flash `run_flash.sh` 用 81 帧，约 3.24 秒；工具按 WAV 时长计算 `--video_length`，且对结果做实际验收。较长视频可能 GPU OOM、发生漂移，仍须真实试验，不应将“传入长参数”视为已支持长视频。
- InfiniteTalk 输出名和 clip 模式依赖上游实际版本，应固定 commit 并在 GPU 环境验收；更新上游可能导致 adapter 变更。
- Wan2.2-S2V 官方示例为 14B 级，需要资源预算；未经真实 GPU 测试不承诺单卡 80GB 以外其他运行条件。

## 4. 盲评 JSONL（同样只能本地私存）

```json
{"case_id":"anon001","model_id":"echomimic_v3_flash","reviewer_id":"guardian01","identity":5,"motion":4,"lip_sync":4,"continuity":4,"emotion":5,"severe_artifact":false}
```

每项 1–5 分，严重畸变硬否决。**评分不是生成成功的替代**，需要关联 run receipts 并确保评价覆盖失败样本、分层和无答复样本。工具将不足 30 个唯一 case 标为 `INSUFFICIENT_EVIDENCE`；同一个 case 多人评价并非独立样本，Wilson 区间仅描述评分行，不等价家庭层面统计区间。后续研究阶段应采用家庭为单位的聚类估计。

## 5. 当前实测边界
| 项目 | 状态 |
|---|---|
| CPU 框架、WAV / consent / 路径检查、命令构造、统计与测试 | 代码已提交，CI 结果以 Actions 为准 |
| 三个官方 CLI 的**参数拼接** | 已实现，实际模型环境待验收 |
| 真实模型 weights、底座许可证、商用授权 | PENDING |
| 婴儿授权图片数据集和家长盲评 | NOT RUN |
| NVIDIA 显存/推理速度/视频质量 | NOT RUN |
| 微信小程序/API | 尚未开始 Phase 1/2 |

## 6. 安全底线
本项目拒绝自动下载、不允许将任意远端 URL 作为儿童图像输入、不在 CLI stdout 打印图像路径/昵称、不会把案例文件送入 GitHub CI。GPU 运行前人工复核每条儿童素材授权，并检查本地目录权限、操作员和第三方进程边界。每个模型依赖许可审查单独保存，不许因为 GitHub repo 标为 Apache 就自称权重已批准。

后续可新增 `nvml` 连续采样、GPU 利用率/显存峰值和 TTS 统一基线；当前只保存 `nvidia-smi` 的设备元数据和端到端 wall time，**没有推理显存峰值指标**。
