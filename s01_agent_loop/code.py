#!/usr/bin/env python3
"""
s01_agent_loop.py - Agent 循环

AI 编程 Agent 的全部秘密就在一个模式中：

    while stop_reason == "tool_use":
        response = LLM(messages, tools)
        执行工具
        追加结果

    +----------+      +-------+      +---------+
    |   用户   | ---> |  LLM  | ---> |  工具   |
    |   提示   |      |       |      |  执行   |
    +----------+      +---+---+      +----+----+
                          ^               |
                          |   tool_result |
                          +---------------+
                          （循环继续）

核心循环：将工具执行结果反馈给模型，直到模型决定停止。
生产级 Agent 在此基础上叠加策略、钩子和生命周期控制。

用法：
    pip install anthropic python-dotenv
    ANTHROPIC_API_KEY=... python s01_agent_loop/code.py
"""

import os
import subprocess

try:
    import readline
    # macOS 的 libedit 在处理中文输入时有退格问题，这四行修复它
    readline.parse_and_bind('set bind-tty-special-chars off')
    readline.parse_and_bind('set input-meta on')
    readline.parse_and_bind('set output-meta on')
    readline.parse_and_bind('set convert-meta off')
except ImportError:
    pass

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]

# 系统级提示词
SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

# ── 工具定义：仅 bash ────────────────────────────
TOOLS = [{
    "name": "bash",
    "description": "Run a shell command.",
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
}]


# ── 工具执行 ────────────────────────────────────────
def run_bash(command: str) -> str:
    # 安全检查：禁止执行极其危险的命令
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"

    # 执行命令，捕获输出和错误，限制输出长度和执行时间
    try:
        r = subprocess.run(command, shell=True, cwd=os.getcwd(),
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"

    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except (FileNotFoundError, OSError) as e:
        return f"Error: {e}"


# ── 核心模式：循环调用工具，直到模型停止 ──
def agent_loop(messages: list):
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )

        # 追加助手回复
        messages.append({"role": "assistant", "content": response.content})

        # 如果模型没有调用工具，流程结束
        if response.stop_reason != "tool_use":
            return

        # 执行每个工具调用，收集结果
        results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"\033[33m$ {block.input['command']}\033[0m")
                output = run_bash(block.input["command"])
                print(output[:200])
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })

        # 将工具结果反馈给模型，继续循环
        messages.append({"role": "user", "content": results})


# ── 入口 ──────────────────────────────────────────
if __name__ == "__main__":
    print("s01: Agent Loop")
    print("输入问题，回车发送。输入 q 退出。\n")

    history = []
    while True:
        try:
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break

        # EOF（Ctrl+D）或 Ctrl+C 退出
        if query.strip().lower() in ("q", "exit", ""):
            break
        # 将用户输入追加到对话历史，并调用 Agent 循环
        history.append({"role": "user", "content": query})
        agent_loop(history)

        # 打印模型的最终文本回复
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if getattr(block, "type", None) == "text":
                    print(block.text)
        print()
