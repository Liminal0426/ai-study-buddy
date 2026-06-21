# AI Study Buddy v0.2.0

跨平台 AI 学习助手（Android + Windows）

## 快速开始

```bash
pip install -e .
python -m study_buddy
```

## 功能

| 输入 | 行为 |
|------|------|
| `x²+2x+1=0怎么解` | 分步解题 + 自动记录知识点 |
| `画y=x²的图像` | 画几何图 + 终端预览 |
| `拍个照` | 拍照 → 视觉模型分析 |
| `我的学习报告` | 学习统计、薄弱环节 |
| `下一步学什么` | AI 推荐学习方向 |

## 跨平台适配

- **Android (Termux)**: `pkg install termux-api chafa`
- **Windows**: `pip install study-buddy` + `pip install opencv-python`（如需拍照）

## 架构

```
study_buddy/
├── __main__.py      — CLI 入口
├── bot.py           — 机器人调度器（意图路由 + 自我进化）
├── solver.py        — 多模型 LLM 客户端
├── config.py        — 多 Provider 配置
├── drawer.py        — matplotlib 几何画图
├── exporter.py      — 导出 TXT/PDF/DOCX
├── memory.py        — SQLite 持久记忆
├── evolution.py     — 自我进化（交互后自动分析）
├── platform.py      — 跨平台适配（路径/相机/字体）
└── db.py            — 旧版数据库
```
