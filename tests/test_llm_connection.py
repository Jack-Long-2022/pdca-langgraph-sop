"""LLM API 连接验证 - 支持智谱 & MiniMax 双模型

用法:
    python tests/test_llm_connection.py              # 测试全部
    python tests/test_llm_connection.py --zhipu      # 仅测试智谱
    python tests/test_llm_connection.py --minimax    # 仅测试 MiniMax

交互命令:
    /help    - 显示帮助
    /status  - 显示连接状态
    /clear   - 清空对话历史
    /model   - 切换/显示当前模型
    /quit    - 退出程序
"""

import os
import sys
import time
import argparse
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def load_env():
    """加载 .env 配置"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)


def get_provider_config(provider: str) -> dict:
    """获取指定 provider 的配置"""
    if provider == "zhipu":
        api_key = os.getenv("ZHIPU_API_KEY", "")
        base_url = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
        model = os.getenv("ZHIPU_MODEL", "glm-4.7")
        missing = []
        if not api_key:
            missing.append("ZHIPU_API_KEY")
    elif provider == "minimax":
        api_key = os.getenv("MINIMAX_API_KEY", "")
        base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
        model = os.getenv("MINIMAX_MODEL", "MiniMax-Text-01")
        missing = []
        if not api_key:
            missing.append("MINIMAX_API_KEY")
    else:
        raise ValueError(f"未知 provider: {provider}")

    return {
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "missing": missing,
    }


def create_client(config: dict) -> OpenAI:
    """创建 OpenAI 兼容客户端"""
    return OpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"],
        timeout=60.0,
    )


def test_connection(client: OpenAI, config: dict) -> bool:
    """发送简单请求验证连接"""
    provider = config["provider"]
    model = config["model"]
    label = provider.upper()

    print(f"\n[TEST] 正在连接 {label} API...")
    print(f"  Base URL : {client.base_url}")
    print(f"  Model    : {model}")

    if config["missing"]:
        print(f"[SKIP] {label} 缺少环境变量: {', '.join(config['missing'])}")
        return False

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

        print(f"\n[OK] {label} 连接成功! ({elapsed:.2f}s)")
        print(f"  Input tokens  : {tokens_in}")
        print(f"  Output tokens : {tokens_out}")
        print(f"  Response      : {content}")
        return True

    except Exception as e:
        print(f"\n[FAIL] {label} 连接失败: {e}")
        return False


def test_all(providers: list[str]) -> dict[str, bool]:
    """测试指定 providers 的连接"""
    results = {}
    for provider in providers:
        config = get_provider_config(provider)
        client = create_client(config)
        results[provider] = test_connection(client, config)
    return results


def chat_loop(available: dict[str, tuple[OpenAI, dict]]) -> None:
    """交互式对话循环，支持多模型切换"""
    providers = list(available.keys())
    current = providers[0]

    histories: dict[str, list[dict]] = {p: [] for p in providers}
    total_in: dict[str, int] = {p: 0 for p in providers}
    total_out: dict[str, int] = {p: 0 for p in providers}
    turns: dict[str, int] = {p: 0 for p in providers}

    labels = " | ".join(f"{p.upper()}({i+1})" for i, p in enumerate(providers))

    print("\n" + "=" * 60)
    print(f"  LLM 交互式对话  可用模型: {labels}")
    print("  /model <序号> 切换模型 | /quit 退出")
    print("=" * 60)

    while True:
        try:
            prompt = f"\n[{current.upper()}] > "
            user_input = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n[BYE]")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd == "/quit":
            print(f"\n[STATS]")
            for p in providers:
                print(f"  {p.upper()}: turns={turns[p]}, "
                      f"tokens_in={total_in[p]}, tokens_out={total_out[p]}")
            print("[BYE]")
            break
        elif cmd == "/help":
            print("  /help           - 显示帮助")
            print("  /status         - 显示连接状态")
            print("  /clear          - 清空当前模型对话历史")
            print("  /model [序号]   - 切换模型或显示当前模型")
            print("  /quit           - 退出程序")
            continue
        elif cmd == "/status":
            for p in providers:
                client, cfg = available[p]
                active = " <-- 当前" if p == current else ""
                print(f"  {p.upper()}{active}")
                print(f"    Base URL : {client.base_url}")
                print(f"    Model    : {cfg['model']}")
                print(f"    History  : {len(histories[p])} msgs")
                print(f"    Turns    : {turns[p]}")
                print(f"    Tokens   : in={total_in[p]}, out={total_out[p]}")
            continue
        elif cmd == "/clear":
            histories[current].clear()
            turns[current] = 0
            total_in[current] = 0
            total_out[current] = 0
            print(f"[CLEARED] {current.upper()} 对话历史已清空")
            continue
        elif cmd.startswith("/model"):
            parts = user_input.split(maxsplit=1)
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(providers):
                    current = providers[idx]
                    _, cfg = available[current]
                    print(f"  已切换到 {current.upper()} (model={cfg['model']})")
                else:
                    print(f"  无效序号，可选: 1-{len(providers)}")
            else:
                _, cfg = available[current]
                print(f"  当前: {current.upper()} (model={cfg['model']})")
                print(f"  可用:")
                for i, p in enumerate(providers):
                    _, c = available[p]
                    print(f"    {i+1}. {p.upper()} - {c['model']}")
            continue

        # 发送消息
        history = histories[current]
        history.append({"role": "user", "content": user_input})

        client, cfg = available[current]
        model = cfg["model"]

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
            total_in[current] += tokens_in
            total_out[current] += tokens_out
            turns[current] += 1

            history.append({"role": "assistant", "content": content})

            print(f"\n[AI] {content}")
            print(f"    --- {elapsed:.2f}s | "
                  f"tokens: +{tokens_in}/{tokens_out} | "
                  f"{current.upper()} turn #{turns[current]} ---")

        except Exception as e:
            print(f"\n[ERROR] {e}")
            history.pop()


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM 连接验证")
    parser.add_argument("--zhipu", action="store_true", help="仅测试智谱")
    parser.add_argument("--minimax", action="store_true", help="仅测试 MiniMax")
    args = parser.parse_args()

    load_env()

    # 确定要测试的 providers
    providers = []
    if args.zhipu or args.minimax:
        if args.zhipu:
            providers.append("zhipu")
        if args.minimax:
            providers.append("minimax")
    else:
        providers = ["zhipu", "minimax"]

    print("=" * 60)
    print("  LLM API 连接验证")
    print("=" * 60)

    # 连接测试
    results = test_all(providers)

    print("\n" + "-" * 60)
    print("  连接测试结果:")
    for p, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"    {p.upper():10s} {status}")
    print("-" * 60)

    passed = {p for p, ok in results.items() if ok}
    if not passed:
        print("\n所有连接均失败，请检查 .env 配置和网络连接。")
        sys.exit(1)

    # 进入交互模式（仅使用连接成功的模型）
    available = {}
    for p in passed:
        config = get_provider_config(p)
        available[p] = (create_client(config), config)

    chat_loop(available)


if __name__ == "__main__":
    main()
