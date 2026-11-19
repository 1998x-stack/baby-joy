# 12｜验证与测试策略

## 1. 测试金字塔
- Static：Python lint/type、TS type、OpenAPI schema lint、SQL migration review、secret scan、依赖漏洞和许可证清单。
- Unit：输入验证、文本变量、时长校验、token 签发、授权版本、用户归属、状态转换、配额和幂等。
- Contract：小程序客户端 ↔ API schema；worker adapter 输入输出；状态码；错误体；响应字段向后兼容。
- Integration：真实 Postgres/Redis/MinIO Testcontainers 或 Compose，mock GPU，端到端从文件上传到可下载 MP4。
- Fault injection：重复投递、断连、慢上传、GPU OOM mock、worker kill、删除竞态、签名过期、对象 GC。
- System：真实 GPU（资源可用时）、微信体验版双平台真机、私有下载和删除。

## 2. P0 安全用例
| Case | 断言 |
|---|---|
| AUTH-01 | 假 code/过期 code 被拒绝；openid/session_key 不到客户端/日志 |
| AUTH-02 | A 用户请求 B 的 asset/job/download/delete → 404/403、无泄露 |
| CONSENT-01 | 未完成当前政策版本及监护人确认不能上传/创建 |
| CONSENT-02 | 撤回后不可新建任务，进行中的任务按规则终止/清理 |
| UPLOAD-01 | 8MiB+、错误 MIME、图像炸弹、恶意 EXIF、零字节拒绝 |
| UPLOAD-02 | 多脸/严重模糊提供可理解原因，上传对象不遗留 |
| IDEMP-01 | 相同 key+body 多次提交同一 job，不多扣配额 |
| IDEMP-02 | 同 key 不同 body 返回 409，不发生额外生产 |
| WORKER-01 | 重复消费/旧租约晚到不得提交两次结果 |
| WORKER-02 | Kill -9 GPU/CPU Worker 后经调度恢复，达到终态 |
| DELETE-01 | COMPLETED/GENERATING 期间删除：不可再下载，所有临时对象回收 |
| DOWNLOAD-01 | 过期签名、不属于本人、未完成任务均不可下载 |
| OUTPUT-01 | 最终视频有可解码音视频、时长匹配、AI 标识 |
| PLATFORM-01 | 小程序弱网/重登/退后台，job_id 保持可恢复 |
| PLATFORM-02 | iOS/Android 下载保存授权拒绝时无死循环 |

## 3. 真 GPU 测试
记录每次案例真实命令、模型 checkpoint/权重 hash、CUDA/驱动、GPU 显存、推理时间、输出时长、质量结果。必须包括：5-12s 句长、不同姿态/光线、同脸多次种子、典型低画质、GPU 显存临界和临时写盘失败。报告成功率分母包括失败生成，不允许只采成功样本。

## 4. 契约不变量
`COMPLETED` 必须有可读 output、通过 QC 和授权状态；`DELETE` 接收后不可继续获得下载能力；任何从 API 返回的素材信息不应包含裸对象存储凭证；`Idempotency-Key` 在一个租户内唯一而非全局跨家庭关联。Worker 只接受 trusted queue 任务，永不执行客户端传来的 shell 命令。

## 5. 指标和出具证据
在 PR 里列出环境、工具版本、输入 fixture 来源、实际执行命令及 PASS/FAIL/NOT RUN。CI 没有 GPU 时标明 REAL_GPU_E2E=NOT_RUN，不能以 mock E2E 冒充。微信真机和正式域名验收必须独立报告；遵循合法测试儿童图片的最小化保留策略。

## 6. 性能负载
按用户并发创建/队列吞吐两条线测压：API 20/50/100 并发请求，合法用户/上传大小分层；GPU 每时段可承载真实 job 数由 Phase 0 推算，不假定水平扩容即可稳定。监测 DB 锁冲突、Redis 队列积压、签名下载流量、对象 GC 延迟、GPU OOM 和重试放大。
