# Changelog

## v0.2.0 — 记忆 + 自我进化 + 跨平台 + 视觉模型自动选

### 新功能

**记忆模块 (memory.py)**
- SQLite 持久化存储：问题记录、知识点追踪、用户偏好、会话管理
- 自动追踪薄弱环节（正确率 < 70% 的知识点）
- 学习报告：输入"我的学习报告"查看统计

**自我进化 (evolution.py)**
- 每次交互后 AI 自动分析：提取知识点、评估难度、识别偏好
- 自动推荐下一步学习方向：输入"下一步学什么"
- 会话生命周期管理，退出时生成总结

**跨平台支持 (platform.py)**
- 统一 Android (Termux) + Windows + Linux 三平台
- Android: `termux-camera-photo` 拍照 / `termux-storage-get` 选相册
- Windows: `tkinter` 文件选择对话框选图
- 字体自动检测：Noto CJK / Microsoft YaHei / SimHei
- 路径自适应：Android `~/.hermes/`，Windows `%LOCALAPPDATA%/hermes/`

**视觉模型自动切换**
- 文字对话用用户偏好模型（如 deepseek-v4-flash）
- 拍照看图自动找可用视觉模型：智谱 GLM-4V-Plus > OpenAI GPT-4o > Claude 等
- 无需用户手动切 provider

**导出增强 (exporter.py)**
- 支持格式：TXT + PNG + JPG + PDF + DOCX
- 导出图片自动合成：题目文字 + 几何图
- AI 自动提取题目描述（而非原始指令）

**终端预览增强**
- 几何图生成后自动 chafa 终端渲染
- 图片复制到公共目录（Android `/sdcard/Download/`）

### 架构变化

```
study_buddy/
├── __main__.py      ← 重写：自然语言输入，零命令
├── bot.py           ← 重写：意图路由 + 自我进化集成
├── solver.py        ← 重写：视觉降级逻辑
├── drawer.py        ← 重构：跨平台字体 + 路径
├── exporter.py      ← 重写：多格式 + 合成图
├── memory.py        ← 新增：SQLite 持久记忆
├── evolution.py     ← 新增：自我进化
└── platform.py      ← 新增：跨平台适配
```

### 已知问题
- DeepSeek API 不支持图像输入，拍照自动走智谱 GLM-4V-Plus
- 需用户自行配置至少一个 API key
