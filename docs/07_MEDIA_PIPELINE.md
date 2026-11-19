# 07｜照片 → TTS → 视频 → 后期 的媒体生产管线

## 1. 候选与最短路线
主候选：**EchoMimicV3-Flash**（音频驱动，模型体积相对轻；官方配置称可在特定环境运行于 12GB VRAM）；对照 **InfiniteTalk** 和 **Wan2.2-S2V**。第二路线：LivePortrait + MuseTalk/LatentSync，用于控制/诊断。先把模型放入统一 adapter，不先训练新模型。

```python
# 应用层协议草案；非模型原生接口
@dataclass
class VideoRequest:
    source_image_path: str
    speech_wav_path: str
    target_fps: int
    model_profile_id: str
    seed: int
    motion_strength: float

class VideoAdapter(Protocol):
    def generate(self, request: VideoRequest, output_dir: str) -> GenerationMetadata: ...
```
每个模型 adapter 管理自己运行环境、权重 checksum、音频采样率、帧率、分辨率、显存限制和 timeout。版本化 model_profile 指向不可变权重与参数，允许对照和回滚。

## 2. 图片输入
1. 限制文件大小和解码像素数，检测 mime magic，不信扩展名、客户端 EXIF；对解码炸弹、畸形图、文件注入设置沙箱。
2. 去除 EXIF/GPS；有色彩空间则统一 sRGB，转换为内部 PNG；遵循尽量不改变脸部几何的原则。
3. 检测人脸和质量。MediaPipe Face Landmarker 用于定位参考，但婴儿样本可能误检，应允许人工审核而不是“人脸识别失败即不可使用”的唯一规则。
4. 生成可追踪的 normalized image，保留变换参数：rotate、crop、resize、pad、color profile；不得把隐式美颜或换脸当作预处理。
5. 多脸、严重遮挡、侧面角度过大拒绝或引导重新选图；避免预测宝宝年龄、性别、健康状况等无关属性。

## 3. 文本与 TTS
- 输入使用 allowlist 模板 + 变量；Unicode NFKC、恶意内容/违禁表达审核、长度及标点规范化。
- 使用 CosyVoice 或经授权的童趣声音；第一版拒绝用户上传参考声纹和真人声纹克隆。语速/音色按模板控制，不将成人音高机械升调等同于婴儿真实发声。
- 产生 PCM/WAV、音频长度、采样率、声道数及 hash；TTS 失败和空音频明确拒绝。
- **按实际音频时长决定帧数**。如果固定目标时长无法容纳音频和停顿，返回 `DURATION_MISMATCH` / 让用户选择另一档，不可静默删除文本。
- TTS 可在用户确认前先合成预听音（未使用儿童生物特征）；如收费需区分预览成本与正式生成成本。

## 4. 视频生成
- 输入仍像原图是首要目标：配置较保守的头部转角、嘴部开合和上半身动作幅度。
- 为模型定义 `supported_fps`、`max_audio_seconds`、`reference_crop`；若模型只支持固定长度分块，应验证分块接缝，MVP 尽可能避免长片拼接。
- 模型输出序列不可信：检查帧数、fps、长宽、重复帧、损坏帧、音轨缺失，禁止“进程退出码 0”即判成功。
- 临时工作目录按 job/attempt 隔离，路径白名单；GPU 权重只读，推理容器禁止无必要的外网访问。
- 模型选择在服务端：不要允许小程序直接指定 `--model`、`--script`、`--path`、`--seed` 命令行参数。

## 5. Baby-Aware 质量与动作规则
研究模块（**不是现有已实现能力**）：`age_group` 仅由监护人主动选择（可不选），映射允许的 motion profile：新生儿/较小婴儿只允许微幅表情；更大宝宝可允许更明显摇头。禁止从照片推测敏感身体/健康属性。
- 质量先通过人工标注的基础样本集；后续融合特征稳定性、人脸关键点变化、运动光流、帧间色彩差和 lip-sync 相关指标。
- 特别监测：牙齿异常、眼睛瞬变、口腔纹理跳变、面部成人化、脸颊几何变化、衣服背景跳变、动作不符合年龄。
- 将 QC 失败保留匿名化错误代码和模型版本，不默认长期保存失败的视频或儿童原图。

## 6. 音画后期
FFmpeg 后期：裁剪/填充到固定 9:16、匹配实际音频、字幕、BGM 混合（只有已授权音乐素材）、AI 内容显式标识 + 适用的隐式 metadata、水印；最终采用 H.264/AAC/faststart MP4，输出封面/封装信息。成片必须 `ffprobe` 检查可读取音轨、视频轨、帧率、时长容差、音量峰值/静音异常；允许可配置较小时长容差（例如±0.25s，实验阶段目标，不是行业保证）。

## 7. 推理成本测量
记录 `GPU_model, GPU_memory_peak, inference_seconds, load_seconds, queue_seconds, audio_seconds, output_seconds, retries, model_revision`，分别统计冷/热启动、360p/720p，实测每成功片总成本，不把未经过模型验证的“12GB 需求”当作企业服务器的保证。质量不达标时不能通过降低比特率冒充成功。

## 8. 许可证闸门
许可证核查必须涵盖代码、权重、底座模型、TTS 声音资产、数据集、Face Detector（如 InsightFace 模型）和 BGM，不得只看 GitHub 仓库 LICENSE。见 [13_OSS_LICENSE_RESEARCH.md](13_OSS_LICENSE_RESEARCH.md)。
