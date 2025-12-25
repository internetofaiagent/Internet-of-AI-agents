#!/usr/bin/env python3
"""
WebSocket 消息格式定义
用于前后端通信的消息协议
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
import json


# ==============================================================================
#  消息类型枚举
# ==============================================================================

class WebSocketMessageType(str, Enum):
    """WebSocket 消息类型"""
    ORDER_STATUS_UPDATE = "order_status_update"      # 订单状态变更
    AGENT_CONNECTION = "agent_connection"            # Agent连接状态
    BLOCKCHAIN_TRANSACTION = "blockchain_transaction" # 链上交易确认
    DELIVERY_NOTIFICATION = "delivery_notification"  # 交付通知
    HEARTBEAT = "heartbeat"                          # 心跳消息
    ERROR = "error"                                  # 错误消息


# ==============================================================================
#  基础消息结构
# ==============================================================================

@dataclass
class WebSocketMessage:
    """WebSocket 消息基础结构"""
    message_type: str  # 消息类型
    timestamp: str  # 消息时间戳（ISO格式）
    data: Dict[str, Any]  # 消息数据
    user_id: Optional[str] = None  # 用户ID（可选，用于消息路由）
    order_id: Optional[str] = None  # 订单ID（可选，用于订单相关消息）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebSocketMessage":
        """从字典创建消息对象"""
        return cls(**data)


# ==============================================================================
#  订单状态更新消息
# ==============================================================================

@dataclass
class OrderStatusUpdateData:
    """订单状态更新消息数据"""
    order_id: str
    old_status: Optional[str] = None  # 旧状态
    new_status: str  # 新状态
    order_data: Optional[Dict[str, Any]] = None  # 完整订单数据（可选）
    status_display: Optional[str] = None  # 状态显示文本
    updated_at: Optional[str] = None  # 更新时间
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def create_order_status_update_message(
    order_id: str,
    new_status: str,
    old_status: Optional[str] = None,
    order_data: Optional[Dict[str, Any]] = None,
    status_display: Optional[str] = None,
    user_id: Optional[str] = None
) -> WebSocketMessage:
    """
    创建订单状态更新消息
    
    Args:
        order_id: 订单ID
        new_status: 新状态
        old_status: 旧状态（可选）
        order_data: 完整订单数据（可选）
        status_display: 状态显示文本（可选）
        user_id: 用户ID（可选）
    
    Returns:
        WebSocketMessage 对象
    """
    update_data = OrderStatusUpdateData(
        order_id=order_id,
        old_status=old_status,
        new_status=new_status,
        order_data=order_data,
        status_display=status_display,
        updated_at=datetime.now().isoformat()
    )
    
    return WebSocketMessage(
        message_type=WebSocketMessageType.ORDER_STATUS_UPDATE.value,
        timestamp=datetime.now().isoformat(),
        data=update_data.to_dict(),
        user_id=user_id,
        order_id=order_id
    )


# ==============================================================================
#  Agent连接状态消息
# ==============================================================================

@dataclass
class AgentConnectionData:
    """Agent连接状态消息数据"""
    agent_type: str  # Agent类型：user, merchant, payment, amazon
    agent_name: Optional[str] = None  # Agent名称
    connection_status: str  # 连接状态：disconnected, connecting, connected, error
    url: Optional[str] = None  # Agent URL
    connected_at: Optional[str] = None  # 连接时间
    last_heartbeat: Optional[str] = None  # 最后心跳时间
    error_message: Optional[str] = None  # 错误信息（如果连接失败）
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def create_agent_connection_message(
    agent_type: str,
    connection_status: str,
    agent_name: Optional[str] = None,
    url: Optional[str] = None,
    connected_at: Optional[str] = None,
    last_heartbeat: Optional[str] = None,
    error_message: Optional[str] = None,
    user_id: Optional[str] = None
) -> WebSocketMessage:
    """
    创建Agent连接状态消息
    
    Args:
        agent_type: Agent类型
        connection_status: 连接状态
        agent_name: Agent名称（可选）
        url: Agent URL（可选）
        connected_at: 连接时间（可选）
        last_heartbeat: 最后心跳时间（可选）
        error_message: 错误信息（可选）
        user_id: 用户ID（可选）
    
    Returns:
        WebSocketMessage 对象
    """
    connection_data = AgentConnectionData(
        agent_type=agent_type,
        agent_name=agent_name,
        connection_status=connection_status,
        url=url,
        connected_at=connected_at,
        last_heartbeat=last_heartbeat,
        error_message=error_message
    )
    
    return WebSocketMessage(
        message_type=WebSocketMessageType.AGENT_CONNECTION.value,
        timestamp=datetime.now().isoformat(),
        data=connection_data.to_dict(),
        user_id=user_id
    )


# ==============================================================================
#  区块链交易消息
# ==============================================================================

@dataclass
class BlockchainTransactionData:
    """区块链交易消息数据"""
    order_id: str
    tx_hash: str  # 交易哈希
    transaction_type: str  # 交易类型：payment, delivery, completed
    status: str  # 交易状态：pending, confirmed, failed
    block_number: Optional[int] = None  # 区块号
    data_hash: Optional[str] = None  # 数据哈希
    timestamp: Optional[str] = None  # 交易时间
    from_address: Optional[str] = None  # 发送地址
    to_address: Optional[str] = None  # 接收地址
    amount: Optional[float] = None  # 交易金额
    currency: Optional[str] = None  # 货币类型
    explorer_url: Optional[str] = None  # 区块链浏览器链接
    error_message: Optional[str] = None  # 错误信息（如果交易失败）
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def create_blockchain_transaction_message(
    order_id: str,
    tx_hash: str,
    transaction_type: str,
    status: str,
    block_number: Optional[int] = None,
    data_hash: Optional[str] = None,
    timestamp: Optional[str] = None,
    from_address: Optional[str] = None,
    to_address: Optional[str] = None,
    amount: Optional[float] = None,
    currency: Optional[str] = None,
    explorer_url: Optional[str] = None,
    error_message: Optional[str] = None,
    user_id: Optional[str] = None
) -> WebSocketMessage:
    """
    创建区块链交易消息
    
    Args:
        order_id: 订单ID
        tx_hash: 交易哈希
        transaction_type: 交易类型
        status: 交易状态
        block_number: 区块号（可选）
        data_hash: 数据哈希（可选）
        timestamp: 交易时间（可选）
        from_address: 发送地址（可选）
        to_address: 接收地址（可选）
        amount: 交易金额（可选）
        currency: 货币类型（可选）
        explorer_url: 区块链浏览器链接（可选）
        error_message: 错误信息（可选）
        user_id: 用户ID（可选）
    
    Returns:
        WebSocketMessage 对象
    """
    transaction_data = BlockchainTransactionData(
        order_id=order_id,
        tx_hash=tx_hash,
        transaction_type=transaction_type,
        status=status,
        block_number=block_number,
        data_hash=data_hash,
        timestamp=timestamp or datetime.now().isoformat(),
        from_address=from_address,
        to_address=to_address,
        amount=amount,
        currency=currency,
        explorer_url=explorer_url,
        error_message=error_message
    )
    
    return WebSocketMessage(
        message_type=WebSocketMessageType.BLOCKCHAIN_TRANSACTION.value,
        timestamp=datetime.now().isoformat(),
        data=transaction_data.to_dict(),
        user_id=user_id,
        order_id=order_id
    )


# ==============================================================================
#  交付通知消息
# ==============================================================================

@dataclass
class DeliveryNotificationData:
    """交付通知消息数据"""
    order_id: str
    delivery_status: str  # 交付状态
    tracking_number: Optional[str] = None  # 物流追踪号
    carrier: Optional[str] = None  # 承运商
    delivery_method: Optional[str] = None  # 交付方式
    estimated_delivery_date: Optional[str] = None  # 预计交付日期
    actual_delivery_date: Optional[str] = None  # 实际交付日期
    delivery_address: Optional[str] = None  # 交付地址
    delivery_proof: Optional[Dict[str, Any]] = None  # 交付凭证
    delivery_proof_hash: Optional[str] = None  # 交付凭证哈希
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def create_delivery_notification_message(
    order_id: str,
    delivery_status: str,
    tracking_number: Optional[str] = None,
    carrier: Optional[str] = None,
    delivery_method: Optional[str] = None,
    estimated_delivery_date: Optional[str] = None,
    actual_delivery_date: Optional[str] = None,
    delivery_address: Optional[str] = None,
    delivery_proof: Optional[Dict[str, Any]] = None,
    delivery_proof_hash: Optional[str] = None,
    user_id: Optional[str] = None
) -> WebSocketMessage:
    """
    创建交付通知消息
    
    Args:
        order_id: 订单ID
        delivery_status: 交付状态
        tracking_number: 物流追踪号（可选）
        carrier: 承运商（可选）
        delivery_method: 交付方式（可选）
        estimated_delivery_date: 预计交付日期（可选）
        actual_delivery_date: 实际交付日期（可选）
        delivery_address: 交付地址（可选）
        delivery_proof: 交付凭证（可选）
        delivery_proof_hash: 交付凭证哈希（可选）
        user_id: 用户ID（可选）
    
    Returns:
        WebSocketMessage 对象
    """
    notification_data = DeliveryNotificationData(
        order_id=order_id,
        delivery_status=delivery_status,
        tracking_number=tracking_number,
        carrier=carrier,
        delivery_method=delivery_method,
        estimated_delivery_date=estimated_delivery_date,
        actual_delivery_date=actual_delivery_date,
        delivery_address=delivery_address,
        delivery_proof=delivery_proof,
        delivery_proof_hash=delivery_proof_hash
    )
    
    return WebSocketMessage(
        message_type=WebSocketMessageType.DELIVERY_NOTIFICATION.value,
        timestamp=datetime.now().isoformat(),
        data=notification_data.to_dict(),
        user_id=user_id,
        order_id=order_id
    )


# ==============================================================================
#  辅助函数
# ==============================================================================

def parse_websocket_message(message_str: str) -> Optional[WebSocketMessage]:
    """
    解析 WebSocket 消息字符串
    
    Args:
        message_str: JSON 格式的消息字符串
    
    Returns:
        WebSocketMessage 对象，如果解析失败则返回 None
    """
    try:
        data = json.loads(message_str)
        return WebSocketMessage.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"❌ 解析 WebSocket 消息失败: {e}")
        return None


def create_error_message(
    error: str,
    error_detail: Optional[str] = None,
    user_id: Optional[str] = None,
    order_id: Optional[str] = None
) -> WebSocketMessage:
    """
    创建错误消息
    
    Args:
        error: 错误信息
        error_detail: 错误详情（可选）
        user_id: 用户ID（可选）
        order_id: 订单ID（可选）
    
    Returns:
        WebSocketMessage 对象
    """
    return WebSocketMessage(
        message_type=WebSocketMessageType.ERROR.value,
        timestamp=datetime.now().isoformat(),
        data={
            "error": error,
            "error_detail": error_detail
        },
        user_id=user_id,
        order_id=order_id
    )


def create_heartbeat_message() -> WebSocketMessage:
    """
    创建心跳消息
    
    Returns:
        WebSocketMessage 对象
    """
    return WebSocketMessage(
        message_type=WebSocketMessageType.HEARTBEAT.value,
        timestamp=datetime.now().isoformat(),
        data={"ping": True}
    )

