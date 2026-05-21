# OpenAI 格式兼容性调研报告

> 生成日期: 2026-05-22 | 来源: 15+ | 置信度: 高

## 核心结论

**当前项目（learn-claude-code）不支持 OpenAI 格式的 API 接口。** 整个项目 20 个章节全部基于 Anthropic SDK 和 Anthropic Messages 协议构建。当前能跑通智谱，是因为智谱提供了 `/api/anthropic` 这个 Anthropic 协议兼容端点做协议转换。

如果公司大模型**只提供 OpenAI 格式**的接口，有三条路可以走。

---

## 三条路径对比

| 方案 | 改动量 | 可维护性 | 推荐场景 |
|------|--------|----------|----------|
| **A. 公司模型提供 Anthropic 兼容端点** | 零改动（只改 `.env`） | 最好 | 公司自建了协议适配层 |
| **B. 用 LiteLLM 做统一适配层** | 中等（替换 client 初始化） | 好 | 需要多模型切换 |
| **C. 直接改用 OpenAI SDK** | 大（每个章节都要改） | 一般 | 公司只需要 OpenAI 格式 |

---

## 方案 A：零改动路线

**前提：公司大模型平台提供 Anthropic 协议兼容端点。**

和智谱的原理完全一样，只需改 `.env`：

```bash
ANTHROPIC_BASE_URL=https://your-company-gateway/api/anthropic
MODEL_ID=your-model-name
ANTHROPIC_API_KEY=your-key
```

### 已知支持 Anthropic 兼容端点的国内厂商

| 厂商 | 国际端点 | 国内端点 | 模型 ID |
|------|----------|----------|---------|
| 智谱 (GLM) | `https://api.z.ai/api/anthropic` | `https://open.bigmodel.cn/api/anthropic` | `glm-5` |
| MiniMax | `https://api.minimax.io/anthropic` | `https://api.minimaxi.com/anthropic` | `MiniMax-M2.5` |
| Kimi (月之暗面) | `https://api.moonshot.ai/anthropic` | `https://api.moonshot.cn/anthropic` | `kimi-k2.5` |
| DeepSeek | `https://api.deepseek.com/anthropic` | 同左 | `deepseek-chat` |

### 工作原理

```
代码 (Anthropic SDK)
    │
    │  Anthropic 协议格式请求
    ▼
厂商 /api/anthropic 端点 (协议适配层)
    │
    │  翻译为厂商内部格式
    ▼
厂商模型 (如 GLM-5)
    │
    │  翻译回 Anthropic 协议格式
    ▼
代码 (正常解析响应)
```

---

## 方案 B：LiteLLM 统一适配（推荐用于公司部署）

**LiteLLM** 是目前最成熟的跨模型适配库，支持 100+ 提供商，统一为 OpenAI 格式调用。

### 简介

```bash
pip install litellm
```

LiteLLM 的核心价值：写一套 OpenAI 格式的代码，底层自动翻译成各家协议。支持 Anthropic、OpenAI、智谱、DeepSeek 等所有主流厂商，完整支持 tool calling 的协议转换。

### 基本用法

```python
import litellm

# 同一套代码，切换不同模型
response = litellm.completion(
    model="openai/gpt-4o",            # OpenAI
    # model="deepseek/deepseek-chat", # DeepSeek
    # model="glm-5.1",                # 智谱 (配合 api_base)
    messages=[{"role": "user", "content": "Hello"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
    }],
)
# 响应始终以 OpenAI 格式返回，无论底层是哪家厂商
```

### 改动范围

使用 LiteLLM 时，agent loop 内部的消息格式、stop_reason 判断、tool_result 拼接仍需从 Anthropic 格式改为 OpenAI 格式。改动集中在协议适配层，agent 的业务逻辑（工具执行、循环控制）不变。

---

## 方案 C：直接改用 OpenAI SDK

改动量最大但最直接，无额外依赖。

### 1. 安装依赖变更

```diff
# requirements.txt
- anthropic>=0.25.0
+ openai>=1.30.0
  python-dotenv>=1.0.0
  pyyaml>=6.0
```

### 2. 客户端初始化

```python
# ── Anthropic（当前）──
from anthropic import Anthropic
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]

# ── OpenAI（改为）──
from openai import OpenAI
client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),  # 如 https://open.bigmodel.cn/api/paas/v4
    api_key=os.environ["OPENAI_API_KEY"],
)
MODEL = os.environ["MODEL_ID"]
```

### 3. 工具定义

```python
# ── Anthropic 格式（当前）──
TOOLS = [{
    "name": "bash",
    "description": "Run a shell command.",
    "input_schema": {          # ← Anthropic 用 input_schema
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
}]

# ── OpenAI 格式（改为）──
TOOLS = [{
    "type": "function",         # ← OpenAI 需要 type 包装
    "function": {               # ← 嵌套在 function 下
        "name": "bash",
        "description": "Run a shell command.",
        "parameters": {         # ← OpenAI 用 parameters
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
}]
```

### 4. API 调用和系统提示词

```python
# ── Anthropic（当前）──
response = client.messages.create(
    model=MODEL,
    system=SYSTEM,              # ← system 是顶级参数
    messages=messages,
    tools=TOOLS,
    max_tokens=8000,
)

# ── OpenAI（改为）──
response = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "system", "content": SYSTEM}] + messages,  # ← system 在 messages 里
    tools=TOOLS,
    max_tokens=8000,
)
```

### 5. 响应解析（agent loop 核心）

```python
# ── Anthropic（当前）──
# 追加助手回复
messages.append({"role": "assistant", "content": response.content})
# 判断是否调用工具
if response.stop_reason != "tool_use":
    return
# 提取工具调用
for block in response.content:
    if block.type == "tool_use":
        command = block.input["command"]     # input 已是 dict
        tool_id = block.id

# ── OpenAI（改为）──
# 追加助手回复
messages.append(response.choices[0].message)
# 判断是否调用工具
if response.choices[0].finish_reason != "tool_calls":
    return
# 提取工具调用
for tool_call in response.choices[0].message.tool_calls:
    import json
    args = json.loads(tool_call.function.arguments)  # arguments 是 JSON 字符串
    command = args["command"]
    tool_id = tool_call.id
```

### 6. 工具结果回传

```python
# ── Anthropic（当前）──
messages.append({"role": "user", "content": [{
    "type": "tool_result",
    "tool_use_id": block.id,
    "content": output,
}]})

# ── OpenAI（改为）──
messages.append({
    "role": "tool",                    # ← 独立的 tool 角色
    "tool_call_id": tool_call.id,      # ← 字段名不同
    "content": output,
})
```

---

## Anthropic vs OpenAI 协议差异速查表

### 工具定义

| 维度 | Anthropic | OpenAI |
|------|-----------|--------|
| 顶层结构 | 扁平，直接包含 name/description | 嵌套在 `{"type": "function", "function": {...}}` 下 |
| 参数字段名 | `input_schema` | `parameters` |

### 工具调用响应

| 维度 | Anthropic | OpenAI |
|------|-----------|--------|
| 调用位置 | `content[]` 中的 `tool_use` block | `message.tool_calls[]` 列表 |
| 参数格式 | 已解析的 dict (`input`) | **JSON 字符串** (`function.arguments`)，需 `json.loads()` |
| ID 前缀 | `toolu_...` | `call_...` |
| 停止原因 | `stop_reason: "tool_use"` | `finish_reason: "tool_calls"` |
| 文本混合 | 文本和工具调用可共存于 `content[]` | `content` 为 `None` 或字符串，工具调用分开 |

### 工具结果回传

| 维度 | Anthropic | OpenAI |
|------|-----------|--------|
| 消息角色 | `role: "user"` | `role: "tool"` |
| 结果结构 | `content[]` 中的 `tool_result` block | 独立消息，`tool_call_id` + `content` |
| ID 匹配字段 | `tool_use_id` | `tool_call_id` |
| 错误信号 | `is_error: true` | 无标准化错误字段 |

### 其他结构差异

| 维度 | Anthropic | OpenAI |
|------|-----------|--------|
| 系统提示词 | 顶级 `system` 参数 | `messages` 中的 `role: "system"` |
| max_tokens | 必需，无默认值 | 可选 |
| temperature 范围 | 0-1 | 0-2 |
| 助手预填充 | 允许最后一条消息为 `role: "assistant"` | 不支持 |
| 工具选择 | `{"type": "auto"|"any"|"tool", "name": "..."}` | `"auto"|"none"|"required"|{"type": "function", ...}` |

### 停止原因对照

| Anthropic `stop_reason` | OpenAI `finish_reason` | 含义 |
|------------------------|------------------------|------|
| `"end_turn"` | `"stop"` | 模型自然完成 |
| `"max_tokens"` | `"length"` | 达到 token 限制 |
| `"tool_use"` | `"tool_calls"` | 模型请求工具调用 |
| `"stop_sequence"` | `"stop"` | 命中了停止序列 |
| 无对应 | `"content_filter"` | 内容被过滤 |

---

## 统一适配工具生态

### LiteLLM（最成熟，推荐）

- 标准化所有提供商使用 OpenAI 格式
- 生产就绪，支持 100+ 提供商
- 完整的 tool calling 跨协议转换
- 文档: https://docs.litellm.ai/docs/providers

### llm-api-adapter（提供商无关的工具定义）

- 一次定义工具，OpenAI / Anthropic / Gemini 通用
- `ToolSpec` 统一模式
- 较新但活跃

### claude-code-provider-proxy（协议级代理）

- 详细的 Anthropic-to-OpenAI 协议映射文档
- 可作为自建翻译层的参考
- 仓库: https://github.com/ujisati/claude-code-provider-proxy

---

## 建议决策路径

```
公司大模型平台是否提供 Anthropic 兼容端点？
    │
    ├── 是 ──→ 方案 A：零改动，只改 .env
    │
    └── 否 ──→ 是否需要同时支持多家模型？
                │
                ├── 是 ──→ 方案 B：LiteLLM 统一适配
                │
                └── 否 ──→ 方案 C：直接改用 OpenAI SDK
```

---

## 参考来源

1. [Anthropic Docs: OpenAI SDK Compatibility](https://platform.claude.com/docs/en/api/openai-sdk)
2. [Anthropic Docs: Build a Tool-Using Agent](https://platform.claude.com/docs/en/agents-and-tools/tool-use/build-a-tool-using-agent)
3. [OpenAI Docs: Function Calling](https://developers.openai.com/api/docs/guides/function-calling)
4. [LiteLLM Docs: Providers](https://docs.litellm.ai/docs/providers)
5. [DeepSeek API Docs](https://api-docs.deepseek.com/zh-cn/)
6. [Provider Proxy Mapping (GitHub)](https://github.com/ujisati/claude-code-provider-proxy/blob/main/docs/mapping.md)
7. [llm-api-adapter (DEV Community)](https://dev.to/inozem/one-tool-calling-interface-for-openai-claude-and-gemini-2l1c)
8. [Portkey: Responses API vs Chat Completions vs Anthropic Messages](https://portkey.ai/blog/open-ai-responses-api-vs-chat-completions-vs-anthropic-anthropic-messages-api)
