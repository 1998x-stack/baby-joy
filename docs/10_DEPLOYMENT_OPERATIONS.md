# 10｜部署、容量、运维与成本控制

## 1. 环境分级
- **dev/mock**：不需要 GPU，使用假模型适配器输出**明确标注为 fixture** 的测试视频，只验证任务协议/业务流程；禁止发布成真 AI 演示。
- **benchmark**：带真实 GPU/权重，单独网络隔离、测试用户合法授权、模型和资源全记录。
- **staging**：微信小程序体验版 / API 域名、私有存储、完整异步链路、少量真实授权照片。
- **production**：备案和监管/许可/审核门禁通过后才能开放。

## 2. 推荐最小拓扑
```text
公网： HTTPS api.<domain> -> Nginx -> FastAPI
内网： Postgres, Redis, Outbox dispatcher, CPU worker, MinIO/S3
GPU：  gpu-worker(模型权重只读挂载) -> 内网对象存储
观测： Prometheus/OTel（无儿童图片/语音/正文日志）
```
单 GPU 服务器是可以接受的 Alpha 起点，但数据库和模型容器需资源隔离，避免 GPU OOM 拉垮 API。建议 CPU 容器预留不少于 4 vCPU/8GiB 的规划空间（非实测配置）；GPU 必须先用 Phase 0 验证峰值显存，不能把某个项目声明的 12GB 等同于生产充足容量。

## 3. Docker Compose 的服务清单
`nginx`、`api`、`postgres`、`redis`、`outbox-dispatcher`、`image-worker`、`gpu-worker`、`render-worker`、`minio`（仅自托管 Alpha）、`metrics`。每个服务定义 healthcheck、资源上限、readiness、restart policy、时区 UTC，容器以非 root 运行，配置从环境/密钥管理注入，严禁把 appsecret 进 .env.example 的真实值或 Git。

建议`docker compose --profile gpu up -d` 作为未来目标命令，**目前没有 Compose 文件和真实服务，不能声称已经可运行**。实现前确定 NVIDIA Container Toolkit、驱动/CUDA 兼容矩阵，开发/测试/生产锁定版本。

## 4. 小程序平台接入
- 合法 request/upload/download 域名提前登记；有合格 HTTPS 证书，确认备案和目标小程序主体类目。
- 小程序调用自己 API，不直接调用微信 code2Session（后者只在服务端）。
- wx.uploadFile 时如果目标域名指向统一后端，需要网关正确设置 body 大小/超时；MVP 图片 8MiB。
- 下载 URL 使用可登记域名（或 API 代理下载）；不要依赖无法配置到小程序 download 域名白名单的随意云存储域名。
- 真机测试相册授权、弱网、安卓/iOS H.264 解码、下载与系统存储不足。
- 微信审核、ICP备案、隐私弹窗要求会变化，发布前以实际官方控制台为准。

## 5. 观测与告警
**Metrics**：API 错误率/P95；job 阶段时长分布；队列深度与最旧任务年龄；GPU 显存/利用率/OOM；TTS/视频模型每版本成功率；QC 拒收率；下载失败；删除积压和超过期限未删对象；成本/合格片。
**Tracing**：request_id、job_id、attempt_id 相关联；不将任何含儿童原图/声纹的对象、昵称或签名 URL 写入 span attributes。
**Alerts**：队列 >上限、模型 OOM 激增、任务 stale lease、持续 5xx、删除任务超时、私有桶 ACL 变更、异常下载激增。
**Runbook**：冻结新任务入队、停 GPU worker、重放 Outbox、仅重试安全可重试任务、处理对象泄露和权限事件、检查数据到期清理。

## 6. 容量与成本
```text
GPU 成本/合格片 = (所有 attempts 的 GPU 秒 * 实际 GPU 每秒成本 + TTS+渲染+存储+流量) / 合格成片数
理论吞吐 ≈ GPU 卡数 * 3600 / 平均每条成功所需 GPU 秒
实际吞吐需扣除模型加载、失败重试、队列不均匀、显存碎片和维护。
```
示例**只作算式不是报价**：若某配置实测每条含重试平均 120 GPU 秒且单卡每小时成本 ¥12，则纯 GPU 推理约 ¥0.40/合格片，其他成本另加；未实测前不能将此假设用于定价。按 P50/P95、不同输入分层计算，而不是单条精选例子。

## 7. 数据与灾备
Postgres 定时备份并测试恢复；对象桶按加密/生命周期策略；Redis broker 可丢任务但 Outbox 可恢复；API 及任务 DB 备份与对象版本一致性检验；按期限执行删除和恢复后的 deletion replay。明确 RPO/RTO 业务目标后再选存储备份架构。部署变更需保持可回滚的镜像 tag、模型版本和 DB schema；生产 DB 不在无人审核时执行 destructive migration。
