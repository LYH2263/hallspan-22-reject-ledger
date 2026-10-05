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
3. 在「违规」查看间距或同卷相邻问题，以及排座拒绝记录。
4. 在「统计」查看占用与违规汇总。

## 排座三账（互斥）

`POST /api/seating/run` 只有两种结果，绝不混在一个回包里：

- **成功（200）**：新增方案行（方案账 +1），响应为方案本身，不带任何失败码；排座图与统计切到新方案；历史拒绝行原样保留。
- **失败（422）**：新增一条可查询的拒绝行（拒绝账 +1），字段恒为 `id / hall_id / reason_code / detail / persisted=false / created_at`，方案表行数不变，图与统计保持操作前。失败入口同构：考室不存在 `HALL_NOT_FOUND`、非法最小距 `INVALID_MIN_DISTANCE`、封闭场未全员落座 `UNPLACED_CANDIDATES`。

拒绝账查询：`GET /api/seating/rejections?hall_id=1`

## 开发与测试

```bash
docker compose exec api pytest -q
```
