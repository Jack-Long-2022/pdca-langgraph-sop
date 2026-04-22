"""LLM调用封装模块

支持多模型调用、错误重试和响应格式化
"""

import os
import time
from typing import Any, Dict, Optional, Callable
from functools import wraps
from pdca.core.logger import get_logger

logger = get_logger(__name__)


class LLMError(Exception):
    """LLM调用异常"""
    pass


class RateLimitError(LLMError):
    """限流异常"""
    pass


class ModelUnavailableError(LLMError):
    """模型不可用异常"""
    pass


def retry_on_error(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """错误重试装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RateLimitError as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            "rate_limit_retry",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            delay=current_delay
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error("rate_limit_max_retries", attempts=attempt + 1)
                        raise
                except Exception as e:
                    last_exception = e
                    logger.error("llm_call_error", error=str(e), attempt=attempt + 1)
                    raise

            raise last_exception
        return wrapper
    return decorator


class OpenAILLM:
    """OpenAI兼容API的LLM封装（支持Zhipu、MiniMax等）"""

    def __init__(
        self,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                client_kwargs = {"api_key": self.api_key, "timeout": self.timeout}
                if self.base_url:
                    client_kwargs["base_url"] = self.base_url
                self._client = OpenAI(**client_kwargs)
            except ImportError:
                raise ModelUnavailableError("请安装 openai 包: pip install openai")
        return self._client

    @retry_on_error(max_retries=3, delay=1.0)
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本（纯user消息）"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens)
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("openai_generate_error", error=str(e))
            if "rate" in str(e).lower():
                raise RateLimitError(f"API限流: {e}")
            raise LLMError(f"生成失败: {e}")

    @retry_on_error(max_retries=3, delay=1.0)
    def generate_messages(self, messages: list[Dict[str, str]], **kwargs) -> str:
        """生成文本（消息格式，支持system/user/assistant）"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens)
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("openai_generate_messages_error", error=str(e))
            if "rate" in str(e).lower():
                raise RateLimitError(f"API限流: {e}")
            raise LLMError(f"生成失败: {e}")


# 向后兼容别名（Phase 3-7 完成后移除）
BaseLLM = OpenAILLM


class LLMManager:
    """LLM管理器，支持多模型注册和角色路由"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._llms: Dict[str, OpenAILLM] = {}
        self._default_model: Optional[str] = None

    def register_llm(self, name: str, llm: OpenAILLM) -> None:
        self._llms[name] = llm
        if self._default_model is None:
            self._default_model = name
        logger.info("llm_registered", name=name, model=llm.model)

    def get_llm(self, name: Optional[str] = None) -> OpenAILLM:
        if name is None:
            name = self._default_model
        if name not in self._llms:
            raise ValueError(f"未注册的LLM: {name}，已注册: {list(self._llms.keys())}")
        return self._llms[name]

    def set_default(self, name: str) -> None:
        if name not in self._llms:
            raise ValueError(f"未注册的LLM: {name}")
        self._default_model = name


# 全局LLM管理器
_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager


def get_llm_for_task(task: str) -> OpenAILLM:
    """按任务角色选择模型

    Planner任务(extract/config/review)用强模型，
    Executor任务(code/test/report)用轻模型。
    """
    from pdca.core.prompts import PLANNER_TASKS
    role = "planner" if task in PLANNER_TASKS else "executor"
    return get_llm_manager().get_llm(role)


def setup_llm(
    name: str = "default",
    provider: str = "openai",
    model: str = "gpt-4",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs
) -> OpenAILLM:
    """快速设置LLM

    Args:
        name: LLM注册名称（如 "planner", "executor"）
        provider: 提供商 (openai, zhipu, minimax)
        model: 模型名称
        api_key: API密钥
        base_url: API基础URL
    """
    manager = get_llm_manager()

    if provider == "zhipu":
        llm = OpenAILLM(
            model=model,
            api_key=api_key or os.getenv("ZHIPU_API_KEY"),
            base_url=base_url or os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"),
            **kwargs,
        )
    elif provider == "minimax":
        llm = OpenAILLM(
            model=model,
            api_key=api_key or os.getenv("MINIMAX_API_KEY"),
            base_url=base_url or os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1"),
            **kwargs,
        )
    elif provider == "openai":
        llm = OpenAILLM(model=model, api_key=api_key, base_url=base_url, **kwargs)
    else:
        raise ValueError(f"不支持的LLM提供商: {provider}")

    manager.register_llm(name, llm)
    return llm
