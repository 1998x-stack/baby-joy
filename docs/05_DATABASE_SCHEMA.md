# 05｜PostgreSQL 数据模型与迁移方案

## 1. 原则
业务主键 UUID（不暴露微信 openid）；所有用户拥有的资源通过 user_id 约束；大文件只存私有对象存储，DB 存 opaque key/哈希/元数据；删除记录必须能驱动物理清理；采用 UTC timestamptz。严禁用全局照片内容哈希连接不同家庭身份。

## 2. 核心实体
| 表 | 核心字段 | 关键约束 |
|---|---|---|
| users | id、wechat_openid_hash/enc、created_at、status | openid 以加密/带密钥索引方式保存且唯一；不作为 URL |
| policies | policy_version、scope、content_digest、published_at | 不变的版本化法律文本 |
| consents | id、user_id、policy_version、scope、guardian_declaration、granted_at、revoked_at、evidence | 与实际政策版本绑定，撤销不抹除必须保留的审计痕迹 |
| assets | id、user_id、kind、bucket_key、mime、bytes、sha256、status、expires_at | 状态与归属索引；bucket_key 唯一；存储加密 |
| jobs | id、user_id、input_asset_id、template/vars、voice_style、duration、status、stage、attempt_count、created_at、updated_at、finished_at | CHECK 允许状态；user_id+created_at 索引；删除中的输入不得创建任务 |
| job_attempts | id、job_id、attempt_no、model_id/revision、seed、lease_token、heartbeat、error_code、gpu_ms、peak_vram | UNIQUE(job_id, attempt_no)、防并发 fencing |
| job_events | id、job_id、stage、status、at、metadata | 不含儿童图像或下载 URL |
| outputs | id、job_id、asset_id、media_metadata、ai_label_version | job_id 唯一，生成完成后才能下载 |
| idempotency_keys | user_id、endpoint、key、request_hash、response_reference、expires_at | UNIQUE(user_id,endpoint,key) |
| outbox_events | id、aggregate_id、event_type、payload、published_at、attempts | 与 job 在同一 DB 事务提交 |
| deletion_requests | id、user_id、target_id、state、requested_at、completed_at、error | 物理对象清理可追踪 |
| usage_quotas | user_id、window_start、used、reserved | 原子预留/释放，避免重复扣费 |
| audit_events | id、actor_id、action、object_type、object_id、occurred_at、minimal_meta | 权限隔离、期限受控，不存图像 |

## 3. 关键事务
创建任务使用一笔事务：读素材行并锁定 → 验证 READY、归属和 consent 当前有效 → 预留配额 → 校验幂等键 → INSERT jobs → INSERT outbox。若幂等键重复，同请求返回已有 job，绝不再次扣配额。Dispatcher 的重复发布不能产生双重推理 attempt。

领取任务时 worker 在事务中用 `SELECT ... FOR UPDATE SKIP LOCKED` 或原子 compare-and-swap 设置 lease_token；更新阶段必须验证 attempt_id+lease_token，防止上一 worker 超时后回写覆盖新的成功结果。

## 4. 数据生命周期
上传隔离区超时清理；原照片默认最长 7 天（或用户提前删），TTS/未完成中间件默认 24h，成片默认 30 天（均为**建议配置值，需与隐私告知一致**），失效后状态改 EXPIRED 并执行删除。审计类保留期按最小化与法律义务另行确定，不得用单一“全库永久保存”。
对象存储版本化、备份、CDN 和 Worker 本地 cache 都属于删除边界，须有可执行的清理/到期策略；备份无法即时精确删除的场景需明确隔离、恢复后的清理流程与保留期限。

## 5. 数据库演进
迁移规范：`0001_initial` 开始，不改已执行 migration；非破坏性 expand -> 服务部署 -> 数据回填 -> contract；测试必须覆盖新建数据库、旧版本升级、失败回滚。当前 [SQL 草案](../specs/001_initial.sql) 仅用于建模审核，尚未在真实 PostgreSQL 执行，不可作为“上线迁移已完成”的证据。

## 6. 隐私设计
openid 使用服务端加密/受限访问，必要索引用 HMAC 带密钥计算，不能简单 SHA256 视为匿名化；日志、外部监控和分析事件不记录昵称、原图、内容全文、会话密钥或签名下载 URL。员工访问真实儿童素材必须独立审批和留痕。
