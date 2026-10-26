# org-sync — 飞书通讯录 → 组织档案每日全量快照

MYIT-7 / M2「组织档案数据契约 v1.0」（冻结于 MYIT-10 评论）的**生产方**：每日拉取飞书通讯录，产出部门/人员拉链全量快照，供数仓 `ods_hr_dept_df` / `ods_hr_user_df` 消费。

## 产物

```
{ORG_SYNC_OUTPUT_DIR}/dt={YYYY-MM-DD}/
├── org_department.jsonl   # 完整拉链表（含历史闭行），字段=契约 §2
├── org_user.jsonl         # 完整拉链表，字段=契约 §3
└── manifest.json          # 行数统计 / synced_at / 契约版本 / 脱敏 app_id
```

- 一行一个 JSON 对象（UTF-8）；`valid_to == "9999-12-31"` 表示当前有效行；
- 时间戳 UTC，`dt` 分区按 Asia/Shanghai；
- 同日重跑幂等（拉链做同日替换，不产生非法区间）。

## 前置：飞书自建应用

在企业飞书开放平台创建自建应用，授予**通讯录只读**权限并开通（scope 名称以管理后台当前页面为准）：

- 获取部门组织架构信息（部门列表/子部门）；
- 获取用户基本信息（按部门取用户）；
- 获取用户 user ID（`feishu_user_id` 字段依赖；缺授权时该列为 null，不阻塞）。

将应用可见范围设为全员（否则通讯录只能看到部分部门）。

## 运行

```bash
pip install -r requirements.txt

# 凭据只走环境变量（仓库红线：严禁硬编码/提交）
export FEISHU_APP_ID=cli_xxx
export FEISHU_APP_SECRET=xxx
export ORG_SYNC_OUTPUT_DIR=./output   # 可选，默认 ./output
export ORG_SYNC_STATE_DIR=./state     # 可选，默认 ./state

python run_sync.py                    # 可选 --date YYYY-MM-DD 补跑指定分区
```

每日调度建议 02:00（Asia/Shanghai）：Linux crontab `0 2 * * *`；Windows 任务计划程序同等配置。

## 关键约定（契约 v1.0 映射）

| 约定 | 实现 |
|---|---|
| `dept_id` ≡ 首次入库 `open_department_id` | 全链路 `department_id_type=open_department_id` |
| `user_id` ≡ 首次入库 `union_id` | union_id 缺失 = 硬失败（授权问题，勿降级为 open_id） |
| 主部门 | `department_ids[0]`（飞书惯例首位为主部门）；不在部门树内则 NULL + 告警 |
| 离职判定 | 全量同步中消失 → 当日快照 `departed` + `departed_at`=首次发现时刻（日精度） |
| 部门裁撤 | 消失 → `disabled` 开行，不物理删除 |
| 拉链触发 | 部门：name/parent/level/path/status；人员：primary_dept_id/employment_status（其余字段现值原位更新） |
| 多部门成员 | 按 union_id 去重，可空字段（user_id/email）用后续出现补全 |

## 测试与故障

```bash
python -m pytest tests/ -q   # 24 用例：拉链语义 / 拉取归一化 / 写出与配置
```

- `SnapshotError: 缺少 union_id` → 应用通讯录授权范围不足；
- 飞书 `code != 0` → 报错含 code/msg，对照开放平台错误码（常见：无权限 / 应用不可见）；
- 限流与 5xx 已内置指数退避重试（最多 3 次）；
- 补跑历史分区：`--date`（注意状态文件只保存最新一份，跨多日补跑需按日顺序执行）。
