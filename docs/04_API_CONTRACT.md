# 04｜API Contract v1（设计稿）

**Base** `https://api.<registered-domain>/v1`（示例占位，不可用于实际部署）。统一 `application/json`；上传接口 `multipart/form-data`；用户端 `Authorization: Bearer <short-lived-token>`，服务端签名、不让微信 AppSecret 出现在客户端。所有返回携带 `request_id`（标头 `X-Request-ID`）。

## 1. 身份与授权
`POST /auth/wechat`
请求 `{"code":"wx.login一次性code"}`。后端调用微信 code2Session；建立/查找主体；只返回内部短期 access_token、expires_in、用户资料完成状态；openid/session_key 永远不返回客户端。微信 code 不写日志，失败不可重放。
`GET /me` 返回脱敏用户资料、当前授权状态与账户删除入口。
`GET /policies` 获取最新隐私说明、AI 标识说明、儿童数据处理专门规则版本与摘要。
`POST /consents` `{"policy_version":"2026-11-19.1","scope":"GUARDIAN_UPLOAD_AND_GENERATE","guardian_declaration":true,"purpose":"FAMILY_GREETING"}`；业务侧校验和保存版本、授权时间与最小证据（不是直接信任任意客户端用户是监护人）。未通过拒绝后续上传与生成。撤回授权时阻止新任务并触发合规删除/保留决策。

## 2. 素材
`POST /assets/images`（multipart：`image`）返回 `202`：
```json
{"asset_id":"ast_01...", "status":"PENDING_SCAN","request_id":"req_..."}
```
- Content-Length≤8MiB（压缩格式）；服务端检测 MIME magic bytes、最大解码像素数、EXIF、病毒/恶意结构、脸部数量及图片质量。素材写临时对象区，校验成功才转 READY。
- `GET /assets/{asset_id}` 返回 `status=READY|REJECTED|PENDING_SCAN` 和 `reason_code`，只允许所有者；无公共读取 URL。
- API 不接收任意远程 `image_url`：避免 SSRF。MVP 不支持微信分享图片的外部任意链接抓取。

## 3. 创建生产任务
`POST /jobs`，必填头 `Idempotency-Key: <UUIDv4>`（建议 24h+ 存储，实际需覆盖离线重试期）：
```json
{
  "asset_id": "ast_01...",
  "template_id": "family_love_v1",
  "template_vars": {"baby_name":"丫丫", "recipient":"爸爸妈妈和爷爷奶奶"},
  "voice_style": "warm_childlike",
  "target_duration_seconds": 8
}
```
返回 `202 Accepted`：
```json
{
  "job_id": "job_01...",
  "status": "QUEUED",
  "stage": "QUEUED",
  "poll_after_seconds": 3,
  "request_id": "req_..."
}
```
- 服务端验证 asset_id 归属、本次用途的监护人授权、模板/变量长度、音色 allowlist、6/8/12 秒集合、配额/冷却期。不能信任客户端提供的任意 prompt、model_id、云桶路径、GPU 参数。
- 同 key 同 canonicalized body → 返回原始 job；同 key 不同 body → `409 IDEMPOTENCY_CONFLICT`。
- `POST /jobs/{id}/retry`：仅服务器允许的失败类型，生成**新 job** 或 attempt，返回关联 ID；必须声明配额处理；同样要求幂等键。
- `POST /jobs/{id}/cancel`：返回请求已接收，不承诺 GPU 正在执行的阶段立即中止。
- `GET /jobs?cursor=&limit=20`：只列本人任务，按时间倒序；限制分页。

## 4. 查询与交付
`GET /jobs/{job_id}`：
```json
{
  "job_id":"job_01...",
  "status":"GENERATING",
  "stage":"GENERATING",
  "stage_started_at":"2026-11-19T07:00:00Z",
  "poll_after_seconds":5,
  "error":null,
  "output":null
}
```
成功时 `status=COMPLETED` 且 `output={ "video_id":"vid_...", "duration_seconds":7.9, "width":720, "height":1280, "ai_generated":true }`。
失败时 `error={"code":"MODEL_OOM","message":"暂时无法生成，请稍后重试","retryable":true}`；错误 message 不泄露路径或儿童信息。
`GET /jobs/{id}/download` 仅完成态和所属用户可调用，按每次请求生成短期签名下载 URL（建议 300 秒）及 expires_at。签名不得持久化到数据库或出现在可公开日志中；如对象存储/CDN 不能保证权限与缓存隔离，改为后端鉴权代理下载。
`DELETE /jobs/{id}` 异步创建删除请求，返回 `202` 与删除跟踪 ID；取消生成并对原图/音频/中间视频/成片逐层清理，不能只删除数据库行。
`GET /deletions/{id}` 查询删除完成状态。
`POST /feedback` 只接收 job_id、枚举标签、简短文字，不自动传送完整素材到第三方工单。

## 5. 统一错误体
```json
{"error":{"code":"ASSET_NOT_READY","message":"照片正在检查，请稍后","retryable":true},"request_id":"req_..."}
```
HTTP：400 参数，401 认证，403 无授权/资源越权（可统一对外 404 防探测），409 冲突，413 太大，415 格式，422 不合格图片，429 限流，503 服务繁忙。任务异步失败通过 job.status 表示，不能把生成失败伪装成 200 成功。
保留 `X-Request-ID` 追踪；API 必须声明字段最大长度、枚举和拒绝未知字段；鉴权错误不暴露用户存在性。

## 6. 安全/版本
所有 mutation 有身份鉴权、用户级限流、业务授权及审计；上传带 request-id；令牌有效期短、服务端可以撤销。若使用 refresh token，应为不可重用旋转令牌并安全存储；Beta 可通过 wx.login 重新获取登录态，避免首版复杂度。公共 API 版本 /v1；数据库和 worker 通过契约测试互相兼容。
具体机器可读接口草案见 [../specs/openapi.yaml](../specs/openapi.yaml)，以端到端自动测试为最终真相。
