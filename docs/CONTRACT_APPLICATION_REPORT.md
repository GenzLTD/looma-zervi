# P0 契约：投递匹配报告

> **仓库真源：** `looma-zervi/docs/CONTRACT_APPLICATION_REPORT.md`（与 DemoPeter `docs/CONTRACT_LOOMA_APPLICATION_REPORT.md` 同步）  
> **实现端点：** `GET /v1/application/<application_id>/report`  

> **日期：** 2026-08-08  
> **目标：** DemoPeter「报告抽屉」— 投递后拉回匹配摘要本地再 Ask  
> **Looma 依赖：** 需 Looma 侧实现此端点  
> **DemoPeter 侧：** `looma_client.get_application_report(application_id)` + `kb_service` 缓存到 metadata

---

## 1. 端点

```
GET /v1/application/<application_id>/report
Authorization: Bearer <token>
```

---

## 2. 鉴权

- **求职者**（该 application 的 owner）：可读自己的报告
- **HR**（该 application 关联 job 的发布者）：可读所有投递到该职位的报告
- 其他角色 → `403 Forbidden`

---

## 3. 行为（懒计算 + 缓存）

```
1. 查 application → 取 resume_id + job_id
2. 查 match_reports 表：是否已有 (resume_id, job_id) 的已存报告？
   → 有且未过期 → 直接返回（304 语义转为 200 + cached: true）
   → 无 → 进入步骤 3
3. 取 resume 正文 + job 正文 → 调用现有匹配引擎（复用 POST /v1/jobs/match 逻辑）
4. 可选：落 match_reports（report_type="application", application_id=<id>）
5. 返回摘要
```

**不阻塞规则**：报告计算失败时返回 `422` 并说明原因（resume 未解析完 / job 无描述 / 匹配引擎不可用），不抛 500。

---

## 4. 响应

### 4.1 成功 (200)

```json
{
  "application_id": "app_abc123",
  "resume_id": "res_xyz789",
  "job_id": "job_demo_001",
  "job_title": "Python 后端工程师",
  "match_report": {
    "report_id": "rpt_...",
    "cached": false,
    "overall_score": 0.78,
    "skill_match": {
      "matched": ["Python", "FastAPI", "PostgreSQL"],
      "missing": ["Docker", "Redis"],
      "partial": ["React"]
    },
    "gaps": [
      {
        "skill": "Docker",
        "importance": "required",
        "suggestion": "建议至少完成 1 个容器化项目"
      },
      {
        "skill": "Redis",
        "importance": "preferred",
        "suggestion": "了解缓存策略与常见场景即可满足"
      }
    ],
    "suggestions": [
      "你的 Python 后端经验与岗位高度匹配，补充容器化技能可提升约 10% 匹配分",
      "React 为加分项，非必需，可暂缓"
    ],
    "generated_at": "2026-08-08T14:30:00Z"
  }
}
```

### 4.2 已缓存 (200, cached)

```json
{
  "application_id": "app_abc123",
  "resume_id": "res_xyz789",
  "job_id": "job_demo_001",
  "job_title": "Python 后端工程师",
  "match_report": {
    "report_id": "rpt_abc",
    "cached": true,
    "overall_score": 0.78,
    "skill_match": { "...": "同上" },
    "gaps": [ "..." ],
    "suggestions": [ "..." ],
    "generated_at": "2026-08-07T09:00:00Z"
  }
}
```

### 4.3 错误

| 状态码 | 含义 | 响应体 |
|--------|------|--------|
| `401` | 未认证 | `{"error": "unauthorized", "message": "缺少或无效 Bearer token"}` |
| `403` | 无权访问 | `{"error": "forbidden", "message": "你不是该投递的求职者或该职位的 HR"}` |
| `404` | 投递不存在 | `{"error": "not_found", "message": "application <id> 不存在"}` |
| `422` | 无法计算 | `{"error": "unprocessable", "message": "resume/job 内容不足以计算匹配", "detail": {"resume_ready": false, "job_ready": true}}` |

---

## 5. 与 `match-reports` 资源的关系

| 资源 | 用途 | 触发方 |
|------|------|--------|
| `POST /v1/jobs/match` | 即时匹配（不落库） | DemoPeter / 求职者实时预览 |
| `POST /v1/match-reports` | 预计算并存报告 | HR / 批量跑匹配（可独立） |
| `GET /v1/match-reports` | 翻历史报告 | HR 看板 |
| **`GET /v1/application/<id>/report`** | **投递维度的懒获取** | **DemoPeter「报告抽屉」** |

`GET /v1/application/<id>/report` 内部：
- 优先读 `match_reports WHERE resume_id=? AND job_id=?`（最近一条）
- 无缓存时调用匹配引擎（同 `POST /v1/jobs/match` 逻辑），**可选**写入 `match_reports`

**实现建议**：Looma 侧 match-reports 已存在时，此端点几乎只是一次查询 + 一层权限检查。

---

## 6. DemoPeter 侧消费

```python
# looma_client.py 新增方法
def get_application_report(self, application_id: str) -> dict:
    """GET /v1/application/<id>/report → 匹配报告摘要"""
    self.ensure_auth()
    return self._request("GET", f"/v1/application/{application_id}/report")

# kb_service.py 缓存写入
# push_to_looma 成功后：
#   report = api.get_application_report(application["cloud_application_id"])
#   patch["looma_report"] = report["match_report"]
#   db.update_document_metadata(doc_id, patch)
```

**报告抽屉 UI**：文档详情页展示 `overall_score` + gaps + suggestions 卡片；支持「对报告提问」走本地 RAG。

---

## 7. 非功能需求

- **幂等**：同一 application 多次 GET 返回相同结果（首次计算后缓存）
- **缓存策略**：以 `(resume_id, job_id)` 为键；resume 更新后旧缓存失效（TBD：是否支持 `?refresh=true` 参数）
- **超时**：匹配计算 < 15s；超时返回 422 + `"detail": {"reason": "timeout"}`

---

## 8. 修订

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-08-08 | 初版：基于 D-P0-4 报告抽屉需求，与 Looma 现有 match/match-reports 对齐 |
