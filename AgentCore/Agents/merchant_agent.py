#!/usr/bin/env python3
"""
商家 Agent - 处理订单接收、交付和订单管理
"""

import os
import json
import logging
import hashlib
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict, field

# --- A2A 库导入 ---
from python_a2a import A2AServer, run_server, AgentCard, AgentSkill, TaskStatus, TaskState, A2AClient

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MerchantAgent")

# --- 区块链服务导入 ---
try:
    from .blockchain_service import BlockchainService, OnChainTransactionData
    BLOCKCHAIN_SERVICE_AVAILABLE = True
    logger.info("✅ [MerchantAgent] 区块链服务导入成功")
except ImportError as e:
    BLOCKCHAIN_SERVICE_AVAILABLE = False
    logger.warning(f"⚠️ [MerchantAgent] 区块链服务导入失败: {e}")

# --- WebSocket 通知服务导入 ---
try:
    import sys
    import os
    # 添加项目根目录到路径，以便导入 ws_notify_server
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from ws_notify_server import send_message
    from .websocket_messages import (
        create_order_status_update_message,
        create_delivery_notification_message,
        create_blockchain_transaction_message
    )
    WEBSOCKET_NOTIFICATION_AVAILABLE = True
    logger.info("✅ [MerchantAgent] WebSocket 通知服务导入成功")
except ImportError as e:
    WEBSOCKET_NOTIFICATION_AVAILABLE = False
    logger.warning(f"⚠️ [MerchantAgent] WebSocket 通知服务导入失败: {e}")
    send_message = None


# ==============================================================================
#  数据类与枚举
# ==============================================================================
class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = "PENDING"           # 待接单
    ACCEPTED = "ACCEPTED"         # 已接单
    PROCESSING = "PROCESSING"     # 处理中
    DELIVERED = "DELIVERED"       # 已交付
    COMPLETED = "COMPLETED"       # 已完成
    CANCELLED = "CANCELLED"       # 已取消


@dataclass
class UserInfo:
    """用户信息数据模型"""
    user_id: str
    user_name: Optional[str] = None
    user_address: Optional[str] = None
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    user_wallet_address: Optional[str] = None  # 用户钱包地址（用于区块链支付）


@dataclass
class ProductInfo:
    """商品信息数据模型"""
    product_id: Optional[str] = None
    product_name: str = ""
    product_description: Optional[str] = None
    product_url: Optional[str] = None
    quantity: int = 1
    unit_price: float = 0.0
    category: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)  # 其他商品属性


@dataclass
class PaymentInfo:
    """支付信息数据模型"""
    payment_order_id: Optional[str] = None
    payment_method: Optional[str] = None  # 支付方式，如 "alipay", "blockchain"
    payment_amount: float = 0.0
    payment_currency: str = "USD"
    payment_status: Optional[str] = None  # 支付状态
    payment_transaction_hash: Optional[str] = None  # 区块链交易哈希（如果使用区块链支付）
    paid_at: Optional[str] = None  # 支付时间（ISO格式）


@dataclass
class DeliveryInfo:
    """交付信息数据模型"""
    delivery_method: Optional[str] = None  # 交付方式，如 "express", "standard"
    tracking_number: Optional[str] = None  # 物流追踪号
    carrier: Optional[str] = None  # 承运商
    estimated_delivery_date: Optional[str] = None  # 预计交付日期
    actual_delivery_date: Optional[str] = None  # 实际交付日期
    delivery_address: Optional[str] = None  # 交付地址
    delivery_status: Optional[str] = None  # 交付状态


@dataclass
class ArbitrationInfo:
    """仲裁信息数据模型"""
    arbitration_agent_url: Optional[str] = None  # 选定的仲裁Agent URL
    status: str = "none"  # none, initiated, decided
    case_id: Optional[str] = None  # 仲裁案例ID（发起仲裁后设置）
    decision: Optional[str] = None  # 仲裁裁定结果（decided后设置）
    responsible_party: Optional[str] = None  # "user" or "merchant"（decided后设置）


@dataclass
class Order:
    """订单数据模型"""
    order_id: str
    user_info: UserInfo
    product_info: ProductInfo
    amount: float  # 订单总金额
    currency: str = "USD"
    status: OrderStatus = OrderStatus.PENDING
    payment_info: Optional[PaymentInfo] = None
    delivery_info: Optional[DeliveryInfo] = None
    arbitration_info: Optional[ArbitrationInfo] = None  # 仲裁信息
    
    # 时间戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    accepted_at: Optional[str] = None  # 接单时间
    delivered_at: Optional[str] = None  # 交付时间
    completed_at: Optional[str] = None  # 完成时间
    cancelled_at: Optional[str] = None  # 取消时间
    
    # 其他元数据
    metadata: Dict[str, Any] = field(default_factory=dict)  # 其他订单元数据
    notes: Optional[str] = None  # 订单备注
    user_agent_url: Optional[str] = None  # 用户 Agent URL（用于交付通知）
    
    def to_dict(self) -> Dict[str, Any]:
        """将订单对象转换为字典"""
        result = asdict(self)
        # 将枚举转换为字符串
        result["status"] = self.status.value
        # 处理嵌套的dataclass对象
        if self.user_info:
            result["user_info"] = asdict(self.user_info)
        if self.product_info:
            result["product_info"] = asdict(self.product_info)
        if self.payment_info:
            result["payment_info"] = asdict(self.payment_info)
        if self.delivery_info:
            result["delivery_info"] = asdict(self.delivery_info)
        if self.arbitration_info:
            result["arbitration_info"] = asdict(self.arbitration_info)
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Order":
        """从字典创建订单对象"""
        # 处理状态枚举
        if isinstance(data.get("status"), str):
            data["status"] = OrderStatus(data["status"])
        elif isinstance(data.get("status"), dict):
            data["status"] = OrderStatus(data["status"].get("value", "PENDING"))
        
        # 处理嵌套的dataclass
        if "user_info" in data and isinstance(data["user_info"], dict):
            data["user_info"] = UserInfo(**data["user_info"])
        if "product_info" in data and isinstance(data["product_info"], dict):
            data["product_info"] = ProductInfo(**data["product_info"])
        if "payment_info" in data and isinstance(data["payment_info"], dict):
            data["payment_info"] = PaymentInfo(**data["payment_info"])
        elif "payment_info" not in data:
            data["payment_info"] = None
        if "delivery_info" in data and isinstance(data["delivery_info"], dict):
            data["delivery_info"] = DeliveryInfo(**data["delivery_info"])
        elif "delivery_info" not in data:
            data["delivery_info"] = None
        if "arbitration_info" in data and isinstance(data["arbitration_info"], dict):
            data["arbitration_info"] = ArbitrationInfo(**data["arbitration_info"])
        elif "arbitration_info" not in data:
            data["arbitration_info"] = None
        
        return cls(**data)


# ==============================================================================
#  商家 Agent 服务器实现
# ==============================================================================
class MerchantAgent(A2AServer):
    """
    商家 Agent - 负责接收订单、处理交付和订单管理
    """
    
    def __init__(self, agent_card: AgentCard):
        """初始化商家 Agent"""
        super().__init__(agent_card=agent_card)
        
        # 订单存储（使用Order数据模型，在实际应用中应该使用数据库）
        self.orders: Dict[str, Order] = {}
        
        # 订单状态映射（用于显示中文）
        self.ORDER_STATUS_DISPLAY = {
            OrderStatus.PENDING.value: "待接单",
            OrderStatus.ACCEPTED.value: "已接单",
            OrderStatus.PROCESSING.value: "处理中",
            OrderStatus.DELIVERED.value: "已交付",
            OrderStatus.COMPLETED.value: "已完成",
            OrderStatus.CANCELLED.value: "已取消"
        }
        
        # 初始化区块链服务（可选）
        self.blockchain_service = None
        if BLOCKCHAIN_SERVICE_AVAILABLE:
            try:
                self.blockchain_service = BlockchainService()
                logger.info("✅ [MerchantAgent] 区块链服务初始化成功")
            except Exception as e:
                logger.warning(f"⚠️ [MerchantAgent] 区块链服务初始化失败: {e}")
                self.blockchain_service = None
        
        # 商家接受的支付方式配置（默认支持所有支付方式）
        # 可以从环境变量读取，格式：MERCHANT_ACCEPTED_PAYMENT_METHODS=alipay,wechat_pay,paypal
        accepted_payment_methods_env = os.getenv("MERCHANT_ACCEPTED_PAYMENT_METHODS", "").strip()
        if accepted_payment_methods_env:
            # 从环境变量解析支付方式列表
            self.accepted_payment_methods = [
                method.strip().lower() 
                for method in accepted_payment_methods_env.split(",") 
                if method.strip()
            ]
            logger.info(f"✅ [MerchantAgent] 从环境变量读取接受的支付方式: {self.accepted_payment_methods}")
        else:
            # 默认支持所有支付方式
            self.accepted_payment_methods = [
                "alipay", "wechat_pay", "paypal", "crypto_stablecoin"
            ]
            logger.info(f"✅ [MerchantAgent] 使用默认接受的支付方式: {self.accepted_payment_methods}")
        
        # 商家接受的仲裁Agent配置（从环境变量读取）
        # 格式：MERCHANT_ACCEPTED_ARBITRATION_AGENTS=http://localhost:5025,http://localhost:5026
        accepted_arbitration_agents_env = os.getenv("MERCHANT_ACCEPTED_ARBITRATION_AGENTS", "").strip()
        if accepted_arbitration_agents_env:
            # 从环境变量解析仲裁Agent URL列表
            self.accepted_arbitration_agents = [
                url.strip() 
                for url in accepted_arbitration_agents_env.split(",") 
                if url.strip()
            ]
            logger.info(f"✅ [MerchantAgent] 从环境变量读取接受的仲裁Agent: {self.accepted_arbitration_agents}")
        else:
            # 默认使用空列表（表示不限制，或使用系统默认）
            self.accepted_arbitration_agents = []
            logger.info("ℹ️ [MerchantAgent] 商家接受的仲裁Agent未配置，将使用默认值（空列表）")
        
        logger.info("✅ [MerchantAgent] 商家 Agent 初始化完成")
    
    def _send_websocket_notification(self, message):
        """
        发送 WebSocket 通知的辅助方法
        
        Args:
            message: WebSocketMessage 对象
        """
        if not WEBSOCKET_NOTIFICATION_AVAILABLE or not send_message:
            return
        
        try:
            success = send_message(message)
            if success:
                logger.debug(f"📤 [MerchantAgent] WebSocket 通知已发送: {message.message_type}")
            else:
                logger.warning(f"⚠️ [MerchantAgent] WebSocket 通知发送失败: {message.message_type}")
        except Exception as e:
            logger.error(f"❌ [MerchantAgent] 发送 WebSocket 通知时发生异常: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def handle_task(self, task):
        """
        A2A服务器的核心处理函数。当收到来自客户端的请求时，此方法被调用。
        """
        text = task.message.get("content", {}).get("text", "")
        logger.info(f"📩 [MerchantAgent] 收到任务: '{text[:100]}...' (length: {len(text)})")
        
        # 处理健康检查请求
        if text.lower().strip() in ["health check", "health", "ping", ""]:
            logger.info("✅ [MerchantAgent] Health check request - returning healthy status")
            task.artifacts = [{"parts": [{"type": "text", "text": "healthy - Merchant Agent is operational"}]}]
            task.status = TaskStatus(state=TaskState.COMPLETED)
            return task
        
        if not text:
            response_text = "错误: 收到了一个空的请求。"
            task.status = TaskStatus(state=TaskState.FAILED)
        else:
            try:
                # 根据请求内容路由到不同的处理方法
                response_text = self._route_request(text)
                task.status = TaskStatus(state=TaskState.COMPLETED)
                logger.info("💬 [MerchantAgent] 处理完成")
                
            except Exception as e:
                import traceback
                logger.error(f"❌ [MerchantAgent] 任务处理时发生错误: {e}")
                traceback.print_exc()
                response_text = f"服务器内部错误: {e}"
                task.status = TaskStatus(state=TaskState.FAILED)
        
        # 将最终结果打包成 A2A 响应
        task.artifacts = [{"parts": [{"type": "text", "text": str(response_text)}]}]
        return task
    
    def _route_request(self, text: str) -> str:
        """路由请求到相应的处理方法"""
        text_lower = text.lower()
        
        # 检查是否是订单接收请求
        if any(keyword in text_lower for keyword in ["订单", "order", "接收订单", "receive order", "new order"]):
            return self._handle_order_received(text)
        
        # 检查是否是订单查询请求
        elif any(keyword in text_lower for keyword in ["查询订单", "query order", "订单状态", "order status", "list orders"]):
            return self._handle_order_query(text)
        
        # 检查是否是订单交付请求
        elif any(keyword in text_lower for keyword in ["交付", "deliver", "发货", "ship", "完成交付"]):
            return self._handle_order_delivery(text)
        
        # 检查是否是订单完成请求
        elif any(keyword in text_lower for keyword in ["完成订单", "complete order", "确认收货", "confirm delivery", "订单完成"]):
            return self._handle_order_completion(text)
        
        # 检查是否是订单管理请求
        elif any(keyword in text_lower for keyword in ["管理订单", "manage order", "更新订单", "update order"]):
            return self._handle_order_management(text)
        
        # 检查是否是仲裁通知请求
        elif any(keyword in text_lower for keyword in ["仲裁", "arbitration", "裁定结果", "arbitration result", "仲裁通知"]):
            return self.handle_arbitration_notification(text)
        
        # 默认响应
        else:
            return self._handle_general_request(text)
    
    def handle_order_received(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        接收来自用户 Agent 的订单
        
        Args:
            order_data: 订单数据字典，包含订单信息
            
        Returns:
            包含处理结果的字典，包含 success, message, order_id 等字段
        """
        logger.info("📦 [MerchantAgent] 接收订单请求")
        
        try:
            # 验证订单信息
            validation_result = self._validate_order_comprehensive(order_data)
            if not validation_result["valid"]:
                logger.warning(f"❌ 订单验证失败: {validation_result['error']}")
                return {
                    "success": False,
                    "error": validation_result["error"],
                    "validation_errors": validation_result.get("errors", [])
                }
            
            # 检查订单ID是否已存在
            order_id = order_data.get("order_id")
            if not order_id:
                order_id = f"ORDER_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            elif order_id in self.orders:
                existing_order = self.orders[order_id]
                logger.warning(f"⚠️ 订单ID已存在: {order_id}, 当前状态: {existing_order.status.value}")
                return {
                    "success": False,
                    "error": f"订单ID已存在: {order_id}",
                    "existing_order_status": existing_order.status.value
                }
            
            # 创建用户信息
            user_info = UserInfo(
                user_id=order_data.get("user_id"),
                user_name=order_data.get("user_name"),
                user_address=order_data.get("user_address"),
                user_email=order_data.get("user_email"),
                user_phone=order_data.get("user_phone"),
                user_wallet_address=order_data.get("user_wallet_address")
            )
            
            # 创建商品信息
            product_data = order_data.get("product_info", {})
            if isinstance(product_data, dict):
                product_info = ProductInfo(
                    product_id=product_data.get("product_id"),
                    product_name=product_data.get("product_name", product_data.get("name", "")),
                    product_description=product_data.get("product_description", product_data.get("description")),
                    product_url=product_data.get("product_url", product_data.get("url")),
                    quantity=product_data.get("quantity", 1),
                    unit_price=product_data.get("unit_price", product_data.get("price", 0.0)),
                    category=product_data.get("category"),
                    attributes={k: v for k, v in product_data.items() 
                              if k not in ["product_id", "product_name", "name", "product_description", 
                                         "description", "product_url", "url", "quantity", "unit_price", 
                                         "price", "category"]}
                )
            else:
                # 如果product_info不是字典，创建一个基本的ProductInfo
                product_info = ProductInfo(product_name=str(product_data) if product_data else "未知商品")
            
            # 验证金额一致性
            amount = float(order_data.get("amount", 0.0))
            calculated_amount = product_info.unit_price * product_info.quantity
            if calculated_amount > 0 and abs(amount - calculated_amount) > 0.01:
                logger.warning(f"⚠️ 金额不一致: 订单金额={amount}, 计算金额={calculated_amount}")
                # 使用订单中的金额，但记录警告
            
            # 验证支付方式是否被接受
            payment_data = order_data.get("payment_info", {})
            payment_method = payment_data.get("payment_method") if payment_data else None
            if payment_method:
                payment_method_lower = payment_method.lower().strip()
                # 标准化支付方式名称（处理可能的变体）
                payment_method_normalized = payment_method_lower.replace("-", "_").replace(" ", "_")
                
                # 检查支付方式是否在接受的列表中
                if payment_method_normalized not in self.accepted_payment_methods:
                    # 尝试匹配支付方式的变体
                    accepted_normalized = [pm.replace("-", "_").replace(" ", "_") for pm in self.accepted_payment_methods]
                    if payment_method_normalized not in accepted_normalized:
                        logger.warning(f"❌ [MerchantAgent] 不接受的支付方式: {payment_method} (接受的支付方式: {self.accepted_payment_methods})")
                        return {
                            "success": False,
                            "error": f"不接受的支付方式: {payment_method}",
                            "accepted_payment_methods": self.accepted_payment_methods,
                            "provided_payment_method": payment_method
                        }
                
                logger.info(f"✅ [MerchantAgent] 支付方式验证通过: {payment_method}")
            
            # 创建支付信息
            payment_info = None
            if payment_data:
                payment_info = PaymentInfo(
                    payment_order_id=payment_data.get("payment_order_id"),
                    payment_method=payment_data.get("payment_method"),
                    payment_amount=payment_data.get("payment_amount", amount),
                    payment_currency=payment_data.get("payment_currency", order_data.get("currency", "USD")),
                    payment_status=payment_data.get("payment_status"),
                    payment_transaction_hash=payment_data.get("payment_transaction_hash"),
                    paid_at=payment_data.get("paid_at")
                )
            
            # 获取用户 Agent URL（用于交付通知）
            user_agent_url = order_data.get("user_agent_url")
            
            # 创建订单对象（初始状态为 PENDING）
            order = Order(
                order_id=order_id,
                user_info=user_info,
                product_info=product_info,
                amount=amount,
                currency=order_data.get("currency", "USD"),
                status=OrderStatus.PENDING,
                payment_info=payment_info,
                delivery_info=None,
                metadata=order_data.get("metadata", {}),
                notes=order_data.get("notes"),
                user_agent_url=user_agent_url
            )
            
            # 存储订单（状态为 PENDING）
            self.orders[order_id] = order
            logger.info(f"📦 [MerchantAgent] 订单已创建: {order_id}, 状态: {order.status.value}")
            
            # 发送订单创建通知
            try:
                if WEBSOCKET_NOTIFICATION_AVAILABLE:
                    order_dict = order.to_dict()
                    notification = create_order_status_update_message(
                        order_id=order_id,
                        new_status=order.status.value,
                        old_status=None,
                        order_data=order_dict,
                        status_display=self.ORDER_STATUS_DISPLAY.get(order.status.value, order.status.value),
                        user_id=order.user_info.user_id
                    )
                    self._send_websocket_notification(notification)
            except Exception as e:
                logger.warning(f"⚠️ [MerchantAgent] 发送订单创建通知失败: {e}")
            
            # 自动接单（在实际应用中可以根据业务规则决定是否自动接单）
            accept_result = self._accept_order(order_id)
            if not accept_result["success"]:
                logger.error(f"❌ 接单失败: {accept_result.get('error')}")
                return accept_result
            
            order = self.orders[order_id]  # 重新获取更新后的订单
            
            logger.info(f"✅ [MerchantAgent] 订单已接收并自动接单: {order_id}")
            
            # 如果支付已完成，调用上链功能
            blockchain_result = None
            if order.payment_info and order.payment_info.payment_status == "paid":
                blockchain_result = self._store_order_on_chain(order, status="paid")
                if blockchain_result and blockchain_result.get("success"):
                    logger.info(f"✅ [MerchantAgent] 订单支付信息已上链: {order_id}, 交易哈希: {blockchain_result.get('tx_hash', 'N/A')}")
                else:
                    error_msg = blockchain_result.get("error", "未知错误") if blockchain_result else "区块链服务不可用"
                    logger.warning(f"⚠️ [MerchantAgent] 订单支付信息上链失败: {order_id}, 错误: {error_msg}")
            
            # 获取状态显示文本
            status_display = self.ORDER_STATUS_DISPLAY.get(order.status.value, order.status.value)
            
            # 返回成功结果
            result = {
                "success": True,
                "message": "订单已成功接收并接单",
                "order_id": order.order_id,
                "status": order.status.value,
                "status_display": status_display,
                "order_info": {
                    "user_id": order.user_info.user_id,
                    "product_name": order.product_info.product_name,
                    "quantity": order.product_info.quantity,
                    "unit_price": order.product_info.unit_price,
                    "amount": order.amount,
                    "currency": order.currency,
                    "created_at": order.created_at,
                    "accepted_at": order.accepted_at
                }
            }
            
            # 如果上链成功，添加上链信息
            if blockchain_result and blockchain_result.get("success"):
                result["blockchain_info"] = {
                    "tx_hash": blockchain_result.get("tx_hash"),
                    "block_number": blockchain_result.get("block_number"),
                    "data_hash": blockchain_result.get("data_hash")
                }
            
            return result
            
        except Exception as e:
            import traceback
            logger.error(f"❌ 处理订单接收失败: {e}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": f"订单接收处理异常: {str(e)}"
            }
    
    def _handle_order_received(self, text: str) -> str:
        """处理订单接收请求（文本格式，内部使用）"""
        logger.info("📦 [MerchantAgent] 处理订单接收请求（文本格式）")
        
        try:
            # 尝试从文本中解析订单信息（JSON格式）
            order_data = self._parse_order_from_text(text)
            
            # 调用主要的订单接收方法
            result = self.handle_order_received(order_data)
            
            if result["success"]:
                order_id = result["order_id"]
                order_info = result["order_info"]
                status_display = result["status_display"]
                
                order = self.orders[order_id]  # 获取完整订单对象以获取currency
                
                return f"""✅ 订单已成功接收并接单！

**订单信息:**
- 订单ID: {order_id}
- 用户ID: {order_info['user_id']}
- 商品名称: {order_info['product_name']}
- 数量: {order_info['quantity']}
- 单价: {order_info['unit_price']} {order.currency}
- 总金额: {order_info['amount']} {order.currency}
- 状态: {status_display} ({result['status']})
- 接收时间: {order_info['created_at']}
- 接单时间: {order_info['accepted_at']}

订单已进入处理流程。"""
            else:
                error_msg = result.get("error", "未知错误")
                validation_errors = result.get("validation_errors", [])
                if validation_errors:
                    error_msg += "\n验证错误详情:\n" + "\n".join(f"- {err}" for err in validation_errors)
                return f"❌ 订单接收失败: {error_msg}"
            
        except Exception as e:
            logger.error(f"❌ 处理订单接收失败: {e}")
            return f"❌ 订单接收失败: {str(e)}"
    
    def _handle_order_query(self, text: str) -> str:
        """处理订单查询请求"""
        logger.info("🔍 [MerchantAgent] 处理订单查询请求")
        
        try:
            # 尝试从文本中提取订单ID
            order_id = self._extract_order_id_from_text(text)
            
            if order_id and order_id in self.orders:
                # 查询单个订单
                order = self.orders[order_id]
                status_display = self.ORDER_STATUS_DISPLAY.get(order.status.value, order.status.value)
                
                order_detail = f"""**订单详情:**

- 订单ID: {order.order_id}
- 用户ID: {order.user_info.user_id}
- 用户名称: {order.user_info.user_name or "未提供"}
- 商品名称: {order.product_info.product_name}
- 商品描述: {order.product_info.product_description or "无"}
- 数量: {order.product_info.quantity}
- 单价: {order.product_info.unit_price} {order.currency}
- 总金额: {order.amount} {order.currency}
- 状态: {status_display} ({order.status.value})
- 创建时间: {order.created_at}
- 更新时间: {order.updated_at}"""
                
                if order.accepted_at:
                    order_detail += f"\n- 接单时间: {order.accepted_at}"
                if order.delivered_at:
                    order_detail += f"\n- 交付时间: {order.delivered_at}"
                if order.completed_at:
                    order_detail += f"\n- 完成时间: {order.completed_at}"
                if order.payment_info:
                    order_detail += f"\n- 支付状态: {order.payment_info.payment_status or '未支付'}"
                if order.delivery_info and order.delivery_info.tracking_number:
                    order_detail += f"\n- 物流追踪号: {order.delivery_info.tracking_number}"
                
                return order_detail
            else:
                # 列出所有订单
                if not self.orders:
                    return "📋 当前没有订单。"
                
                orders_list = []
                for oid, order in self.orders.items():
                    status_display = self.ORDER_STATUS_DISPLAY.get(order.status.value, order.status.value)
                    orders_list.append(f"- {oid}: {status_display} - {order.amount} {order.currency}")
                
                return f"""**所有订单列表 ({len(self.orders)}个):**

{chr(10).join(orders_list)}

使用 "查询订单 [订单ID]" 查看具体订单详情。"""
                
        except Exception as e:
            logger.error(f"❌ 查询订单失败: {e}")
            return f"❌ 查询订单失败: {str(e)}"
    
    def _handle_order_delivery(self, text: str) -> str:
        """处理订单交付请求"""
        logger.info("🚚 [MerchantAgent] 处理订单交付请求")
        
        try:
            # 提取订单ID
            order_id = self._extract_order_id_from_text(text)
            
            if not order_id or order_id not in self.orders:
                return "❌ 未找到指定的订单。请提供有效的订单ID。"
            
            order = self.orders[order_id]
            
            # 检查订单状态
            if order.status in [OrderStatus.DELIVERED, OrderStatus.COMPLETED]:
                status_display = self.ORDER_STATUS_DISPLAY.get(order.status.value, order.status.value)
                return f"⚠️ 订单 {order_id} 已经交付完成，当前状态: {status_display}"
            
            if order.status == OrderStatus.CANCELLED:
                return f"❌ 订单 {order_id} 已取消，无法交付。"
            
            # 准备交付时间和交付信息
            delivered_at = datetime.now().isoformat()
            
            # 解析交付信息
            delivery_info_dict = self._parse_delivery_info_from_text(text)
            if delivery_info_dict:
                # 更新或创建交付信息
                if order.delivery_info is None:
                    order.delivery_info = DeliveryInfo(**delivery_info_dict)
                else:
                    # 更新现有交付信息
                    for key, value in delivery_info_dict.items():
                        if hasattr(order.delivery_info, key):
                            setattr(order.delivery_info, key, value)
            else:
                # 如果没有解析到交付信息，创建一个基本的DeliveryInfo
                if order.delivery_info is None:
                    order.delivery_info = DeliveryInfo()
            
            # 验证交付信息
            validation_result = self._validate_delivery_info(order, order.delivery_info, delivered_at)
            if not validation_result["valid"]:
                error_msg = validation_result["error"]
                validation_errors = validation_result.get("errors", [])
                error_details = "\n".join(f"- {err}" for err in validation_errors)
                logger.warning(f"❌ [MerchantAgent] 交付信息验证失败: {error_msg}\n{error_details}")
                return f"""❌ 交付信息验证失败: {error_msg}

验证错误详情:
{error_details}

请修正交付信息后重试。"""
            
            # 保存旧状态
            old_status = order.status.value
            
            # 验证通过，更新订单状态为已交付
            order.status = OrderStatus.DELIVERED
            order.delivered_at = delivered_at
            order.updated_at = datetime.now().isoformat()
            
            logger.info(f"✅ [MerchantAgent] 订单已交付: {order_id}")
            
            # 发送订单交付通知
            try:
                if WEBSOCKET_NOTIFICATION_AVAILABLE:
                    # 发送订单状态更新通知
                    order_dict = order.to_dict()
                    status_notification = create_order_status_update_message(
                        order_id=order_id,
                        new_status=order.status.value,
                        old_status=old_status,
                        order_data=order_dict,
                        status_display=self.ORDER_STATUS_DISPLAY.get(order.status.value, order.status.value),
                        user_id=order.user_info.user_id
                    )
                    self._send_websocket_notification(status_notification)
                    
                    # 发送交付通知
                    delivery_notification = create_delivery_notification_message(
                        order_id=order_id,
                        delivery_status="delivered",
                        tracking_number=order.delivery_info.tracking_number if order.delivery_info else None,
                        carrier=order.delivery_info.carrier if order.delivery_info else None,
                        delivery_method=order.delivery_info.delivery_method if order.delivery_info else None,
                        actual_delivery_date=delivered_at,
                        delivery_address=order.delivery_info.delivery_address if order.delivery_info else None,
                        delivery_proof=delivery_proof if delivery_proof.get("success") else None,
                        delivery_proof_hash=delivery_proof.get("proof_hash") if delivery_proof.get("success") else None,
                        user_id=order.user_info.user_id
                    )
                    self._send_websocket_notification(delivery_notification)
            except Exception as e:
                logger.warning(f"⚠️ [MerchantAgent] 发送订单交付通知失败: {e}")
            
            # 生成交付凭证
            delivery_proof = self._generate_delivery_proof(order)
            proof_info = ""
            if delivery_proof.get("success"):
                proof_hash = delivery_proof.get("proof_hash", "")
                proof_info = f"\n- 交付凭证哈希: {proof_hash[:16]}..." if proof_hash else ""
                logger.info(f"✅ [MerchantAgent] 交付凭证已生成: {order_id}")
            else:
                logger.warning(f"⚠️ [MerchantAgent] 交付凭证生成失败: {delivery_proof.get('error', '未知错误')}")
            
            # 通知用户 Agent 交付完成
            notification_info = ""
            if delivery_proof.get("success"):
                notification_result = self._notify_user_agent_delivery(order, delivery_proof)
                if notification_result.get("success"):
                    notification_info = "\n- ✅ 交付通知已成功发送至用户 Agent"
                    logger.info(f"✅ [MerchantAgent] 交付通知已成功发送: {order_id}")
                else:
                    notification_info = f"\n- ⚠️ 交付通知发送失败: {notification_result.get('error', '未知错误')}"
                    logger.warning(f"⚠️ [MerchantAgent] 交付通知发送失败: {notification_result.get('error', '未知错误')}")
            else:
                notification_info = "\n- ⚠️ 由于交付凭证生成失败，未发送交付通知"
                logger.warning(f"⚠️ [MerchantAgent] 由于交付凭证生成失败，未发送交付通知: {order_id}")
            
            # 调用上链功能存储交付信息
            blockchain_result = None
            delivery_tx_hash = None
            if delivery_proof.get("success"):
                blockchain_result = self._store_order_on_chain(order, status="delivered")
                if blockchain_result and blockchain_result.get("success"):
                    delivery_tx_hash = blockchain_result.get("tx_hash")
                    # 将交付交易哈希保存到订单元数据中，以便后续完成订单时使用
                    if delivery_tx_hash:
                        if "blockchain_tx_hashes" not in order.metadata:
                            order.metadata["blockchain_tx_hashes"] = {}
                        order.metadata["blockchain_tx_hashes"]["delivery"] = delivery_tx_hash
                    
                    blockchain_info = f"\n- ✅ 交付信息已上链，交易哈希: {delivery_tx_hash[:16] if delivery_tx_hash else 'N/A'}..."
                    notification_info += blockchain_info
                    logger.info(f"✅ [MerchantAgent] 订单交付信息已上链: {order_id}, 交易哈希: {delivery_tx_hash}")
                else:
                    error_msg = blockchain_result.get("error", "未知错误") if blockchain_result else "区块链服务不可用"
                    blockchain_info = f"\n- ⚠️ 交付信息上链失败: {error_msg}"
                    notification_info += blockchain_info
                    logger.warning(f"⚠️ [MerchantAgent] 订单交付信息上链失败: {order_id}, 错误: {error_msg}")
            
            status_display = self.ORDER_STATUS_DISPLAY.get(order.status.value, order.status.value)
            delivery_info_str = json.dumps(asdict(order.delivery_info), ensure_ascii=False) if order.delivery_info else "{}"
            
            return f"""✅ 订单交付完成！

**订单信息:**
- 订单ID: {order_id}
- 状态: {status_display} ({order.status.value})
- 交付时间: {order.delivered_at}
- 交付信息: {delivery_info_str}{proof_info}{notification_info}

订单已标记为已交付。"""
            
        except Exception as e:
            logger.error(f"❌ 处理订单交付失败: {e}")
            return f"❌ 订单交付失败: {str(e)}"
    
    def _handle_order_management(self, text: str) -> str:
        """处理订单管理请求"""
        logger.info("⚙️ [MerchantAgent] 处理订单管理请求")
        
        # 这是一个占位方法，后续可以扩展更多订单管理功能
        return """📋 订单管理功能

支持的操作:
- 接收订单: 发送包含订单信息的请求
- 查询订单: "查询订单 [订单ID]" 或 "list orders"
- 订单交付: "交付订单 [订单ID]"
- 更新订单状态: "更新订单 [订单ID] [新状态]"

更多功能正在开发中..."""
    
    def _handle_general_request(self, text: str) -> str:
        """处理一般请求"""
        text_lower = text.lower()
        
        # 检查是否是查询仲裁偏好的请求
        if any(keyword in text_lower for keyword in ["仲裁agent", "arbitration agent", "accepted_arbitration_agents", "仲裁偏好"]):
            # 返回商家接受的仲裁Agent列表（JSON格式）
            return json.dumps({
                "accepted_arbitration_agents": self.accepted_arbitration_agents
            }, ensure_ascii=False)
        
        return f"""🤖 商家 Agent 服务

我已收到您的请求: "{text}"

**支持的功能:**
1. 接收订单 - 发送订单信息（JSON格式或文本描述）
2. 查询订单 - "查询订单 [订单ID]" 或 "list orders"
3. 订单交付 - "交付订单 [订单ID]"
4. 订单管理 - 查看订单管理帮助

**示例:**
- "接收订单: 订单ID=ORDER001, 用户ID=user123, 金额=100 USD"
- "查询订单 ORDER001"
- "交付订单 ORDER001"
"""
    
    def handle_arbitration_notification(self, text: str) -> str:
        """
        处理仲裁通知
        
        接收仲裁Agent发送的通知，包括：
        - 裁定结果通知
        - 执行结果通知
        - 订单更新通知
        
        Args:
            text: 通知文本（可能是JSON格式或文本格式）
        
        Returns:
            响应文本（JSON格式或文本格式）
        """
        logger.info("⚖️ [MerchantAgent] 接收仲裁通知")
        
        try:
            # 尝试解析JSON格式的请求
            try:
                if "{" in text and "}" in text:
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    json_str = text[start:end]
                    request_data = json.loads(json_str)
                    request_type = request_data.get("type", "")
                    
                    if request_type == "update_order_arbitration":
                        # 更新订单仲裁信息
                        result = self._update_order_arbitration_info(request_data)
                        return json.dumps(result, ensure_ascii=False, indent=2)
                    else:
                        # 其他类型的JSON请求，作为通知处理
                        return json.dumps({
                            "success": True,
                            "status": "received",
                            "message": "仲裁通知已接收"
                        }, ensure_ascii=False, indent=2)
                else:
                    # 不是JSON格式，作为文本通知处理
                    return self._handle_text_arbitration_notification(text)
            
            except json.JSONDecodeError:
                # 解析JSON失败，作为文本通知处理
                return self._handle_text_arbitration_notification(text)
        
        except Exception as e:
            logger.error(f"❌ [MerchantAgent] 处理仲裁通知失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            return json.dumps({
                "success": False,
                "error": f"处理仲裁通知失败: {str(e)}"
            }, ensure_ascii=False, indent=2)
    
    def _handle_text_arbitration_notification(self, text: str) -> str:
        """
        处理文本格式的仲裁通知
        
        Args:
            text: 通知文本
        
        Returns:
            响应文本（JSON格式）
        """
        logger.info("📝 [MerchantAgent] 处理文本格式的仲裁通知")
        
        try:
            # 检查是否是裁定结果通知
            if "裁定结果" in text or "仲裁裁定" in text or "arbitration result" in text.lower():
                # 提取案例ID和订单ID
                import re
                case_id_match = re.search(r'案例[_\s]*ID[:\s]*([A-Za-z0-9_-]+)', text, re.IGNORECASE)
                if not case_id_match:
                    case_id_match = re.search(r'case[_\s]*id[:\s]*([A-Za-z0-9_-]+)', text, re.IGNORECASE)
                if not case_id_match:
                    case_id_match = re.search(r'ARB[_\-]?[A-Za-z0-9_]+', text, re.IGNORECASE)
                
                order_id_match = re.search(r'订单[_\s]*ID[:\s]*([A-Za-z0-9_-]+)', text, re.IGNORECASE)
                if not order_id_match:
                    order_id_match = re.search(r'order[_\s]*id[:\s]*([A-Za-z0-9_-]+)', text, re.IGNORECASE)
                
                case_id = case_id_match.group(1) if case_id_match else None
                order_id = order_id_match.group(1) if order_id_match else None
                
                if case_id:
                    # 自动确认裁定结果（默认同意）
                    # 可以从环境变量或配置中读取确认策略
                    auto_agree = os.getenv("MERCHANT_AUTO_AGREE_ARBITRATION", "true").lower() == "true"
                    
                    if auto_agree:
                        logger.info(f"✅ [MerchantAgent] 自动确认裁定结果: {case_id}")
                        confirm_result = self._confirm_arbitration_decision(case_id, True)
                        return json.dumps(confirm_result, ensure_ascii=False, indent=2)
                    else:
                        logger.info(f"ℹ️ [MerchantAgent] 需要人工确认裁定结果: {case_id}")
                        return json.dumps({
                            "success": True,
                            "status": "received",
                            "case_id": case_id,
                            "order_id": order_id,
                            "message": "裁定结果通知已接收，等待人工确认"
                        }, ensure_ascii=False, indent=2)
                else:
                    return json.dumps({
                        "success": True,
                        "status": "received",
                        "message": "裁定结果通知已接收，但无法提取案例ID"
                    }, ensure_ascii=False, indent=2)
            
            # 检查是否是执行结果通知
            elif "执行结果" in text or "仲裁结果已执行" in text or "execution result" in text.lower():
                # 提取案例ID和订单ID
                import re
                case_id_match = re.search(r'案例[_\s]*ID[:\s]*([A-Za-z0-9_-]+)', text, re.IGNORECASE)
                if not case_id_match:
                    case_id_match = re.search(r'case[_\s]*id[:\s]*([A-Za-z0-9_-]+)', text, re.IGNORECASE)
                if not case_id_match:
                    case_id_match = re.search(r'ARB[_\-]?[A-Za-z0-9_]+', text, re.IGNORECASE)
                
                order_id_match = re.search(r'订单[_\s]*ID[:\s]*([A-Za-z0-9_-]+)', text, re.IGNORECASE)
                if not order_id_match:
                    order_id_match = re.search(r'order[_\s]*id[:\s]*([A-Za-z0-9_-]+)', text, re.IGNORECASE)
                
                case_id = case_id_match.group(1) if case_id_match else None
                order_id = order_id_match.group(1) if order_id_match else None
                
                logger.info(f"✅ [MerchantAgent] 收到执行结果通知: case_id={case_id}, order_id={order_id}")
                
                return json.dumps({
                    "success": True,
                    "status": "received",
                    "case_id": case_id,
                    "order_id": order_id,
                    "message": "执行结果通知已接收"
                }, ensure_ascii=False, indent=2)
            
            # 其他类型的通知
            else:
                logger.info("ℹ️ [MerchantAgent] 收到其他类型的仲裁通知")
                return json.dumps({
                    "success": True,
                    "status": "received",
                    "message": "仲裁通知已接收"
                }, ensure_ascii=False, indent=2)
        
        except Exception as e:
            logger.error(f"❌ [MerchantAgent] 处理文本仲裁通知失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            return json.dumps({
                "success": False,
                "error": f"处理通知失败: {str(e)}"
            }, ensure_ascii=False, indent=2)
    
    def _update_order_arbitration_info(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新订单的仲裁信息
        
        Args:
            request_data: 包含订单更新信息的字典
        
        Returns:
            包含处理结果的字典
        """
        logger.info("📝 [MerchantAgent] 更新订单仲裁信息")
        
        try:
            order_id = request_data.get("order_id")
            if not order_id:
                return {
                    "success": False,
                    "error": "缺少必需字段: order_id"
                }
            
            # 检查订单是否存在
            if order_id not in self.orders:
                return {
                    "success": False,
                    "error": f"订单不存在: {order_id}"
                }
            
            order = self.orders[order_id]
            arbitration_result = request_data.get("arbitration_result", {})
            
            # 更新订单的仲裁信息
            if not order.arbitration_info:
                order.arbitration_info = ArbitrationInfo()
            
            # 更新仲裁信息字段
            if "case_id" in arbitration_result:
                order.arbitration_info.case_id = arbitration_result["case_id"]
            
            if "decision" in arbitration_result:
                order.arbitration_info.decision = arbitration_result["decision"]
            
            if "decision_reason" in arbitration_result:
                # decision_reason 不在 ArbitrationInfo 数据类中，可以在 metadata 中存储
                if not order.metadata:
                    order.metadata = {}
                order.metadata["arbitration_decision_reason"] = arbitration_result["decision_reason"]
            
            if "responsible_party" in arbitration_result:
                order.arbitration_info.responsible_party = arbitration_result["responsible_party"]
            
            if "status" in arbitration_result:
                order.arbitration_info.status = arbitration_result["status"]
            
            # 更新订单的更新时间
            order.updated_at = datetime.now().isoformat()
            
            logger.info(f"✅ [MerchantAgent] 订单 {order_id} 的仲裁信息已更新")
            logger.info(f"   裁定结果: {arbitration_result.get('decision')}")
            logger.info(f"   责任方: {arbitration_result.get('responsible_party')}")
            logger.info(f"   状态: {arbitration_result.get('status')}")
            
            return {
                "success": True,
                "order_id": order_id,
                "message": "订单仲裁信息已更新",
                "arbitration_info": {
                    "decision": arbitration_result.get("decision"),
                    "responsible_party": arbitration_result.get("responsible_party"),
                    "status": arbitration_result.get("status")
                }
            }
        
        except Exception as e:
            logger.error(f"❌ [MerchantAgent] 更新订单仲裁信息失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "error": f"更新订单仲裁信息失败: {str(e)}"
            }
    
    def _confirm_arbitration_decision(self, case_id: str, agreed: bool) -> Dict[str, Any]:
        """
        确认裁定结果
        
        Args:
            case_id: 仲裁案例ID
            agreed: 是否同意（True表示同意，False表示不同意）
        
        Returns:
            包含确认结果的字典
        """
        logger.info(f"✅ [MerchantAgent] 确认裁定结果: case_id={case_id}, agreed={agreed}")
        
        try:
            # 从订单中获取仲裁Agent URL
            # 这里需要从订单的仲裁信息中获取，或者从环境变量获取
            arbitration_agent_url = os.getenv("ARBITRATION_AGENT_URL", "http://localhost:5025")
            
            # 通过搜索订单找到包含此案例的订单
            order_with_case = None
            for order in self.orders.values():
                # 从 arbitration_info 或 metadata 中查找案例ID
                case_id_match = False
                if order.arbitration_info and order.arbitration_info.case_id == case_id:
                    case_id_match = True
                    # 从 arbitration_info 中获取仲裁Agent URL
                    if order.arbitration_info.arbitration_agent_url:
                        arbitration_agent_url = order.arbitration_info.arbitration_agent_url
                elif order.metadata and order.metadata.get("arbitration_case_id") == case_id:
                    case_id_match = True
                    # 如果有 arbitration_info，从中获取仲裁Agent URL
                    if order.arbitration_info and order.arbitration_info.arbitration_agent_url:
                        arbitration_agent_url = order.arbitration_info.arbitration_agent_url
                
                if case_id_match:
                    order_with_case = order
                    break
            
            if not order_with_case:
                logger.warning(f"⚠️ [MerchantAgent] 未找到包含案例 {case_id} 的订单，使用默认仲裁Agent URL")
            
            # 调用仲裁Agent的 confirm_decision 方法
            try:
                arbitration_client = A2AClient(arbitration_agent_url)
                
                confirm_request = {
                    "type": "confirm_decision",
                    "case_id": case_id,
                    "party": "merchant",
                    "agreed": agreed
                }
                
                request_text = json.dumps(confirm_request, ensure_ascii=False)
                response = arbitration_client.ask(request_text)
                
                # 解析响应
                try:
                    if "{" in response and "}" in response:
                        start = response.find("{")
                        end = response.rfind("}") + 1
                        json_str = response[start:end]
                        result = json.loads(json_str)
                        
                        if result.get("success"):
                            logger.info(f"✅ [MerchantAgent] 确认结果已发送到仲裁Agent: {case_id}")
                            
                            # 如果确认成功，更新本地订单状态
                            if order_with_case and order_with_case.arbitration_info:
                                if agreed:
                                    order_with_case.arbitration_info.status = "agreed"
                                    logger.info(f"📝 [MerchantAgent] 订单 {order_with_case.order_id} 的仲裁状态已更新为: agreed")
                                else:
                                    order_with_case.arbitration_info.status = "escalated"
                                    logger.info(f"📝 [MerchantAgent] 订单 {order_with_case.order_id} 的仲裁状态已更新为: escalated")
                            
                            return {
                                "success": True,
                                "case_id": case_id,
                                "agreed": agreed,
                                "message": f"确认结果已发送: {'同意' if agreed else '不同意'}",
                                "arbitration_response": result
                            }
                        else:
                            error_msg = result.get("error", "未知错误")
                            logger.error(f"❌ [MerchantAgent] 确认失败: {error_msg}")
                            return {
                                "success": False,
                                "error": error_msg,
                                "arbitration_response": result
                            }
                    else:
                        # 文本响应，认为成功
                        logger.info(f"✅ [MerchantAgent] 确认结果已发送（文本响应）")
                        return {
                            "success": True,
                            "case_id": case_id,
                            "agreed": agreed,
                            "message": f"确认结果已发送: {'同意' if agreed else '不同意'}",
                            "raw_response": response
                        }
                
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"⚠️ [MerchantAgent] 解析仲裁Agent响应失败: {e}")
                    return {
                        "success": False,
                        "error": f"解析响应失败: {str(e)}",
                        "raw_response": response
                    }
            
            except Exception as e:
                logger.error(f"❌ [MerchantAgent] 调用仲裁Agent失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                
                return {
                    "success": False,
                    "error": f"调用仲裁Agent失败: {str(e)}"
                }
        
        except Exception as e:
            logger.error(f"❌ [MerchantAgent] 确认裁定结果失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "error": f"确认裁定结果失败: {str(e)}",
                "case_id": case_id
            }
    
    def _parse_order_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中解析订单信息"""
        order_data = {}
        
        try:
            # 尝试解析JSON格式
            if "{" in text and "}" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                json_str = text[start:end]
                order_data = json.loads(json_str)
                return order_data
        except:
            pass
        
        # 如果不是JSON，尝试从文本中提取关键信息
        import re
        
        # 提取订单ID
        order_id_match = re.search(r'订单[_\s]*ID[:\s]*([A-Za-z0-9_]+)', text, re.IGNORECASE)
        if not order_id_match:
            order_id_match = re.search(r'order[_\s]*id[:\s]*([A-Za-z0-9_]+)', text, re.IGNORECASE)
        if order_id_match:
            order_data["order_id"] = order_id_match.group(1)
        
        # 提取用户ID
        user_id_match = re.search(r'用户[_\s]*ID[:\s]*([A-Za-z0-9_]+)', text, re.IGNORECASE)
        if not user_id_match:
            user_id_match = re.search(r'user[_\s]*id[:\s]*([A-Za-z0-9_]+)', text, re.IGNORECASE)
        if user_id_match:
            order_data["user_id"] = user_id_match.group(1)
        
        # 提取金额
        amount_match = re.search(r'金额[:\s]*([0-9.]+)', text, re.IGNORECASE)
        if not amount_match:
            amount_match = re.search(r'amount[:\s]*([0-9.]+)', text, re.IGNORECASE)
        if amount_match:
            order_data["amount"] = float(amount_match.group(1))
        
        # 提取货币
        currency_match = re.search(r'货币[:\s]*([A-Z]+)', text, re.IGNORECASE)
        if not currency_match:
            currency_match = re.search(r'currency[:\s]*([A-Z]+)', text, re.IGNORECASE)
        if currency_match:
            order_data["currency"] = currency_match.group(1)
        
        # 尝试提取商品信息
        product_match = re.search(r'商品[:\s]*([^\n,]+)', text, re.IGNORECASE)
        if not product_match:
            product_match = re.search(r'product[:\s]*([^\n,]+)', text, re.IGNORECASE)
        if product_match:
            order_data["product_info"] = {"name": product_match.group(1).strip()}
        
        return order_data
    
    def _validate_order(self, order_data: Dict[str, Any]) -> bool:
        """验证订单数据的完整性（简单验证，保持向后兼容）"""
        validation_result = self._validate_order_comprehensive(order_data)
        return validation_result["valid"]
    
    def _validate_order_comprehensive(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        全面验证订单数据
        
        Args:
            order_data: 订单数据字典
            
        Returns:
            验证结果字典，包含 valid, error, errors 字段
        """
        errors = []
        
        # 1. 验证用户ID（必需）
        user_id = order_data.get("user_id")
        if not user_id or not str(user_id).strip():
            errors.append("用户ID(user_id)是必需的，不能为空")
        elif len(str(user_id).strip()) < 1:
            errors.append("用户ID(user_id)格式无效")
        
        # 2. 验证金额（必需且必须为正数）
        amount = order_data.get("amount")
        if amount is None:
            errors.append("订单金额(amount)是必需的")
        else:
            try:
                amount = float(amount)
                if amount <= 0:
                    errors.append(f"订单金额必须大于0，当前值: {amount}")
                elif amount > 1000000:  # 设置一个合理的上限
                    errors.append(f"订单金额过大: {amount}，超过最大限制1000000")
            except (ValueError, TypeError):
                errors.append(f"订单金额格式无效: {amount}")
        
        # 3. 验证商品信息
        product_info = order_data.get("product_info")
        if not product_info:
            errors.append("商品信息(product_info)是必需的")
        elif isinstance(product_info, dict):
            # 验证商品名称
            product_name = product_info.get("product_name") or product_info.get("name")
            if not product_name or not str(product_name).strip():
                errors.append("商品名称是必需的")
            
            # 验证数量
            quantity = product_info.get("quantity", 1)
            try:
                quantity = int(quantity)
                if quantity <= 0:
                    errors.append(f"商品数量必须大于0，当前值: {quantity}")
                elif quantity > 10000:  # 设置一个合理的上限
                    errors.append(f"商品数量过大: {quantity}，超过最大限制10000")
            except (ValueError, TypeError):
                errors.append(f"商品数量格式无效: {quantity}")
            
            # 验证单价
            unit_price = product_info.get("unit_price") or product_info.get("price")
            if unit_price is not None:
                try:
                    unit_price = float(unit_price)
                    if unit_price < 0:
                        errors.append(f"商品单价不能为负数，当前值: {unit_price}")
                except (ValueError, TypeError):
                    errors.append(f"商品单价格式无效: {unit_price}")
            
            # 验证金额一致性（如果同时提供了总金额和单价*数量）
            if amount is not None and unit_price is not None and quantity is not None:
                try:
                    calculated_amount = float(unit_price) * int(quantity)
                    if abs(float(amount) - calculated_amount) > 0.01:
                        logger.warning(f"⚠️ 金额不一致: 订单金额={amount}, 计算金额={calculated_amount}")
                        # 这里只记录警告，不阻止订单创建
                except (ValueError, TypeError):
                    pass
        
        # 4. 验证货币（如果提供）
        currency = order_data.get("currency", "USD")
        if currency and len(str(currency)) != 3:
            errors.append(f"货币代码格式无效: {currency}，应为3位字母（如USD）")
        
        # 5. 验证支付信息（如果提供）
        payment_info = order_data.get("payment_info")
        if payment_info and isinstance(payment_info, dict):
            payment_amount = payment_info.get("payment_amount")
            if payment_amount is not None:
                try:
                    payment_amount = float(payment_amount)
                    if payment_amount < 0:
                        errors.append(f"支付金额不能为负数，当前值: {payment_amount}")
                except (ValueError, TypeError):
                    errors.append(f"支付金额格式无效: {payment_amount}")
        
        # 返回验证结果
        if errors:
            return {
                "valid": False,
                "error": "订单验证失败",
                "errors": errors
            }
        else:
            return {
                "valid": True,
                "error": None,
                "errors": []
            }
    
    def _accept_order(self, order_id: str) -> Dict[str, Any]:
        """
        接单：将订单状态从 PENDING 更新为 ACCEPTED
        
        Args:
            order_id: 订单ID
            
        Returns:
            包含处理结果的字典
        """
        if order_id not in self.orders:
            return {
                "success": False,
                "error": f"订单不存在: {order_id}"
            }
        
        order = self.orders[order_id]
        
        # 检查订单状态
        if order.status != OrderStatus.PENDING:
            return {
                "success": False,
                "error": f"订单状态不允许接单，当前状态: {order.status.value}",
                "current_status": order.status.value
            }
        
        # 保存旧状态
        old_status = order.status.value
        
        # 更新订单状态
        order.status = OrderStatus.ACCEPTED
        order.accepted_at = datetime.now().isoformat()
        order.updated_at = datetime.now().isoformat()
        
        logger.info(f"✅ [MerchantAgent] 订单已接单: {order_id}")
        
        # 发送订单接单通知
        try:
            if WEBSOCKET_NOTIFICATION_AVAILABLE:
                order_dict = order.to_dict()
                notification = create_order_status_update_message(
                    order_id=order_id,
                    new_status=order.status.value,
                    old_status=old_status,
                    order_data=order_dict,
                    status_display=self.ORDER_STATUS_DISPLAY.get(order.status.value, order.status.value),
                    user_id=order.user_info.user_id
                )
                self._send_websocket_notification(notification)
        except Exception as e:
            logger.warning(f"⚠️ [MerchantAgent] 发送订单接单通知失败: {e}")
        
        return {
            "success": True,
            "message": "订单已成功接单",
            "order_id": order_id,
            "status": order.status.value,
            "accepted_at": order.accepted_at
        }
    
    def _complete_order(self, order_id: str) -> Dict[str, Any]:
        """
        完成订单：将订单状态从 DELIVERED 更新为 COMPLETED
        
        Args:
            order_id: 订单ID
            
        Returns:
            包含处理结果的字典
        """
        if order_id not in self.orders:
            return {
                "success": False,
                "error": f"订单不存在: {order_id}"
            }
        
        order = self.orders[order_id]
        
        # 检查订单状态
        if order.status != OrderStatus.DELIVERED:
            return {
                "success": False,
                "error": f"订单状态不允许完成，当前状态: {order.status.value}，只有已交付(DELIVERED)的订单才能完成",
                "current_status": order.status.value
            }
        
        # 保存旧状态
        old_status = order.status.value
        
        # 更新订单状态
        order.status = OrderStatus.COMPLETED
        order.completed_at = datetime.now().isoformat()
        order.updated_at = datetime.now().isoformat()
        
        logger.info(f"✅ [MerchantAgent] 订单已完成: {order_id}")
        
        # 发送订单完成通知
        try:
            if WEBSOCKET_NOTIFICATION_AVAILABLE:
                order_dict = order.to_dict()
                notification = create_order_status_update_message(
                    order_id=order_id,
                    new_status=order.status.value,
                    old_status=old_status,
                    order_data=order_dict,
                    status_display=self.ORDER_STATUS_DISPLAY.get(order.status.value, order.status.value),
                    user_id=order.user_info.user_id
                )
                self._send_websocket_notification(notification)
        except Exception as e:
            logger.warning(f"⚠️ [MerchantAgent] 发送订单完成通知失败: {e}")
        
        return {
            "success": True,
            "message": "订单已成功完成",
            "order_id": order_id,
            "status": order.status.value,
            "completed_at": order.completed_at
        }
    
    def _handle_order_completion(self, text: str) -> str:
        """处理订单完成请求"""
        logger.info("✅ [MerchantAgent] 处理订单完成请求")
        
        try:
            # 提取订单ID
            order_id = self._extract_order_id_from_text(text)
            
            if not order_id or order_id not in self.orders:
                return "❌ 未找到指定的订单。请提供有效的订单ID。"
            
            order = self.orders[order_id]
            
            # 检查订单状态
            if order.status == OrderStatus.COMPLETED:
                status_display = self.ORDER_STATUS_DISPLAY.get(order.status.value, order.status.value)
                return f"ℹ️ 订单 {order_id} 已经完成，当前状态: {status_display}"
            
            if order.status != OrderStatus.DELIVERED:
                status_display = self.ORDER_STATUS_DISPLAY.get(order.status.value, order.status.value)
                return f"❌ 订单 {order_id} 当前状态为 {status_display}，只有已交付(DELIVERED)的订单才能完成。"
            
            # 调用完成订单方法
            complete_result = self._complete_order(order_id)
            
            if not complete_result["success"]:
                return f"❌ 订单完成失败: {complete_result.get('error', '未知错误')}"
            
            # 重新获取更新后的订单
            order = self.orders[order_id]
            
            # 调用上链功能存储订单完成信息
            blockchain_result = None
            blockchain_info = ""
            try:
                blockchain_result = self._store_order_on_chain(order, status="completed")
                if blockchain_result and blockchain_result.get("success"):
                    completion_tx_hash = blockchain_result.get("tx_hash")
                    # 将完成交易哈希保存到订单元数据中
                    if completion_tx_hash:
                        if "blockchain_tx_hashes" not in order.metadata:
                            order.metadata["blockchain_tx_hashes"] = {}
                        order.metadata["blockchain_tx_hashes"]["completed"] = completion_tx_hash
                    
                    blockchain_info = f"\n- ✅ 订单完成信息已上链，交易哈希: {completion_tx_hash[:16] if completion_tx_hash else 'N/A'}..."
                    logger.info(f"✅ [MerchantAgent] 订单完成信息已上链: {order_id}, 交易哈希: {completion_tx_hash}")
                else:
                    error_msg = blockchain_result.get("error", "未知错误") if blockchain_result else "区块链服务不可用"
                    blockchain_info = f"\n- ⚠️ 订单完成信息上链失败: {error_msg}"
                    logger.warning(f"⚠️ [MerchantAgent] 订单完成信息上链失败: {order_id}, 错误: {error_msg}")
            except Exception as e:
                logger.error(f"❌ [MerchantAgent] 上链处理异常: {e}")
                import traceback
                logger.error(traceback.format_exc())
                blockchain_info = f"\n- ⚠️ 上链处理异常: {str(e)}"
            
            status_display = self.ORDER_STATUS_DISPLAY.get(order.status.value, order.status.value)
            
            return f"""✅ 订单已完成！

**订单信息:**
- 订单ID: {order_id}
- 状态: {status_display} ({order.status.value})
- 完成时间: {order.completed_at}
- 交付时间: {order.delivered_at or 'N/A'}
- 接单时间: {order.accepted_at or 'N/A'}{blockchain_info}

订单已标记为已完成，交易流程结束。"""
            
        except Exception as e:
            logger.error(f"❌ 处理订单完成失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"❌ 订单完成失败: {str(e)}"
    
    def _extract_order_id_from_text(self, text: str) -> Optional[str]:
        """从文本中提取订单ID"""
        import re
        
        # 尝试多种格式匹配订单ID
        patterns = [
            r'订单[_\s]*ID[:\s]*([A-Za-z0-9_]+)',
            r'order[_\s]*id[:\s]*([A-Za-z0-9_]+)',
            r'ORDER[_\s]*([A-Za-z0-9_]+)',
            r'订单[:\s]*([A-Za-z0-9_]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # 如果没找到，尝试查找类似ORDER_xxx的格式
        order_match = re.search(r'([A-Z]+[_\s]?[0-9A-Z_]+)', text, re.IGNORECASE)
        if order_match:
            potential_id = order_match.group(1).replace(" ", "_").upper()
            if potential_id in self.orders:
                return potential_id
        
        return None
    
    def _parse_delivery_info_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中解析交付信息"""
        delivery_info = {}
        
        import re
        
        # 提取交付方式
        delivery_method_match = re.search(r'交付方式[:\s]*([^\n,]+)', text, re.IGNORECASE)
        if not delivery_method_match:
            delivery_method_match = re.search(r'delivery[_\s]*method[:\s]*([^\n,]+)', text, re.IGNORECASE)
        if delivery_method_match:
            delivery_info["delivery_method"] = delivery_method_match.group(1).strip()
        
        # 提取追踪号
        tracking_match = re.search(r'追踪号[:\s]*([A-Za-z0-9]+)', text, re.IGNORECASE)
        if not tracking_match:
            tracking_match = re.search(r'tracking[_\s]*number[:\s]*([A-Za-z0-9]+)', text, re.IGNORECASE)
        if tracking_match:
            delivery_info["tracking_number"] = tracking_match.group(1).strip()
        
        return delivery_info
    
    def _validate_delivery_info(
        self,
        order: Order,
        delivery_info: Optional[DeliveryInfo],
        delivered_at: str
    ) -> Dict[str, Any]:
        """
        验证交付信息
        
        Args:
            order: 订单对象
            delivery_info: 交付信息对象
            delivered_at: 交付时间（ISO格式字符串）
            
        Returns:
            验证结果字典，包含 valid, error, errors 字段
        """
        errors = []
        
        # 1. 验证交付时间（不能早于接单时间）
        try:
            delivered_time = datetime.fromisoformat(delivered_at.replace('Z', '+00:00') if 'Z' in delivered_at else delivered_at)
            
            # 如果有接单时间，验证交付时间不能早于接单时间
            if order.accepted_at:
                try:
                    accepted_time = datetime.fromisoformat(
                        order.accepted_at.replace('Z', '+00:00') if 'Z' in order.accepted_at else order.accepted_at
                    )
                    if delivered_time < accepted_time:
                        errors.append(f"交付时间({delivered_at})不能早于接单时间({order.accepted_at})")
                except ValueError:
                    logger.warning(f"⚠️ 无法解析接单时间: {order.accepted_at}")
            
            # 验证交付时间不能早于订单创建时间
            if order.created_at:
                try:
                    created_time = datetime.fromisoformat(
                        order.created_at.replace('Z', '+00:00') if 'Z' in order.created_at else order.created_at
                    )
                    if delivered_time < created_time:
                        errors.append(f"交付时间({delivered_at})不能早于订单创建时间({order.created_at})")
                except ValueError:
                    logger.warning(f"⚠️ 无法解析订单创建时间: {order.created_at}")
            
            # 验证交付时间不能是未来时间（允许最多5分钟的误差）
            now = datetime.now()
            if delivered_time > now:
                time_diff = (delivered_time - now).total_seconds()
                if time_diff > 300:  # 5分钟 = 300秒
                    errors.append(f"交付时间({delivered_at})不能是未来时间（超过5分钟）")
                else:
                    logger.info(f"ℹ️ 交付时间略早于当前时间（{time_diff:.0f}秒），允许通过")
                    
        except ValueError as e:
            errors.append(f"交付时间格式无效: {delivered_at}，错误: {str(e)}")
        except Exception as e:
            errors.append(f"验证交付时间时出错: {str(e)}")
        
        # 2. 验证交付方式（必填）
        if not delivery_info:
            errors.append("交付信息(delivery_info)是必需的")
        else:
            delivery_method = delivery_info.delivery_method
            if not delivery_method or not str(delivery_method).strip():
                errors.append("交付方式(delivery_method)是必需的，不能为空")
            elif len(str(delivery_method).strip()) < 2:
                errors.append(f"交付方式格式无效: {delivery_method}，长度至少为2个字符")
            
            # 3. 验证物流追踪号格式（如果提供）
            tracking_number = delivery_info.tracking_number
            if tracking_number:
                tracking_str = str(tracking_number).strip()
                # 物流追踪号应该至少包含3个字符（字母或数字）
                if len(tracking_str) < 3:
                    errors.append(f"物流追踪号格式无效: {tracking_number}，长度至少为3个字符")
                elif len(tracking_str) > 50:
                    errors.append(f"物流追踪号格式无效: {tracking_number}，长度不能超过50个字符")
                # 验证追踪号只能包含字母、数字、连字符和下划线
                import re
                if not re.match(r'^[A-Za-z0-9_-]+$', tracking_str):
                    errors.append(f"物流追踪号格式无效: {tracking_number}，只能包含字母、数字、连字符(-)和下划线(_)")
        
        # 返回验证结果
        if errors:
            return {
                "valid": False,
                "error": "交付信息验证失败",
                "errors": errors
            }
        else:
            return {
                "valid": True,
                "error": None,
                "errors": []
            }
    
    def _generate_delivery_proof(self, order: Order) -> Dict[str, Any]:
        """
        生成交付凭证
        
        使用订单ID + 交付时间 + 交付信息生成哈希作为交付凭证
        
        Args:
            order: 订单对象
            
        Returns:
            包含交付凭证信息的字典，包含 proof_hash, proof_data 等字段
        """
        try:
            # 检查订单是否已交付
            if order.status != OrderStatus.DELIVERED or not order.delivered_at:
                logger.warning(f"⚠️ 订单 {order.order_id} 尚未交付，无法生成交付凭证")
                return {
                    "success": False,
                    "error": "订单尚未交付，无法生成交付凭证"
                }
            
            # 构建交付凭证数据
            delivery_data = {
                "order_id": order.order_id,
                "delivered_at": order.delivered_at,
                "delivery_info": asdict(order.delivery_info) if order.delivery_info else {},
                "amount": order.amount,
                "currency": order.currency
            }
            
            # 将交付数据序列化为JSON字符串（确保排序一致）
            proof_data_str = json.dumps(delivery_data, sort_keys=True, ensure_ascii=False)
            
            # 生成SHA256哈希
            proof_hash = hashlib.sha256(proof_data_str.encode('utf-8')).hexdigest()
            
            logger.info(f"✅ [MerchantAgent] 生成交付凭证: 订单 {order.order_id}, 哈希: {proof_hash[:16]}...")
            
            return {
                "success": True,
                "proof_hash": proof_hash,
                "proof_data": delivery_data,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 生成交付凭证失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": f"生成交付凭证失败: {str(e)}"
            }
    
    def _notify_user_agent_delivery(
        self,
        order: Order,
        delivery_proof: Dict[str, Any],
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        通知用户 Agent 交付完成
        
        使用 A2AClient 调用用户 Agent，发送交付完成通知（包含订单ID、交付时间、交付凭证）
        包含错误处理和重试机制
        
        Args:
            order: 订单对象
            delivery_proof: 交付凭证字典（由 _generate_delivery_proof 生成）
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            
        Returns:
            包含通知结果的字典，包含 success, message 等字段
        """
        # 检查是否有用户 Agent URL
        if not order.user_agent_url:
            logger.warning(f"⚠️ [MerchantAgent] 订单 {order.order_id} 没有用户 Agent URL，无法发送交付通知")
            return {
                "success": False,
                "error": "订单中没有用户 Agent URL，无法发送交付通知"
            }
        
        # 检查交付凭证是否有效
        if not delivery_proof.get("success"):
            logger.warning(f"⚠️ [MerchantAgent] 订单 {order.order_id} 交付凭证生成失败，无法发送交付通知")
            return {
                "success": False,
                "error": f"交付凭证无效: {delivery_proof.get('error', '未知错误')}"
            }
        
        user_agent_url = order.user_agent_url
        logger.info(f"📤 [MerchantAgent] 准备通知用户 Agent 交付完成: {user_agent_url}")
        
        # 构建交付通知消息
        delivery_notification = {
            "type": "delivery_completed",
            "order_id": order.order_id,
            "delivered_at": order.delivered_at,
            "delivery_proof": {
                "proof_hash": delivery_proof.get("proof_hash"),
                "proof_data": delivery_proof.get("proof_data"),
                "generated_at": delivery_proof.get("generated_at")
            },
            "delivery_info": asdict(order.delivery_info) if order.delivery_info else {},
            "order_summary": {
                "product_name": order.product_info.product_name,
                "quantity": order.product_info.quantity,
                "amount": order.amount,
                "currency": order.currency
            }
        }
        
        # 将通知消息格式化为文本（JSON格式）
        notification_json = json.dumps(delivery_notification, ensure_ascii=False, indent=2)
        notification_text = f"""订单交付完成通知：

{notification_json}

订单 {order.order_id} 已成功交付，请确认收货。"""
        
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔄 [MerchantAgent] 尝试通知用户 Agent (第 {attempt}/{max_retries} 次)")
                
                # 使用 A2AClient 连接用户 Agent
                user_agent_client = A2AClient(user_agent_url)
                
                # 发送交付通知
                response = user_agent_client.ask(notification_text)
                
                logger.info(f"📥 [MerchantAgent] 收到用户 Agent 响应: {response[:200] if response else 'None'}...")
                
                # 尝试解析响应（可能是 JSON 格式或文本格式）
                try:
                    # 尝试解析 JSON 格式的响应
                    if "{" in response and "}" in response:
                        start = response.find("{")
                        end = response.rfind("}") + 1
                        json_str = response[start:end]
                        parsed_response = json.loads(json_str)
                        
                        if parsed_response.get("success") or parsed_response.get("status") == "received":
                            logger.info(f"✅ [MerchantAgent] 用户 Agent 成功接收交付通知: {order.order_id}")
                            return {
                                "success": True,
                                "message": "交付通知已成功发送至用户 Agent",
                                "order_id": order.order_id,
                                "user_agent_response": parsed_response
                            }
                        else:
                            error_msg = parsed_response.get("error", "未知错误")
                            logger.warning(f"⚠️ [MerchantAgent] 用户 Agent 返回错误: {error_msg}")
                            last_error = error_msg
                except (json.JSONDecodeError, KeyError) as e:
                    # 如果不是 JSON 格式，检查文本响应
                    if any(keyword in response.lower() for keyword in ["成功", "收到", "确认", "success", "received", "confirmed"]):
                        logger.info(f"✅ [MerchantAgent] 用户 Agent 成功接收交付通知（文本格式响应）")
                        return {
                            "success": True,
                            "message": "交付通知已成功发送至用户 Agent",
                            "order_id": order.order_id,
                            "user_agent_response": response
                        }
                    else:
                        logger.warning(f"⚠️ [MerchantAgent] 用户 Agent 响应格式异常: {response[:100]}")
                        last_error = f"响应格式异常: {response[:100]}"
                
                # 如果成功但没有明确的成功标识，也认为是成功的（避免误判）
                if attempt == max_retries:
                    logger.info(f"✅ [MerchantAgent] 用户 Agent 响应收到，视为成功")
                    return {
                        "success": True,
                        "message": "交付通知已发送至用户 Agent（响应已收到）",
                        "order_id": order.order_id,
                        "user_agent_response": response
                    }
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ [MerchantAgent] 通知用户 Agent 失败 (第 {attempt}/{max_retries} 次): {e}")
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries:
                    logger.info(f"⏳ [MerchantAgent] 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    # 指数退避：每次重试延迟时间翻倍
                    retry_delay *= 2
                else:
                    logger.error(f"❌ [MerchantAgent] 通知用户 Agent 失败，已达到最大重试次数")
        
        # 所有重试都失败
        error_message = f"通知用户 Agent 失败（已重试 {max_retries} 次）"
        if last_error:
            error_message += f": {last_error}"
        
        logger.error(f"❌ [MerchantAgent] {error_message}")
        
        return {
            "success": False,
            "error": error_message,
            "last_error": last_error,
            "user_agent_url": user_agent_url,
            "order_id": order.order_id
        }
    
    def _store_order_on_chain(
        self,
        order: Order,
        status: str = "paid"
    ) -> Dict[str, Any]:
        """
        将订单信息存储到链上
        
        Args:
            order: 订单对象
            status: 订单状态 ("paid", "delivered", "completed")
            
        Returns:
            包含上链结果的字典
        """
        if not self.blockchain_service:
            return {
                "success": False,
                "error": "区块链服务不可用"
            }
        
        try:
            # 从订单中提取支付交易哈希
            payment_tx_hash = ""
            if order.payment_info and order.payment_info.payment_transaction_hash:
                payment_tx_hash = order.payment_info.payment_transaction_hash
            
            # 从订单元数据中提取交付交易哈希（如果存在）
            delivery_tx_hash = None
            if order.metadata and "blockchain_tx_hashes" in order.metadata:
                delivery_tx_hash = order.metadata["blockchain_tx_hashes"].get("delivery")
            
            # 创建上链交易数据
            transaction_data = self.blockchain_service.create_transaction_data_from_order(
                order=order,
                payment_tx_hash=payment_tx_hash if payment_tx_hash else None,
                delivery_tx_hash=delivery_tx_hash,  # 从订单元数据中获取交付交易哈希
                status=status
            )
            
            # 调用上链服务
            result = self.blockchain_service.store_transaction_on_chain(transaction_data)
            
            if result.get("success"):
                logger.info(f"✅ [MerchantAgent] 订单信息已成功上链: {order.order_id}")
                
                # 发送上链成功通知
                try:
                    if WEBSOCKET_NOTIFICATION_AVAILABLE:
                        tx_hash = result.get("tx_hash", "")
                        block_number = result.get("block_number")
                        data_hash = result.get("data_hash")
                        
                        # 构建区块链浏览器链接（IoTeX 测试网）
                        explorer_url = None
                        if tx_hash:
                            # IoTeX 测试网浏览器
                            explorer_url = f"https://testnet.iotexscan.io/tx/{tx_hash}"
                        
                        # 获取钱包地址（如果有）
                        from_address = None
                        to_address = None
                        if self.blockchain_service and self.blockchain_service.merchant_address:
                            from_address = self.blockchain_service.merchant_address
                        if order.user_info and order.user_info.user_wallet_address:
                            to_address = order.user_info.user_wallet_address
                        
                        # 使用 websocket_messages.py 中的辅助函数创建消息
                        blockchain_notification = create_blockchain_transaction_message(
                            order_id=order.order_id,
                            tx_hash=tx_hash,
                            transaction_type=status,  # "paid", "delivered", "completed"
                            status="confirmed",
                            block_number=block_number,
                            data_hash=data_hash,
                            timestamp=datetime.now().isoformat(),
                            from_address=from_address,
                            to_address=to_address,
                            amount=order.amount,
                            currency=order.currency,
                            explorer_url=explorer_url,
                            user_id=order.user_info.user_id
                        )
                        
                        # 调用 WebSocket 服务器的 send_message() 发送
                        self._send_websocket_notification(blockchain_notification)
                        logger.debug(f"📤 [MerchantAgent] 上链成功通知已发送: {order.order_id}, 交易类型: {status}, 交易哈希: {tx_hash[:16] if tx_hash else 'N/A'}...")
                except Exception as e:
                    logger.warning(f"⚠️ [MerchantAgent] 发送上链成功通知失败: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
            else:
                logger.warning(f"⚠️ [MerchantAgent] 订单信息上链失败: {order.order_id}, 错误: {result.get('error', '未知错误')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [MerchantAgent] 上链处理异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": f"上链处理异常: {str(e)}"
            }


def main():
    """主函数，用于配置和启动商家 Agent 服务器"""
    port = int(os.environ.get("MERCHANT_A2A_PORT", 5020))
    
    agent_card = AgentCard(
        name="Merchant A2A Agent",
        description="An A2A agent that handles order receiving, delivery processing, and order management for merchants.",
        url=f"http://localhost:{port}",
        skills=[
            AgentSkill(
                name="receive_order",
                description="Receive and accept new orders from user agents. Validates order information and automatically accepts valid orders."
            ),
            AgentSkill(
                name="order_delivery",
                description="Process order delivery. Update order status to delivered and manage delivery information."
            ),
            AgentSkill(
                name="order_management",
                description="Query order status, list all orders, and manage order information."
            )
        ]
    )
    
    server = MerchantAgent(agent_card)
    
    print("\n" + "="*60)
    print("🚀 Starting Merchant A2A Server...")
    print(f"👂 Listening on http://localhost:{port}")
    print("📋 功能特性:")
    print("   - 接收订单和自动接单")
    print("   - 订单查询和管理")
    print("   - 订单交付处理")
    print("   - A2A协议兼容")
    print("="*60 + "\n")
    
    run_server(server, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

