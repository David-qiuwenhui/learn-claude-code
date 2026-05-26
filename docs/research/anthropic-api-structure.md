# Anthropic Messages API 响应结构详解

> 基于智谱 GLM-5.1 的 Anthropic 兼容端点实际返回数据整理（2026-05-24）

## 概述

Anthropic Messages API 的端点为 `POST /v1/messages`，请求和响应都遵循 Anthropic 自有的 JSON 协议格式。本文档聚焦于**响应体（Response Body）**的完整结构，并结合 s01_agent_loop 代码说明每个字段在 Agent 中的实际用途。

---

## 一、响应体顶层结构

```json
{
  "id":             "string",      // 消息唯一 ID，格式: msg_{timestamp}{hash}
  "type":           "message",     // 固定值，表示这是一个消息对象
  "role":           "assistant",   // 固定值，响应始终来自 assistant
  "model":          "string",      // 实际使用的模型名称（如 "glm-5.1"）
  "content":        [...],         // 内容块数组，见下文详述
  "stop_reason":    "string",      // 停止原因，见下文枚举
  "stop_sequence":  null,          // 命中的停止序列（通常为 null）
  "stop_details":   null,          // 停止详情（通常为 null）
  "container":      null,          // 容器信息（通常为 null）
  "usage":          {...}          // Token 用量统计，见下文详述
}
```

### 1.1 stop_reason 枚举值

| 值                | 含义                 | Agent 中的处理                 |
| ----------------- | -------------------- | ------------------------------ |
| `"end_turn"`      | 模型自然完成回复     | Agent 停止循环，向用户展示文本 |
| `"tool_use"`      | 模型请求调用工具     | Agent 执行工具并将结果喂回模型 |
| `"max_tokens"`    | 达到 max_tokens 上限 | 回复被截断，Agent 需处理       |
| `"stop_sequence"` | 命中了自定义停止序列 | 较少见                         |

> **s01 代码对应**: 第 100 行 `if response.stop_reason != "tool_use": return`
> 当 stop_reason 不是 tool_use 时，Agent 循环结束。

---

## 二、content 内容块数组

`content` 是一个数组，可包含**多个内容块（block）**，每个 block 有 `type` 字段区分类型。

### 2.1 文本块 (type: "text")

模型返回的纯文本内容：

```json
{
  "type": "text",
  "text": "好的，我来帮你查看当前目录下的文件：",
  "citations": null
}
```

| 字段        | 类型       | 说明                              |
| ----------- | ---------- | --------------------------------- |
| `type`      | string     | 固定 `"text"`                     |
| `text`      | string     | 文本内容                          |
| `citations` | null/array | 引用信息（智谱兼容端点返回 null） |

### 2.2 工具调用块 (type: "tool_use")

模型请求调用工具时返回：

```json
{
  "type": "tool_use",
  "id": "call_3ffc8770a1b44b97ae53c49f",
  "name": "bash",
  "input": {
    "command": "ls"
  },
  "caller": null
}
```

| 字段     | 类型   | 说明                                             |
| -------- | ------ | ------------------------------------------------ |
| `type`   | string | 固定 `"tool_use"`                                |
| `id`     | string | 工具调用的唯一 ID，用于后续回传结果时匹配        |
| `name`   | string | 要调用的工具名称（如 `"bash"`）                  |
| `input`  | object | 工具参数，**已解析为 dict**（不需要 json.loads） |
| `caller` | null   | 调用者信息（通常为 null）                        |

> **s01 代码对应**:
>
> - 第 106 行 `if block.type == "tool_use":` 筛选工具调用块
> - 第 107 行 `block.input['command']` 直接读取参数
> - 第 112 行 `block.id` 记录 ID 用于回传结果

### 2.3 content 可以同时包含多种块

一次响应中可以**同时包含文本和工具调用**：

```json
"content": [
  {
    "type": "text",
    "text": "好的，我来帮你查看当前目录下的文件："
  },
  {
    "type": "tool_use",
    "id": "call_3ffc8770a1b44b97ae53c49f",
    "name": "bash",
    "input": {"command": "ls"}
  }
]
```

模型先说一句话，再调用工具。s01 代码中会把整个 content（包含 text 和 tool_use）一起追加到消息历史：

> **s01 代码对应**: 第 97 行 `messages.append({"role": "assistant", "content": response.content})`

---

## 三、usage Token 用量统计

```json
"usage": {
  "input_tokens":               177,
  "output_tokens":              20,
  "cache_read_input_tokens":    0,
  "cache_creation_input_tokens": null,
  "cache_creation":             null,
  "server_tool_use": {
    "web_search_requests":      0,
    "web_fetch_requests":       null
  },
  "service_tier":               "standard",
  "inference_geo":              null
}
```

| 字段                          | 类型     | 说明                                 |
| ----------------------------- | -------- | ------------------------------------ |
| `input_tokens`                | int      | 输入消耗的 token 数                  |
| `output_tokens`               | int      | 输出生成的 token 数                  |
| `cache_read_input_tokens`     | int      | 从缓存读取的 token 数（节省费用）    |
| `cache_creation_input_tokens` | int/null | 创建缓存消耗的 token 数              |
| `service_tier`                | string   | 服务层级（如 `"standard"`）          |
| `server_tool_use`             | object   | 服务端工具使用统计（如网页搜索次数） |

---

## 四、完整真实示例

### 示例 1：纯文本回复（模型不调用工具）

请求：

```json
{
  "model": "glm-5.1",
  "max_tokens": 100,
  "messages": [{ "role": "user", "content": "说一个字：好" }]
}
```

响应：

```json
{
  "id": "msg_20260524085856f5693ae2848849c1",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "好！",
      "citations": null
    }
  ],
  "model": "glm-5.1",
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "stop_details": null,
  "container": null,
  "usage": {
    "input_tokens": 10,
    "output_tokens": 3,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": null,
    "cache_creation": null,
    "server_tool_use": {
      "web_search_requests": 0,
      "web_fetch_requests": null
    },
    "service_tier": "standard",
    "inference_geo": null
  }
}
```

Agent 处理流程：

1. `stop_reason` 为 `"end_turn"` → 不是工具调用 → 循环结束
2. 遍历 `content`，提取 `type: "text"` 块 → 输出 `"好！"` 给用户

### 示例 2：工具调用回复（模型请求执行命令）

请求：

```json
{
  "model": "glm-5.1",
  "max_tokens": 300,
  "system": "You are a coding agent. Use bash to solve tasks.",
  "messages": [
    {
      "role": "user",
      "content": "当前目录下有哪些文件？请用 bash 工具执行 ls 命令查看"
    }
  ],
  "tools": [
    {
      "name": "bash",
      "description": "Run a shell command.",
      "input_schema": {
        "type": "object",
        "properties": { "command": { "type": "string" } },
        "required": ["command"]
      }
    }
  ]
}
```

响应：

```json
{
  "id": "msg_20260524085859b42da1a5c4474638",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "好的，我来帮你查看当前目录下的文件：",
      "citations": null
    },
    {
      "type": "tool_use",
      "id": "call_3ffc8770a1b44b97ae53c49f",
      "name": "bash",
      "input": { "command": "ls" },
      "caller": null
    }
  ],
  "model": "glm-5.1",
  "stop_reason": "tool_use",
  "stop_sequence": null,
  "stop_details": null,
  "container": null,
  "usage": {
    "input_tokens": 177,
    "output_tokens": 20,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": null,
    "cache_creation": null,
    "server_tool_use": {
      "web_search_requests": 0,
      "web_fetch_requests": null
    },
    "service_tier": "standard",
    "inference_geo": null
  }
}
```

Agent 处理流程：

1. `stop_reason` 为 `"tool_use"` → 模型要调用工具 → 继续循环
2. 遍历 `content`，找到 `type: "tool_use"` 块
3. 读取 `block.name` → `"bash"`
4. 读取 `block.input["command"]` → `"ls"`
5. 执行 `ls` 命令，获取输出
6. 构造工具结果，回传给模型：

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "call_3ffc8770a1b44b97ae53c49f",
      "content": "README.md\ncode.py\nimages\n..."
    }
  ]
}
```

7. 模型收到结果后继续回复，循环直到 `stop_reason` 不再是 `"tool_use"`

---

## 五、请求体（入参）详解

当你（或 Agent 代码）调用 Anthropic Messages API 时，发送的是一个 HTTP POST 请求，请求体是 JSON 格式。

### 5.1 请求体完整字段

```json
{
  // ── 必需字段 ──
  "model":          "string",       // 模型 ID，如 "glm-5.1"、"claude-sonnet-4-6"
  "max_tokens":     8000,           // 最大输出 token 数（Anthropic 要求必填，OpenAI 可选）
  "messages":       [...],          // 对话历史数组（必需）

  // ── 可选字段 ──
  "system":         "string",       // 系统提示词（不在 messages 里，单独传）
  "tools":          [...],          // 工具定义数组
  "temperature":    0.0,            // 生成随机性，0（确定）到 1（随机）
  "top_p":          0.9,            // 核采样概率
  "stop_sequences": ["\n\n"],       // 自定义停止序列
  "stream":         false,          // 是否流式返回
  "tool_choice":    {...},          // 工具选择策略
  "metadata":       {...}           // 附加元数据
}
```

### 5.2 各字段详细说明

#### model（必需）

要调用的模型 ID。在智谱兼容端点中使用智谱的模型名：

```json
"model": "glm-5.1"
```

#### max_tokens（必需）

限制模型回复的最大 token 数。如果模型在达到上限前没有自然结束，`stop_reason` 会是 `"max_tokens"`。

```json
"max_tokens": 8000
```

#### system（可选）

系统提示词，定义模型的角色和行为规范。Anthropic 格式中 `system` 是请求体的**顶级字段**，不放在 `messages` 数组里。

```json
"system": "You are a coding agent at /home/user/project. Use bash to solve tasks. Act, don't explain."
```

> **与 OpenAI 的区别**: OpenAI 把系统提示词放在 messages 中 `{"role": "system", "content": "..."}` 里。

#### messages（必需）

对话历史数组，由多轮消息组成。每条消息有 `role` 和 `content` 两个字段。

##### role 类型

| role          | 说明                | 谁产生的                        |
| ------------- | ------------------- | ------------------------------- |
| `"user"`      | 用户/人类发送的消息 | 用户输入，或 Agent 回传工具结果 |
| `"assistant"` | 模型的回复          | API 响应后追加到历史中          |

##### content 类型

`content` 可以是简单字符串，也可以是内容块数组：

```json
// 简单字符串（纯文本对话）
{"role": "user", "content": "帮我列出当前目录的文件"}

// 内容块数组（包含工具结果回传）
{"role": "user", "content": [
  {"type": "tool_result", "tool_use_id": "call_xxx", "content": "file1.py\nfile2.py"}
]}
```

#### tools（可选）

告诉模型"你可以调用哪些工具"。每个工具定义包含名称、描述和参数 Schema。

```json
"tools": [
  {
    "name":         "bash",                      // 工具名称
    "description":  "Run a shell command.",       // 告诉模型这个工具做什么
    "input_schema": {                             // 参数的 JSON Schema
      "type":       "object",
      "properties": {
        "command": {"type": "string", "description": "The shell command to run"}
      },
      "required":   ["command"]
    }
  }
]
```

> **与 OpenAI 的区别**: Anthropic 用 `input_schema`，OpenAI 用 `parameters` 并嵌套在 `{"type": "function", "function": {...}}` 中。

#### tool_choice（可选）

控制模型是否必须调用工具：

```json
// 自动决定（默认）
"tool_choice": {"type": "auto"}

// 必须调用某个指定工具
"tool_choice": {"type": "tool", "name": "bash"}

// 必须调用任意工具（但不能是纯文本回复）
"tool_choice": {"type": "any"}
```

### 5.3 完整入参示例：一次 Agent 调用

以下是一个真实的入参示例，对应 s01 中 `client.messages.create()` 的调用：

```json
POST https://open.bigmodel.cn/api/anthropic/v1/messages
Headers:
  Content-Type: application/json
  x-api-key: <your-api-key>
  anthropic-version: 2023-06-01

Body:
{
  "model": "glm-5.1",
  "max_tokens": 8000,
  "system": "You are a coding agent at /home/user/project. Use bash to solve tasks. Act, don't explain.",
  "messages": [
    {
      "role": "user",
      "content": "当前目录下有哪些 Python 文件？"
    }
  ],
  "tools": [
    {
      "name": "bash",
      "description": "Run a shell command.",
      "input_schema": {
        "type": "object",
        "properties": {
          "command": {
            "type": "string"
          }
        },
        "required": ["command"]
      }
    }
  ]
}
```

### 5.4 完整入参示例：多轮对话（含工具结果回传）

当 Agent 已经执行了工具，需要把结果喂回模型时，`messages` 数组会变长：

```json
{
  "model": "glm-5.1",
  "max_tokens": 8000,
  "system": "You are a coding agent at /home/user/project. Use bash to solve tasks. Act, don't explain.",
  "messages": [
    // 第 1 轮：用户提问
    {
      "role": "user",
      "content": "当前目录下有哪些 Python 文件？"
    },
    // 第 1 轮：模型回复（包含文本 + 工具调用）
    {
      "role": "assistant",
      "content": [
        { "type": "text", "text": "我来查看一下当前目录：" },
        {
          "type": "tool_use",
          "id": "call_abc123",
          "name": "bash",
          "input": { "command": "ls *.py" }
        }
      ]
    },
    // 第 1 轮：Agent 把工具执行结果回传
    {
      "role": "user",
      "content": [
        {
          "type": "tool_result",
          "tool_use_id": "call_abc123",
          "content": "hello.py\nagent.py\nutils.py"
        }
      ]
    }
  ],
  "tools": [
    {
      "name": "bash",
      "description": "Run a shell command.",
      "input_schema": {
        "type": "object",
        "properties": {
          "command": { "type": "string" }
        },
        "required": ["command"]
      }
    }
  ]
}
```

消息顺序：`user` → `assistant` → `user`（工具结果）→ 模型再次回复...如此循环。

### 5.5 入参在 s01 代码中的对应

```python
# s01_agent_loop/code.py

# model 和 max_tokens
response = client.messages.create(
    model=MODEL,              # → "model": "glm-5.1"
    system=SYSTEM,            # → "system": "You are a coding agent..."
    messages=messages,        # → "messages": [...]
    tools=TOOLS,              # → "tools": [...]
    max_tokens=8000,          # → "max_tokens": 8000
)

# messages 的构造过程：
# 1. 用户输入 → history.append({"role": "user", "content": query})
# 2. 模型回复 → messages.append({"role": "assistant", "content": response.content})
# 3. 工具结果 → messages.append({"role": "user", "content": [{"type": "tool_result", ...}]})
```

---

## 六、数据流全景图

```
用户输入
    │
    ▼
┌─────────────────────────────────────────────┐
│  Request: client.messages.create(...)        │
│  ┌─────────────────────────────────────────┐ │
│  │ model, system, messages, tools          │ │
│  └─────────────────────────────────────────┘ │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  Response                                    │
│  ┌─────────────────────────────────────────┐ │
│  │ id:        "msg_xxx"                    │ │
│  │ role:      "assistant"                  │ │
│  │ stop_reason: "tool_use" | "end_turn"    │ │
│  │ content: [                              │ │
│  │   { type: "text", text: "..." },        │ │
│  │   { type: "tool_use", name, input, id } │ │
│  │ ]                                       │ │
│  │ usage: { input_tokens, output_tokens }  │ │
│  └─────────────────────────────────────────┘ │
└──────────────────┬──────────────────────────┘
                   │
          stop_reason == "tool_use" ?
                   │
         ┌──── yes ──┴── no ────┐
         │                      │
         ▼                      ▼
  执行工具，构造          输出文本，循环结束
  tool_result 回传
         │
         ▼
  追加到 messages，继续循环
```

---

## 参考来源

- [Anthropic Messages API 官方文档](https://docs.anthropic.com/en/api/messages)
- [Anthropic Tool Use 文档](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- 本项目 s01_agent_loop/code.py
