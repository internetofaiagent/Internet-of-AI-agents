#!/usr/bin/env python3
"""
支付转换服务

实现不同支付方式之间的转换逻辑，包括判断是否需要转换。
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

# 导入支付方式相关模块
from .payment_methods import (
    PaymentMethod,
    requires_conversion,
    get_payment_method_display_name
)

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PaymentConverter")


class PaymentConverter:
    """
    支付转换服务类 - 处理不同支付方式之间的转换
    
    转换逻辑：
    - 如果用户支付方式 = 商家收款方式 → 直接使用，无需转换
    - 如果不同 → 需要转换（通过稳定币桥接或其他方式）
    """
    
    def __init__(self):
        """初始化支付转换服务"""
        logger.info("✅ [PaymentConverter] 支付转换服务初始化完成")
    
    def check_conversion_needed(
        self,
        user_payment: PaymentMethod,
        merchant_payment: PaymentMethod
    ) -> Dict[str, Any]:
        """
        检查是否需要支付方式转换
        
        Args:
            user_payment: 用户使用的支付方式
            merchant_payment: 商家接受的收款方式
            
        Returns:
            dict: 包含转换检查结果的字典
                - needs_conversion: 是否需要转换 (bool)
                - user_payment: 用户支付方式 (PaymentMethod)
                - merchant_payment: 商家收款方式 (PaymentMethod)
                - reason: 转换原因说明 (str)
        """
        # 使用已有的 requires_conversion 函数判断
        needs_conversion = requires_conversion(user_payment, merchant_payment)
        
        if needs_conversion:
            reason = f"用户使用 {get_payment_method_display_name(user_payment)}，商家接受 {get_payment_method_display_name(merchant_payment)}，需要转换"
            logger.info(f"✅ [PaymentConverter] 需要转换: {reason}")
        else:
            reason = f"用户使用 {get_payment_method_display_name(user_payment)}，商家接受 {get_payment_method_display_name(merchant_payment)}，支付方式匹配，无需转换"
            logger.info(f"ℹ️ [PaymentConverter] 无需转换: {reason}")
        
        return {
            "needs_conversion": needs_conversion,
            "user_payment": user_payment,
            "merchant_payment": merchant_payment,
            "user_payment_display": get_payment_method_display_name(user_payment),
            "merchant_payment_display": get_payment_method_display_name(merchant_payment),
            "reason": reason
        }
    
    def check_conversion_needed_from_string(
        self,
        user_payment_str: str,
        merchant_payment_str: str
    ) -> Dict[str, Any]:
        """
        从字符串检查是否需要支付方式转换
        
        Args:
            user_payment_str: 用户支付方式字符串（如 "alipay", "wechat_pay"）
            merchant_payment_str: 商家收款方式字符串（如 "paypal", "alipay"）
            
        Returns:
            dict: 包含转换检查结果的字典
                - needs_conversion: 是否需要转换 (bool)
                - success: 是否成功解析支付方式 (bool)
                - error: 错误信息（如果解析失败）
        """
        # 从字符串转换为枚举
        user_payment = PaymentMethod.from_string(user_payment_str)
        merchant_payment = PaymentMethod.from_string(merchant_payment_str)
        
        if not user_payment:
            return {
                "success": False,
                "error": f"无效的用户支付方式: {user_payment_str}",
                "needs_conversion": False
            }
        
        if not merchant_payment:
            return {
                "success": False,
                "error": f"无效的商家收款方式: {merchant_payment_str}",
                "needs_conversion": False
            }
        
        # 调用枚举版本的方法
        result = self.check_conversion_needed(user_payment, merchant_payment)
        result["success"] = True
        
        return result
    
    def get_conversion_info(
        self,
        user_payment: PaymentMethod,
        merchant_payment: PaymentMethod
    ) -> Dict[str, Any]:
        """
        获取转换信息（包括是否需要转换、转换路径等）
        
        Args:
            user_payment: 用户使用的支付方式
            merchant_payment: 商家接受的收款方式
            
        Returns:
            dict: 包含转换信息的字典
                - needs_conversion: 是否需要转换
                - conversion_path: 转换路径（如果需要转换）
                - intermediate_method: 中间支付方式（稳定币等）
        """
        check_result = self.check_conversion_needed(user_payment, merchant_payment)
        
        if not check_result["needs_conversion"]:
            return {
                **check_result,
                "conversion_path": None,
                "intermediate_method": None
            }
        
        # 如果需要转换，确定转换路径
        # 转换路径：用户支付方式 → 稳定币 → 商家收款方式
        conversion_path = [
            {
                "from": check_result["user_payment_display"],
                "to": "稳定币 (USDC/USDT)",
                "step": 1
            },
            {
                "from": "稳定币 (USDC/USDT)",
                "to": check_result["merchant_payment_display"],
                "step": 2
            }
        ]
        
        return {
            **check_result,
            "conversion_path": conversion_path,
            "intermediate_method": PaymentMethod.CRYPTO_STABLECOIN
        }
    
    async def execute_conversion(
        self,
        user_payment: PaymentMethod,
        merchant_payment: PaymentMethod,
        payment_order_id: str,
        amount: float,
        currency: str = "USD",
        product_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行简化转换流程（模拟版）
        
        如果用户支付 Alipay，商家收 PayPal：
        - 步骤1：用户通过 Alipay 支付 → 记录支付成功
        - 步骤2：模拟转换为稳定币（记录状态，不上链）
        - 步骤3：模拟从稳定币转换为商家收款方式（记录状态）
        - 步骤4：通知商家收款成功
        
        Args:
            user_payment: 用户使用的支付方式
            merchant_payment: 商家接受的收款方式
            payment_order_id: 支付订单号
            amount: 支付金额
            currency: 货币类型（默认 USD）
            product_info: 商品信息（可选）
            
        Returns:
            dict: 包含转换结果的字典
                - success: 是否成功 (bool)
                - conversion_steps: 转换步骤详情列表
                - final_status: 最终状态
                - merchant_notification: 商家通知结果
                - error: 错误信息（如果失败）
        """
        try:
            # 检查是否需要转换
            conversion_check = self.check_conversion_needed(user_payment, merchant_payment)
            
            if not conversion_check["needs_conversion"]:
                # 如果不需要转换，直接返回
                logger.info(f"ℹ️ [PaymentConverter] 支付方式匹配，无需转换")
                return {
                    "success": True,
                    "needs_conversion": False,
                    "user_payment": user_payment.value,
                    "merchant_payment": merchant_payment.value,
                    "conversion_steps": [],
                    "final_status": "no_conversion_needed",
                    "message": "支付方式匹配，无需转换"
                }
            
            logger.info(f"🔄 [PaymentConverter] 开始执行支付转换流程: {user_payment.value} → {merchant_payment.value}")
            
            conversion_steps = []
            current_timestamp = datetime.now()
            
            # 步骤1：用户通过支付方式支付 → 记录支付成功
            step1 = {
                "step": 1,
                "action": "user_payment_completed",
                "from_method": get_payment_method_display_name(user_payment),
                "to_method": None,
                "status": "completed",
                "order_id": payment_order_id,
                "amount": amount,
                "currency": currency,
                "timestamp": current_timestamp.isoformat(),
                "note": f"用户通过 {get_payment_method_display_name(user_payment)} 支付成功，订单号: {payment_order_id}"
            }
            conversion_steps.append(step1)
            logger.info(f"✅ [PaymentConverter] 步骤1完成: 用户支付成功 ({payment_order_id})")
            
            # 步骤2：模拟转换为稳定币（记录状态，不上链）
            stablecoin_amount = amount  # 假设1:1转换，实际应该考虑汇率
            step2_timestamp = current_timestamp.replace(second=current_timestamp.second + 1)
            step2 = {
                "step": 2,
                "action": "convert_to_stablecoin",
                "from_method": get_payment_method_display_name(user_payment),
                "to_method": "稳定币 (USDC/USDT)",
                "status": "completed",
                "amount": stablecoin_amount,
                "currency": "USDC",
                "timestamp": step2_timestamp.isoformat(),
                "on_chain": False,  # 不上链，仅记录状态
                "note": f"模拟转换: {amount} {currency} → {stablecoin_amount} USDC（状态记录，未上链）"
            }
            conversion_steps.append(step2)
            logger.info(f"✅ [PaymentConverter] 步骤2完成: 转换为稳定币 ({stablecoin_amount} USDC)")
            
            # 步骤3：模拟从稳定币转换为商家收款方式（记录状态）
            merchant_amount = stablecoin_amount  # 假设1:1转换，实际应该考虑汇率
            step3_timestamp = step2_timestamp.replace(second=step2_timestamp.second + 1)
            step3 = {
                "step": 3,
                "action": "convert_to_merchant_payment",
                "from_method": "稳定币 (USDC/USDT)",
                "to_method": get_payment_method_display_name(merchant_payment),
                "status": "completed",
                "amount": merchant_amount,
                "currency": currency,  # 假设商家收款使用相同货币
                "timestamp": step3_timestamp.isoformat(),
                "merchant_order_id": f"MERCHANT_{payment_order_id}",
                "note": f"模拟转换: {stablecoin_amount} USDC → {merchant_amount} {currency} ({get_payment_method_display_name(merchant_payment)})"
            }
            conversion_steps.append(step3)
            logger.info(f"✅ [PaymentConverter] 步骤3完成: 转换为商家收款方式 ({merchant_amount} {currency})")
            
            # 步骤4：通知商家收款成功（模拟通知）
            step4_timestamp = step3_timestamp.replace(second=step3_timestamp.second + 1)
            merchant_notification = {
                "step": 4,
                "action": "notify_merchant",
                "status": "completed",
                "merchant_payment_method": merchant_payment.value,
                "merchant_order_id": step3["merchant_order_id"],
                "amount": merchant_amount,
                "currency": currency,
                "timestamp": step4_timestamp.isoformat(),
                "notification_result": "merchant_notified_successfully",
                "note": f"商家已收到 {merchant_amount} {currency}，收款方式: {get_payment_method_display_name(merchant_payment)}"
            }
            conversion_steps.append(merchant_notification)
            logger.info(f"✅ [PaymentConverter] 步骤4完成: 商家已收到收款通知")
            
            # 构建最终结果
            result = {
                "success": True,
                "needs_conversion": True,
                "user_payment": user_payment.value,
                "merchant_payment": merchant_payment.value,
                "payment_order_id": payment_order_id,
                "original_amount": amount,
                "original_currency": currency,
                "final_amount": merchant_amount,
                "final_currency": currency,
                "conversion_steps": conversion_steps,
                "conversion_path": [
                    get_payment_method_display_name(user_payment),
                    "稳定币 (USDC/USDT)",
                    get_payment_method_display_name(merchant_payment)
                ],
                "final_status": "conversion_completed",
                "merchant_notification": merchant_notification,
                "total_steps": len(conversion_steps),
                "conversion_completed_at": step4_timestamp.isoformat(),
                "message": f"支付转换成功: {get_payment_method_display_name(user_payment)} → {get_payment_method_display_name(merchant_payment)}"
            }
            
            logger.info(f"✅ [PaymentConverter] 支付转换流程完成: {len(conversion_steps)} 个步骤全部成功")
            return result
            
        except Exception as e:
            error_msg = f"支付转换流程执行失败: {str(e)}"
            logger.error(f"❌ [PaymentConverter] {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "user_payment": user_payment.value if user_payment else None,
                "merchant_payment": merchant_payment.value if merchant_payment else None,
                "payment_order_id": payment_order_id,
                "conversion_steps": conversion_steps if 'conversion_steps' in locals() else [],
                "final_status": "conversion_failed"
            }
