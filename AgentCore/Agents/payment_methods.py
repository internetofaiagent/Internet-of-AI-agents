#!/usr/bin/env python3
"""
支付方式枚举和配置

定义支持的支付方式类型，以及支付方式与支付 Agent 的映射关系。
"""

from enum import Enum
from typing import Dict, Optional, Any
import os


class PaymentMethod(Enum):
    """支付方式枚举"""
    ALIPAY = "alipay"              # 支付宝
    WECHAT_PAY = "wechat_pay"      # 微信支付
    PAYPAL = "paypal"              # PayPal
    CRYPTO_STABLECOIN = "crypto_stablecoin"  # 加密货币稳定币（USDC/USDT等）
    
    @classmethod
    def from_string(cls, value: str) -> Optional['PaymentMethod']:
        """从字符串转换为支付方式枚举"""
        value_lower = value.lower().replace("-", "_").replace(" ", "_")
        for method in cls:
            if method.value == value_lower:
                return method
        return None
    
    def __str__(self) -> str:
        return self.value


# 支付方式显示名称映射
PAYMENT_METHOD_DISPLAY_NAMES: Dict[PaymentMethod, str] = {
    PaymentMethod.ALIPAY: "支付宝",
    PaymentMethod.WECHAT_PAY: "微信支付",
    PaymentMethod.PAYPAL: "PayPal",
    PaymentMethod.CRYPTO_STABLECOIN: "稳定币 (USDC/USDT)"
}

# 支付方式与支付 Agent URL 的映射
# 可以从环境变量或配置文件中读取，这里使用默认值
PAYMENT_AGENT_URLS: Dict[PaymentMethod, str] = {
    PaymentMethod.ALIPAY: os.getenv(
        "ALIPAY_AGENT_URL",
        f"http://localhost:{os.getenv('PAYMENT_AGENT_PORT', '5005')}"
    ),
    PaymentMethod.WECHAT_PAY: os.getenv(
        "WECHAT_PAY_AGENT_URL",
        f"http://localhost:{os.getenv('WECHAT_PAY_AGENT_PORT', '5006')}"
    ),
    PaymentMethod.PAYPAL: os.getenv(
        "PAYPAL_AGENT_URL",
        "http://localhost:5007"  # PayPal Agent 默认端口（如果实现）
    ),
    PaymentMethod.CRYPTO_STABLECOIN: os.getenv(
        "CRYPTO_AGENT_URL",
        "http://localhost:5008"  # Crypto Agent 默认端口（如果实现）
    ),
}


def get_payment_agent_url(payment_method: PaymentMethod) -> str:
    """
    获取指定支付方式的 Agent URL
    
    Args:
        payment_method: 支付方式枚举
        
    Returns:
        str: 支付 Agent 的 URL
    """
    return PAYMENT_AGENT_URLS.get(payment_method, "")


def get_payment_method_display_name(payment_method: PaymentMethod) -> str:
    """
    获取支付方式的显示名称
    
    Args:
        payment_method: 支付方式枚举
        
    Returns:
        str: 支付方式的显示名称
    """
    return PAYMENT_METHOD_DISPLAY_NAMES.get(payment_method, payment_method.value)


def is_fiat_payment(payment_method: PaymentMethod) -> bool:
    """
    判断是否为法币支付方式（非加密货币）
    
    Args:
        payment_method: 支付方式枚举
        
    Returns:
        bool: 如果是法币支付返回 True，否则返回 False
    """
    return payment_method != PaymentMethod.CRYPTO_STABLECOIN


def is_crypto_payment(payment_method: PaymentMethod) -> bool:
    """
    判断是否为加密货币支付方式
    
    Args:
        payment_method: 支付方式枚举
        
    Returns:
        bool: 如果是加密货币支付返回 True，否则返回 False
    """
    return payment_method == PaymentMethod.CRYPTO_STABLECOIN


def requires_conversion(user_payment: PaymentMethod, merchant_payment: PaymentMethod) -> bool:
    """
    判断是否需要支付方式转换
    
    Args:
        user_payment: 用户使用的支付方式
        merchant_payment: 商家接受的收款方式
        
    Returns:
        bool: 如果需要转换返回 True，否则返回 False
    """
    # 如果支付方式相同，不需要转换
    if user_payment == merchant_payment:
        return False
    
    # 如果都是法币支付，需要转换（通过稳定币桥接）
    if is_fiat_payment(user_payment) and is_fiat_payment(merchant_payment):
        return True
    
    # 如果一个是法币一个是加密货币，需要转换
    if (is_fiat_payment(user_payment) and is_crypto_payment(merchant_payment)) or \
       (is_crypto_payment(user_payment) and is_fiat_payment(merchant_payment)):
        return True
    
    # 其他情况不需要转换
    return False


# ==============================================================================
#  支付服务工厂类
# ==============================================================================
class PaymentServiceFactory:
    """
    支付服务工厂类 - 根据支付方式创建对应的支付服务实例
    """
    
    # 支付服务类映射（延迟导入，避免循环依赖）
    _service_classes: Dict[PaymentMethod, type] = {}
    
    @classmethod
    def _lazy_import_services(cls):
        """延迟导入支付服务类（避免循环依赖）"""
        if not cls._service_classes:
            try:
                from AgentCore.Agents.payment import AlipayOrderService
                from AgentCore.Agents.wechat_pay_service import WeChatPayOrderService
                
                cls._service_classes = {
                    PaymentMethod.ALIPAY: AlipayOrderService,
                    PaymentMethod.WECHAT_PAY: WeChatPayOrderService,
                    # PaymentMethod.PAYPAL: PayPalOrderService,  # 如果实现
                    # PaymentMethod.CRYPTO_STABLECOIN: CryptoStablecoinService,  # 如果实现
                }
            except ImportError as e:
                print(f"⚠️ [PaymentServiceFactory] 导入支付服务类失败: {e}")
                cls._service_classes = {}
    
    @classmethod
    def create_service(cls, payment_method: PaymentMethod):
        """
        根据支付方式创建对应的支付服务实例
        
        Args:
            payment_method: 支付方式枚举
            
        Returns:
            支付服务实例（AlipayOrderService, WeChatPayOrderService 等）
            
        Raises:
            ValueError: 如果支付方式不支持
        """
        cls._lazy_import_services()
        
        if payment_method not in cls._service_classes:
            supported = [m.value for m in cls._service_classes.keys()]
            raise ValueError(
                f"不支持的支付方式: {payment_method.value}。"
                f"支持的支付方式: {supported}"
            )
        
        service_class = cls._service_classes[payment_method]
        return service_class()
    
    @classmethod
    def create_service_from_string(cls, payment_method_str: str):
        """
        从字符串创建支付服务实例
        
        Args:
            payment_method_str: 支付方式字符串（如 "alipay", "wechat_pay"）
            
        Returns:
            支付服务实例
            
        Raises:
            ValueError: 如果支付方式字符串无效或不受支持
        """
        payment_method = PaymentMethod.from_string(payment_method_str)
        if not payment_method:
            raise ValueError(f"无效的支付方式字符串: {payment_method_str}")
        
        return cls.create_service(payment_method)
    
    @classmethod
    async def create_payment(
        cls,
        payment_method: PaymentMethod,
        query: str,
        product_info: dict = None
    ) -> Dict[str, Any]:
        """
        创建支付订单（统一接口）
        
        Args:
            payment_method: 支付方式枚举
            query: 用户查询字符串
            product_info: 产品信息字典（可选）
            
        Returns:
            dict: 包含支付订单创建结果的字典
                - success: 是否成功
                - order_number: 订单号
                - rmb_amount: 人民币金额（如果适用）
                - response_content: 响应内容
                - error: 错误信息（如果失败）
        """
        try:
            service = cls.create_service(payment_method)
            
            # 根据支付方式调用对应的方法
            if payment_method == PaymentMethod.ALIPAY:
                result = await service.run_alipay_query(query, product_info)
            elif payment_method == PaymentMethod.WECHAT_PAY:
                result = await service.run_wechat_pay_query(query, product_info)
            else:
                return {
                    "success": False,
                    "error": f"支付方式 {payment_method.value} 暂未实现创建支付订单功能"
                }
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "payment_method": payment_method.value
            }
    
    @classmethod
    async def query_payment_status(
        cls,
        payment_method: PaymentMethod,
        order_number: str
    ) -> Dict[str, Any]:
        """
        查询支付状态（统一接口）
        
        Args:
            payment_method: 支付方式枚举
            order_number: 订单号字符串
            
        Returns:
            dict: 包含支付状态查询结果的字典
                - success: 是否成功
                - order_number: 订单号
                - status_info: 状态信息内容
                - error: 错误信息（如果失败）
        """
        try:
            service = cls.create_service(payment_method)
            
            # 所有支付服务都使用相同的方法名
            result = await service.query_payment_status(order_number)
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "order_number": order_number,
                "payment_method": payment_method.value
            }

