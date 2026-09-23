# 万能视频下载

打开网页、粘贴链接、选清晰度、点下载。电脑和手机都能用，不需要安装客户端。

基于 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 薄封装，不修改其源码，可随时跟随上游更新。

更完整的背景与架构说明：

- [docs/01-需求分析文档.md](docs/01-需求分析文档.md)
- [docs/02-方案设计文档.md](docs/02-方案设计文档.md)

## 环境

- Python 3.12+（本仓库在 3.14 下验证过）
- Node.js 20+
- FFmpeg（必须在 PATH 中，用于合并音视频轨和提取 MP3）

## 启动

```bash
# 1. 后端
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2. 前端（另开一个终端）
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173

生产构建：`cd frontend && npm run build`，然后只启动后端。FastAPI 会托管 `frontend/dist`。

## 冒烟测试

```bash
backend/.venv/Scripts/python.exe scripts/api_smoke_test.py "https://www.youtube.com/watch?v=jNQXAC9IVRw"
```

## 维护

平台反爬策略变化很快。解析失效时先升级引擎，不要改 yt-dlp 源码：

```bash
backend/.venv/Scripts/python.exe -m pip install -U yt-dlp
```

会员内容或需登录的高清源：把浏览器导出的 Netscape `cookies.txt` 放到 `backend/data/cookies/<根域名>.txt`（例如 `bilibili.com.txt`）或 `backend/data/cookies.txt`。

## 免责声明

本项目仅提供技术工具，请在遵守相关法律法规与平台协议的前提下，将下载内容用于个人学习、研究或合法备份，不得用于商业传播。因使用者行为导致的版权纠纷由使用者自行承担。
