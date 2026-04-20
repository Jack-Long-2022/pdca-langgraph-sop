"""LLM调用封装模块

支持多模型调用、错误重试和响应格式化
"""

import os
import time
from abc import ABC, abstractmethod
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
    """错误重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 延迟倍数
    """
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


class BaseLLM(ABC):
    """LLM基类"""
    
    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本
        
        Args:
            prompt: 输入提示
            **kwargs: 其他参数
        
        Returns:
            生成的文本
        """
        pass
    
    @abstractmethod
    def generate_messages(self, messages: list[Dict[str, str]], **kwargs) -> str:
        """生成文本（消息格式）
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            **kwargs: 其他参数
        
        Returns:
            生成的文本
        """
        pass


class OpenAILLM(BaseLLM):
    """OpenAI LLM封装"""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client = None
    
    @property
    def client(self):
        """懒加载OpenAI客户端"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key, timeout=self.timeout)
            except ImportError:
                raise ModelUnavailableError("请安装 openai 包: pip install openai")
        return self._client
    
    @retry_on_error(max_retries=3, delay=1.0)
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
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
                raise RateLimitError(f"OpenAI API限流: {e}")
            raise LLMError(f"OpenAI生成失败: {e}")
    
    @retry_on_error(max_retries=3, delay=1.0)
    def generate_messages(self, messages: list[Dict[str, str]], **kwargs) -> str:
        """生成文本（消息格式）"""
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
                raise RateLimitError(f"OpenAI API限流: {e}")
            raise LLMError(f"OpenAI生成失败: {e}")


class LLMManager:
    """LLM管理器，支持多模型"""
    
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
        self._llms: Dict[str, BaseLLM] = {}
        self._default_model: Optional[str] = None
    
    def register_llm(self, name: str, llm: BaseLLM) -> None:
        """注册LLM实例
        
        Args:
            name: LLM名称
            llm: LLM实例
        """
        self._llms[name] = llm
        if self._default_model is None:
            self._default_model = name
        logger.info("llm_registered", name=name, model=llm.model)
    
    def get_llm(self, name: Optional[str] = None) -> BaseLLM:
        """获取LLM实例
        
        Args:
            name: LLM名称，如果为None则使用默认LLM
        
        Returns:
            LLM实例
        """
        if name is None:
            name = self._default_model
        if name not in self._llms:
            raise ValueError(f"未注册的LLM: {name}")
        return self._llms[name]
    
    def set_default(self, name: str) -> None:
        """设置默认LLM"""
        if name not in self._llms:
            raise ValueError(f"未注册的LLM: {name}")
        self._default_model = name
    
    def generate(self, prompt: str, model_name: Optional[str] = None, **kwargs) -> str:
        """生成文本"""
        return self.get_llm(model_name).generate(prompt, **kwargs)
    
    def generate_messages(
        self,
        messages: list[Dict[str, str]],
        model_name: Optional[str] = None,
        **kwargs
    ) -> str:
        """生成文本（消息格式）"""
        return self.get_llm(model_name).generate_messages(messages, **kwargs)


# 全局LLM管理器
_llm_manager: Optional[LLMManager] = None

def get_llm_manager() -> LLMManager:
    """获取全局LLM管理器"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager

def setup_llm(
    name: str = "default",
    provider: str = "openai",
    model: str = "gpt-4",
    api_key: Optional[str] = None,
    **kwargs
) -> BaseLLM:
    """快速设置LLM
    
    Args:
        name: LLM名称
        provider: 提供商 (openai)
        model: 模型名称
        api_key: API密钥
        **kwargs: 其他参数
    
    Returns:
        LLM实例
    """
    manager = get_llm_manager()
    
    if provider == "openai":
        llm = OpenAILLM(model=model, api_key=api_key, **kwargs)
    else:
        raise ValueError(f"不支持的LLM提供商: {provider}")
    
    manager.register_llm(name, llm)
    return llm
