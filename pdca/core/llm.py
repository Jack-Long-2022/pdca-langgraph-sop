"""LLM调用封装模块

支持多模型调用、错误重试和响应格式化
"""

import os
import random
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


class TimeoutError(LLMError):
    """请求超时异常"""
    pass


class ModelUnavailableError(LLMError):
    """模型不可用异常"""
    pass


# 可重试的错误类型
_RETRYABLE_ERRORS = (RateLimitError, TimeoutError)


def _is_retryable_exception(exc: Exception) -> bool:
    """判断异常是否值得重试"""
    if isinstance(exc, _RETRYABLE_ERRORS):
        return True
    # 检查错误信息中的可重试关键词
    msg = str(exc).lower()
    retryable_keywords = [
        "timed out", "timeout",
        "529", "overloaded",
        "rate", "limit",
        "too many requests", "429",
        "connection", "reset", "unavailable",
    ]
    return any(kw in msg for kw in retryable_keywords)


def retry_on_error(max_retries: int = 3, delay: float = 2.0, backoff: float = 2.0):
    """错误重试装饰器

    对可重试错误（限流、超时、过载等）自动重试，带指数退避和随机抖动。
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if _is_retryable_exception(e) and attempt < max_retries:
                        # 添加随机抖动，避免多请求同时重试
                        jitter = random.uniform(0.5, 1.5)
                        actual_delay = current_delay * jitter
                        logger.warning(
                            "llm_retryable_error",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            delay=round(actual_delay, 2),
                            error=str(e)[:200],
                        )
                        time.sleep(actual_delay)
                        current_delay *= backoff
                    else:
                        if attempt >= max_retries:
                            logger.error(
                                "llm_max_retries_exceeded",
                                attempts=attempt + 1,
                                error=str(e)[:200],
                            )
                        else:
                            logger.error(
                                "llm_non_retryable_error",
                                error=str(e)[:200],
                                attempt=attempt + 1,
                            )
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

    @retry_on_error(max_retries=3, delay=2.0)
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
            raise self._classify_error(e)

    @retry_on_error(max_retries=3, delay=2.0)
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
            raise self._classify_error(e)

    @staticmethod
    def _classify_error(e: Exception) -> LLMError:
        """将原始异常分类为具体的 LLM 错误类型"""
        msg = str(e).lower()
        if any(kw in msg for kw in ("rate", "limit", "429", "too many")):
            return RateLimitError(f"API限流: {e}")
        if any(kw in msg for kw in ("timed out", "timeout")):
            return TimeoutError(f"请求超时: {e}")
        if any(kw in msg for kw in ("529", "overloaded")):
            return RateLimitError(f"API过载: {e}")
        return LLMError(f"生成失败: {e}")


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
            timeout=kwargs.pop("timeout", 120.0),
            **kwargs,
        )
    elif provider == "minimax":
        llm = OpenAILLM(
            model=model,
            api_key=api_key or os.getenv("MINIMAX_API_KEY"),
            base_url=base_url or os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1"),
            timeout=kwargs.pop("timeout", 180.0),
            **kwargs,
        )
    elif provider == "openai":
        llm = OpenAILLM(model=model, api_key=api_key, base_url=base_url, **kwargs)
    else:
        raise ValueError(f"不支持的LLM提供商: {provider}")

    manager.register_llm(name, llm)
    return llm
