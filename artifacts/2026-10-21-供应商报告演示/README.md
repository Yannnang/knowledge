# 对话产物归档：供应商报告渲染链路演示（DEMO）

- **来源**：Multica × 飞书直聊会话（后端开发助手 × yang）
- **日期**：2026-10-21
- **性质**：⚠ 全部数字为**虚构演示数据**，仅用于验证 supplier-report-彭于晏版 skill 的模板渲染链路在 Multica 运行时上可用，不代表任何真实供应商经营情况。

## 文件清单

| 文件 | 说明 |
|---|---|
| `supplier-999999-演示报告-DEMO.html` | 最终产物：单文件 HTML 报告（虚构 supplier 999999，2026 年 YTD，9 章节全开），顶部含演示数据横幅，校验器 0 fail |
| `data.json` | 演示数据源（结构与 skill 的 `fetch_data.py` 产出完全对齐，数字虚构但内部自洽） |
| `gen_demo_data.py` | 生成 `data.json` 的脚本（复用 skill 的 `window.py` 计算真实窗口结构） |
| `insert_banner.py` | 在报告 HTML 顶部插入「演示数据」横幅的脚本 |

## 复现步骤

```bash
python gen_demo_data.py                       # → data.json
python <skill>/tools/build_report.py --data data.json --out html-preview/index.html --lang zh --currency CNY
python insert_banner.py html-preview/index.html
node <skill>/templates/validate-report.js html-preview/index.html   # 退出码 0 = 全绿
```

`<skill>` = supplier-report-彭于晏版 skill 目录（运行时本机 `~/.claude/skills/` 下）。

## 背景结论（当次会话验证）

- Multica 运行时上模板渲染链路（Python/Node/Chart.js CDN）完全可用
- 唯一断点是取数通道：data-mcp（data-api-mcp.didaadmin.com）从当前运行时网络不可达，且无凭证；真实报告需先打通网络 + 注册 MCP 凭证

## 同会话的其他产物（不在本仓库）

- 飞书云文档《介绍multica》（空文档，lark-cli 创建通道验证）：https://didatravel.feishu.cn/docx/Wp8xdzZlwouE6fx9TADcteMbnng
