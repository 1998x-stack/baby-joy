# 13｜开源模型、组件和商业许可核查

> 2026-11-19 查阅官方 GitHub 仓库元数据与项目 README 的初步清单。**仓库 SPDX 标签不等于完整商业许可结论**；底座模型、checkpoint、TTS 音色、训练数据、依赖和使用地域需独立确认。未审查完之前将商业准入状态标为 PENDING。

## 1. 视频模型候选
| 项目 | 仓库 | 用途 | 当前核查 | 下一步 |
|---|---|---|---|---|
| EchoMimicV3 / Flash | https://github.com/antgroup/echomimic_v3 | 单图+音频说话、头部/身体驱动 | 仓库 Apache-2.0；官方 Flash 版本写明 12GB 特定配置、8步、768px | 固定权重 hash；核查底座/音频 encoder 许可；真实婴儿 benchmark |
| InfiniteTalk | https://github.com/MeiGen-AI/InfiniteTalk | 单图/视频 + 音频，可更长时间 | 仓库 Apache-2.0 | 权重、Wan 底座、长时身份漂移、显存和费用 |
| Wan2.2-S2V | https://github.com/Wan-Video/Wan2.2 | 高质量音频驱动视频 | 仓库 Apache-2.0；部分官方示例 80GB 显存 | 核查目标 checkpoint、硬件；与 Echo 质量/价格对照 |
| HunyuanVideo-Avatar | https://github.com/Tencent-Hunyuan/HunyuanVideo-Avatar | 动作/情绪基准 | 特定腾讯社区许可，非宽松开源许可 | 地域/公司规模/商用风险审查，不进默认 MVP |
| LivePortrait | https://github.com/KlingAIResearch/LivePortrait | 表情/姿态控制对照 | 项目代码公开；依赖 InsightFace 检测/权重可能受非商业限制 | 如商用，替换受限制检测权重或取得许可 |
| MuseTalk | https://github.com/TMElyralab/MuseTalk | 视频口型同步 | 需审各版本权重和依赖 | 作为后处理对照，不要默认叠加以免身份漂移 |
| LatentSync | https://github.com/bytedance/LatentSync | 扩散式口型修复 | 需审完整许可证与权重 | 测试口型改善是否抵消脸部失真 |

## 2. 语音与媒体基础
| 项目 | 用途 | 许可备注 |
|---|---|---|
| CosyVoice https://github.com/FunAudioLLM/CosyVoice （兼容历史仓库 QwenAudio/CosyVoice） | 中文 TTS 主候选 | GitHub 仓库为 Apache-2.0 标签；进一步核查当前音色资产及依赖 |
| IndexTTS https://github.com/index-tts/index-tts | 情感与语速对照 | 自定义模型许可，商用使用前需要审查 |
| F5-TTS https://github.com/SWivid/F5-TTS | TTS 研究基准 | 代码 MIT；官方预训练权重可能为 CC-BY-NC，不能因为代码 MIT 就直接商用 |
| MediaPipe https://github.com/google-ai-edge/mediapipe | 面部定位、图像质量特征 | 核查引入的具体模型文件/平台许可 |
| FFmpeg https://ffmpeg.org/legal.html | 编码/封装/混音 | LGPL/GPL、codec/build 组合不同；避免无意引入 GPL 组件或专利纠纷 |
| Pillow/OpenCV | 图像处理 | 核查具体 wheel/构建依赖 |
| Redis/PostgreSQL/FastAPI/Celery | 后台处理 | 核对版本和第三方依赖 |
| 字幕字体、背景音乐 | 成片资源 | 仅使用明确授权的商用素材，不自动复制网络内容 |

## 3. 逐模型商用检查表
- 代码：commit SHA、许可证及 NOTICE/署名要求。
- 模型：准确 checkpoint 文件 SHA256、模型卡/license、可否商用/托管 API/收费用户生成。
- 继承依赖：底座模型、Face detector、audio encoder、LoRA、TTS 声音、任何模型包中的第三方权重。
- 限制：地域、禁止用途、再分发、生成内容权利、保留/回传用户数据条款。
- 部署：GPU 型号、CUDA/driver 版本、显存峰值、单片耗时；只用真实测量填值。
- 数据：不把儿童肖像用于无授权训练；评测素材合法授权和存储删除规则。
- 结论：`REVIEWED_ALLOWED | REVIEWED_RESTRICTED | NOT_ALLOWED | PENDING` + 审查人/日期/依据链接。

## 4. 特别说明
1. EchoMimicV3-Flash 的“12GB”是官方对其指定推理配置的说明，不证明任何 12GB 卡都能以目标时长、720p 或高并发达到要求。
2. Wan2.2-S2V 的 80GB 见其官方示例配置；这不意味着所有优化路线必须 80GB。要按实际模型和脚本 benchmark。
3. 一些开源的人脸识别/口型算法在**成人**数据上训练，“指标分数高”不能替代“是否像这个宝宝”的家长评价。
4. 若审核发现任何主模型权重许可或声库许可无法满足商用，就切换到可用候选或暂不上线，不能通过单纯修改引用声明规避许可。

## 5. 第一阶段输出产物
`docs/licensing/model-approval.csv`（后续实现）：`component,repo,commit,weight_sha256,code_license,weight_license,dependency_review,commercial_api_allowed,territory,reviewer,date,decision,evidence_url`。
初版所有模型商用完整准入均为 **PENDING**，不得将此表当作审批通过。
