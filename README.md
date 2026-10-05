# HallSpan 考场间距排座

在考室网格上按最小曼哈顿距离排座，同试卷套不得四邻相邻，并输出违规与统计。

技术栈：Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Vue 3 / TypeScript / Vite

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4900 |
| API | http://localhost:9900 |
| API 文档 | http://localhost:9900/docs |
| Postgres | localhost:5450 |

健康检查：`GET http://localhost:9900/api/health`

## 使用说明

1. 在「考室」「考生」「试卷套」确认基础数据。
2. 打开「排座图」执行间距排座。
3. 在「违规」查看间距或同卷相邻问题。
4. 在「统计」查看占用与违规汇总。
5. 在「拒绝记录」查看排座失败留痕。

## 三本互斥账

排座结果分为三本互斥的账，不存在"一个回包改两个字段"的混合态：

| 账 | 内容 | 接口 |
| --- | --- | --- |
| 方案账 | 仅成功写库的排座方案 | `GET /api/seating/plans` |
| 拒绝账 | 每次失败一行（原因码、说明、是否写库=否） | `GET /api/seating/rejections` |
| 图展示 | 当前图，只读最新方案，无副作用 | `GET /api/seating/latest` |

`POST /api/seating/run` 的两种结局互斥：

- **成功**（201）：新增方案行，回包为方案（`plan_id`、座位、统计），不含失败码；拒绝账一行不增不减，图跟新方案。
- **失败**（4xx）：新增一行同构拒绝行（`rejection_id`、`reason_code`、`detail`、`persisted=false`、`created_at`），方案表行数不变，图与统计保持操作前。

失败入口与原因码（拒绝行字段同构）：

| 入口 | reason_code | HTTP |
| --- | --- | --- |
| 考室不存在 | `HALL_NOT_FOUND` | 404 |
| 非法最小距（min_manhattan < 1） | `INVALID_MIN_DISTANCE` | 422 |
| 封闭场全员落座失败（封闭考室有人未排上） | `CLOSED_HALL_UNPLACED` | 409 |

种子数据中 `H102` 为封闭场（2×2、最小距 2、5 名考生），对其执行排座必触发 `CLOSED_HALL_UNPLACED`，可用于演示拒绝账。

## 开发与测试

```bash
docker compose exec api pytest -q
```
