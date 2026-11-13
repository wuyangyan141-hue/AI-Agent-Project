# 豆豆 · AI 学习桌宠

Electron + React/TypeScript 桌宠，FastAPI + LangChain + MCP + Skills 学习服务，SQLite 保存资料索引、对话、偏好、记忆和学习任务。

## 启动

需要 Node.js 20+（CI 使用22）、npm、Python 3.12。

- macOS：在终端进入项目目录，执行 `bash start-doudou.command`。
- Windows：运行 `start-doudou.bat`。
- 初次启动会安装依赖并构建程序，需要联网。应用默认离线运行，无需模型 API Key。
- 如果8000端口正在运行旧版本，先在旧后端终端按 Ctrl+C 停止它。启动器不会自动关闭其他进程。

出现小狗后，单击打开气泡聊天，双击打开完整窗口，“知识库”按钮可上传资料；按住身体或顶部拖动，右键可重启，快捷键为 macOS `⌘⇧R` / Windows `Ctrl+Shift+R`。沿用仓库已有图片和动画图集。

开发时可分别启动：

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另一个终端在项目根目录执行 `npm ci`，然后 `npm run dev`。只需浏览器预览时，可在 `apps/desktop` 执行 `npx vite --host 127.0.0.1`；浏览器预览不能验证原生窗口的置顶和拖动。

## 知识与学习流程

1. 上传 PDF / DOCX / PPTX / TXT，保留真实页码、幻灯片号或章节片段位置。扫描 PDF 需要先 OCR；旧版 DOC/PPT 需要先另存为新格式。
2. 自动区分聊天、资料问答、全文摘要、比较、个人信息、计划和复习。也可显式选择“普通聊天”或指定资料范围。
3. 离线使用关键词/BM25检索；配置语义向量后使用关键词与语义混合检索。无关问题返回资料不足，不自动把文档开头当命中结果。
4. 连续追问使用服务端保存的主题与范围。桌宠和主窗口同步消息、范围、引用、警告和计划草稿，恢复历史时仍能查看原文。
5. 全文导览遍历全部片段；有模型时按预算分组总结并汇总，章节结果缓存，失败重试可复用已完成分组。比较为每份资料分别取证。
6. 根据选定资料生成计划草稿，确认后保存任务。出题时固定保存问题、参考答案、评分要点和证据快照，批改不会重新换一份资料。等待复习题时仍可提问或聊天。
<img width="311" height="250" alt="8d0b101c4f58e22c94661965f87f0957" src="https://github.com/user-attachments/assets/b611dfe7-bbd7-49c8-9903-96e1044a27cf" />

## 可选模型

复制 `.env.example` 为项目根目录的 `.env`。配置后重启后端。

```dotenv
OPENAI_API_KEY=百炼或兼容服务密钥
OPENAI_BASE_URL=https://业务空间ID.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
AGENT_MODEL=openai:qwen-plus
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_BATCH_SIZE=10
```

两个模型可以使用不同的密钥和地址，通过 `EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL` 指定。`EMBEDDING_PROVIDER=openai` 表示兼容接口协议。地域、密钥和模型权限须匹配。切换向量模型或地址后，资料会提示重新索引。

模型路径使用工具调用格式的结构化输出：生成结论时必须带原文摘录，服务端检查摘录属于对应来源，再单独审核结论是否得到支持。此机制仍需要真实问答集评估，不能保证模型完全不出错。

当前交付默认不连接真实模型 API。离线显示相关原文、全文导览和各文档原文；普通材料复习保留回答供人工核对。综合摘要、跨语言语义检索与语义评分需要启用对应模型。测试替身验证接口与失败处理，不代表真实模型准确率。

**不要提交 `.env`、API Key、个人文档或数据库。密钥只交给本地 Python 后端，前端不保存密钥。**

## 检查与说明

```bash
npm run typecheck
npm test
npm run build
```

在 `services/api` 的虚拟环境中执行 `python -m pytest -q`。

- [API 协议](docs/api.md)
- [RAG 设计与验证](docs/rag-upgrade.md)
- [团队开发约定](docs/development.md)

本项目为单用户本地原型。数据位于后端运行目录的 `data/`，服务默认绑定 `127.0.0.1`。当前仍需在目标操作系统验收真实桌宠窗口行为。
