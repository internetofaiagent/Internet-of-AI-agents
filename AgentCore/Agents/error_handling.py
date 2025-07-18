#!/usr/bin/env python3
"""
错误处理和重试机制
"""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional, Type
from functools import wraps
from datetime import datetime, timedelta
import traceback

class RetryConfig:
    """重试配置"""
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

class PaymentError(Exception):
    """支付相关错误"""
    def __init__(self, message: str, error_code: str = None, retryable: bool = False):
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable

class AmazonAPIError(Exception):
    """Amazon API相关错误"""
    def __init__(self, message: str, error_code: str = None, retryable: bool = False):
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable

class NetworkError(Exception):
    """网络相关错误"""
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable

class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 错误分类映射
        self.retryable_errors = {
            # 网络错误
            'ConnectionError',
            'TimeoutError',
            'HTTPError',
            
            # 支付宝错误
            'SYSTEM_ERROR',
            'UNKNOW_ERROR',
            'ACQ.SYSTEM_ERROR',
            
            # Amazon错误
            'RequestThrottled',
            'ServiceUnavailable',
            'InternalFailure'
        }
        
        # 不可重试的错误
        self.non_retryable_errors = {
            # 支付宝错误
            'ACQ.INVALID_PARAMETER',
            'ACQ.ACCESS_FORBIDDEN',
            'ACQ.TRADE_NOT_EXIST',
            
            # Amazon错误
            'InvalidParameterValue',
            'AccessDenied',
            'InvalidAccessKeyId'
        }
    
    def is_retryable(self, error: Exception) -> bool:
        """判断错误是否可重试"""
        # 检查自定义错误类型
        if hasattr(error, 'retryable'):
            return error.retryable
        
        # 检查错误代码
        error_code = getattr(error, 'error_code', None) or str(type(error).__name__)
        
        if error_code in self.non_retryable_errors:
            return False
        
        if error_code in self.retryable_errors:
            return True
        
        # 默认网络相关错误可重试
        return isinstance(error, (ConnectionError, TimeoutError))
    
    def categorize_error(self, error: Exception) -> Dict[str, Any]:
        """错误分类"""
        error_type = type(error).__name__
        error_message = str(error)
        error_code = getattr(error, 'error_code', None)
        
        category = "unknown"
        severity = "medium"
        
        # 支付错误
        if isinstance(error, PaymentError):
            category = "payment"
            severity = "high" if not error.retryable else "medium"
        
        # Amazon API错误
        elif isinstance(error, AmazonAPIError):
            category = "amazon_api"
            severity = "high" if not error.retryable else "medium"
        
        # 网络错误
        elif isinstance(error, (ConnectionError, TimeoutError, NetworkError)):
            category = "network"
            severity = "low"
        
        # 系统错误
        elif isinstance(error, (ValueError, TypeError, KeyError)):
            category = "system"
            severity = "high"
        
        return {
            "type": error_type,
            "message": error_message,
            "code": error_code,
            "category": category,
            "severity": severity,
            "retryable": self.is_retryable(error),
            "timestamp": datetime.now().isoformat()
        }

def retry_with_backoff(
    config: RetryConfig = None,
    exceptions: tuple = (Exception,),
    on_retry: Callable = None
):
    """重试装饰器"""
    if config is None:
        config = RetryConfig()
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            error_handler = ErrorHandler()
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                
                except exceptions as e:
                    last_exception = e
                    error_info = error_handler.categorize_error(e)
                    
                    # 记录错误
                    logging.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed: {error_info['message']}"
                    )
                    
                    # 检查是否可重试
                    if not error_handler.is_retryable(e):
                        logging.error(f"Non-retryable error: {error_info['message']}")
                        raise e
                    
                    # 最后一次尝试失败
                    if attempt == config.max_attempts - 1:
                        logging.error(f"All {config.max_attempts} attempts failed")
                        raise e
                    
                    # 计算延迟时间
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random() * 0.5)
                    
                    # 调用重试回调
                    if on_retry:
                        await on_retry(attempt + 1, e, delay)
                    
                    # 等待后重试
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            error_handler = ErrorHandler()
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                
                except exceptions as e:
                    last_exception = e
                    error_info = error_handler.categorize_error(e)
                    
                    logging.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed: {error_info['message']}"
                    )
                    
                    if not error_handler.is_retryable(e):
                        logging.error(f"Non-retryable error: {error_info['message']}")
                        raise e
                    
                    if attempt == config.max_attempts - 1:
                        logging.error(f"All {config.max_attempts} attempts failed")
                        raise e
                    
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random() * 0.5)
                    
                    import time
                    time.sleep(delay)
            
            raise last_exception
        
        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

class CircuitBreaker:
    """熔断器"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if self._should_attempt_reset():
                    self.state = "HALF_OPEN"
                else:
                    raise Exception("Circuit breaker is OPEN")
            
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            
            except self.expected_exception as e:
                self._on_failure()
                raise e
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if self._should_attempt_reset():
                    self.state = "HALF_OPEN"
                else:
                    raise Exception("Circuit breaker is OPEN")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            
            except self.expected_exception as e:
                self._on_failure()
                raise e
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置"""
        return (
            self.last_failure_time and
            datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout)
        )
    
    def _on_success(self):
        """成功时的处理"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        """失败时的处理"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO)
    
    # 重试配置
    retry_config = RetryConfig(max_attempts=3, base_delay=1.0)
    
    @retry_with_backoff(config=retry_config, exceptions=(PaymentError, NetworkError))
    async def mock_payment_call():
        """模拟支付调用"""
        import random
        if random.random() < 0.7:  # 70% 失败率
            raise PaymentError("支付服务暂时不可用", "SYSTEM_ERROR", retryable=True)
        return {"success": True, "order_id": "12345"}
    
    @CircuitBreaker(failure_threshold=3, recovery_timeout=30)
    async def mock_amazon_call():
        """模拟Amazon调用"""
        import random
        if random.random() < 0.8:  # 80% 失败率
            raise AmazonAPIError("Amazon API限流", "RequestThrottled", retryable=True)
        return {"success": True, "products": []}
    
    async def test_error_handling():
        """测试错误处理"""
        try:
            result = await mock_payment_call()
            print(f"支付成功: {result}")
        except Exception as e:
            print(f"支付失败: {e}")
        
        try:
            result = await mock_amazon_call()
            print(f"Amazon调用成功: {result}")
        except Exception as e:
            print(f"Amazon调用失败: {e}")
    
    # 运行测试
    asyncio.run(test_error_handling())
