"""智谱模型 API 连接验证 - 交互式控制台对话

用法:
    python tests/test_llm_connection.py

命令:
    /help    - 显示帮助
    /status  - 显示连接状态
    /clear   - 清空对话历史
    /model   - 显示当前模型信息
    /quit    - 退出程序
"""

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def load_config() -> dict:
    """加载 .env 配置"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    api_key = os.getenv("ZHIPU_API_KEY", "")
    base_url = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
    model = os.getenv("ZHIPU_MODEL", "glm-4")

    missing = []
    if not api_key:
        missing.append("ZHIPU_API_KEY")
    if missing:
        print(f"[ERROR] 缺少环境变量: {', '.join(missing)}")
        print(f"请在 {env_path} 中配置")
        sys.exit(1)

    return {"api_key": api_key, "base_url": base_url, "model": model}


def create_client(config: dict) -> OpenAI:
    """创建 OpenAI 兼容客户端"""
    return OpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"],
        timeout=60.0,
    )


def test_connection(client: OpenAI, model: str) -> bool:
    """发送简单请求验证连接"""
    print(f"\n[TEST] 正在连接智谱 API...")
    print(f"  Base URL : {client.base_url}")
    print(f"  Model    : {model}")

    try:
        start = time.time()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "你好，请用一句话介绍你自己。"}],
            max_tokens=100,
        )
        elapsed = time.time() - start
        content = response.choices[0].message.content
        tokens_in = response.usage.prompt_tokens
        tokens_out = response.usage.completion_tokens

        print(f"\n[OK] 连接成功! ({elapsed:.2f}s)")
        print(f"  Input tokens  : {tokens_in}")
        print(f"  Output tokens : {tokens_out}")
        print(f"  Response      : {content}")
        return True

    except Exception as e:
        print(f"\n[FAIL] 连接失败: {e}")
        return False


def chat_loop(client: OpenAI, model: str) -> None:
    """交互式对话循环"""
    history: list[dict] = []
    total_in = 0
    total_out = 0
    turn = 0

    print("\n" + "=" * 60)
    print("  智谱模型交互式对话 (输入 /quit 退出)")
    print("=" * 60)

    while True:
        try:
            user_input = input("\n[You] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n[BYE]")
            break

        if not user_input:
            continue

        # 内置命令
        cmd = user_input.lower()
        if cmd == "/quit":
            print(f"\n[STATS] Total turns={turn}, "
                  f"tokens_in={total_in}, tokens_out={total_out}")
            print("[BYE]")
            break
        elif cmd == "/help":
            print("  /help   - 显示帮助")
            print("  /status - 显示连接状态")
            print("  /clear  - 清空对话历史")
            print("  /model  - 显示当前模型")
            print("  /quit   - 退出程序")
            continue
        elif cmd == "/status":
            print(f"  Base URL     : {client.base_url}")
            print(f"  Model        : {model}")
            print(f"  History msgs : {len(history)}")
            print(f"  Total turns  : {turn}")
            print(f"  Total tokens : in={total_in}, out={total_out}")
            continue
        elif cmd == "/clear":
            history.clear()
            turn = 0
            total_in = 0
            total_out = 0
            print("[CLEARED] 对话历史已清空")
            continue
        elif cmd == "/model":
            print(f"  Model    : {model}")
            print(f"  Base URL : {client.base_url}")
            continue

        # 发送消息
        history.append({"role": "user", "content": user_input})

        try:
            start = time.time()
            response = client.chat.completions.create(
                model=model,
                messages=history,
                temperature=0.7,
            )
            elapsed = time.time() - start

            content = response.choices[0].message.content
            tokens_in = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens
            total_in += tokens_in
            total_out += tokens_out
            turn += 1

            history.append({"role": "assistant", "content": content})

            print(f"\n[AI] {content}")
            print(f"    --- {elapsed:.2f}s | "
                  f"tokens: +{tokens_in}/{tokens_out} | "
                  f"turn #{turn} ---")

        except Exception as e:
            print(f"\n[ERROR] {e}")
            # 移除失败的用户消息，避免历史污染
            history.pop()


def main() -> None:
    config = load_config()
    client = create_client(config)

    if not test_connection(client, config["model"]):
        print("\n连接测试失败，请检查 .env 配置和网络连接。")
        sys.exit(1)

    chat_loop(client, config["model"])


if __name__ == "__main__":
    main()
