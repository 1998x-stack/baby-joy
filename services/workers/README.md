# GPU/CPU Workers（计划）

**尚未实现代码。** CPU worker 负责图像预处理、QC、FFmpeg 和数据清理；GPU worker 负责受控的 TTS 与视频模型适配器。所有文件从私有对象存储获取，结果有 per-job/attempt 隔离与 lease fencing。
详见 [管线](../../docs/07_MEDIA_PIPELINE.md)、[状态机](../../docs/06_JOB_ORCHESTRATION.md)、[Benchmark](../../docs/08_MODEL_EVALUATION.md)。