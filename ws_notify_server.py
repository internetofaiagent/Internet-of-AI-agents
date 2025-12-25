#!/usr/bin/env python3
"""
WebSocket 通知服务器
支持实时推送订单状态、Agent连接、区块链交易等消息
"""

import asyncio
import websockets
import sys
import os
import logging
from typing import Set, Optional

# 添加项目根目录到路径
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# 导入 WebSocket 消息格式
try:
    from AgentCore.Agents.websocket_messages import WebSocketMessage
    WEBSOCKET_MESSAGES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ [WebSocket] 无法导入 websocket_messages: {e}")
    WEBSOCKET_MESSAGES_AVAILABLE = False
    WebSocketMessage = None

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [WebSocket] - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WebSocketServer")

# 全局连接集合
connected: Set[websockets.WebSocketServerProtocol] = set()


async def handler(websocket, path):
    """
    WebSocket 连接处理器
    
    Args:
        websocket: WebSocket 连接对象
        path: 连接路径
    """
    connected.add(websocket)
    client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logger.info(f"✅ 新前端连接: {client_addr} (总连接数: {len(connected)})")
    
    try:
        # 监听客户端消息（用于心跳、订阅等）
        async for message in websocket:
            try:
                # 解析客户端消息（可能是 JSON 格式）
                import json
                client_msg = json.loads(message)
                logger.debug(f"📥 收到客户端消息: {client_msg}")
                
                # 处理客户端消息（如心跳响应、订阅请求等）
                # 目前简化处理，只记录日志
                if client_msg.get("type") == "ping":
                    # 心跳响应
                    await websocket.send(json.dumps({"type": "pong", "timestamp": client_msg.get("timestamp")}))
                    
            except json.JSONDecodeError:
                # 如果不是 JSON，当作普通文本处理
                logger.debug(f"📥 收到客户端文本消息: {message}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"🔌 前端断开连接: {client_addr}")
    except Exception as e:
        logger.error(f"❌ 连接异常: {client_addr}, 错误: {e}")
    finally:
        connected.discard(websocket)
        logger.info(f"🔌 连接已移除: {client_addr} (剩余连接数: {len(connected)})")


async def broadcast(message: str):
    """
    广播消息给所有连接的客户端（简化版，不实现路由）
    
    Args:
        message: 要广播的消息（JSON 字符串）
    """
    if not connected:
        logger.debug("📤 没有连接的客户端，跳过广播")
        return
    
    # 收集所有断开的连接
    disconnected = set()
    
    # 发送消息给所有连接
    tasks = []
    for ws in connected:
        try:
            tasks.append(ws.send(message))
        except Exception as e:
            logger.warning(f"⚠️ 发送消息失败，连接可能已断开: {e}")
            disconnected.add(ws)
    
    # 等待所有发送完成
    if tasks:
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug(f"📤 消息已广播给 {len(connected)} 个客户端")
        except Exception as e:
            logger.error(f"❌ 广播消息时发生错误: {e}")
    
    # 清理断开的连接
    for ws in disconnected:
        connected.discard(ws)
        logger.info(f"🧹 清理断开的连接 (剩余连接数: {len(connected)})")


def send_message(message: WebSocketMessage) -> bool:
    """
    发送 WebSocket 消息（同步函数，内部使用异步）
    
    此函数可以在同步代码中调用，会自动处理异步发送。
    消息会被广播给所有连接的客户端。
    
    Args:
        message: WebSocketMessage 对象，包含要发送的消息
    
    Returns:
        bool: 是否成功发送（注意：此函数是异步的，返回 True 只表示任务已创建）
    
    Example:
        >>> from AgentCore.Agents.websocket_messages import create_order_status_update_message
        >>> from ws_notify_server import send_message
        >>> 
        >>> msg = create_order_status_update_message(
        ...     order_id="ORDER_123",
        ...     new_status="DELIVERED",
        ...     user_id="user_001"
        ... )
        >>> send_message(msg)
        True
    """
    if not WEBSOCKET_MESSAGES_AVAILABLE:
        logger.error("❌ websocket_messages 模块不可用，无法发送消息")
        return False
    
    if not isinstance(message, WebSocketMessage):
        logger.error(f"❌ 消息类型错误，期望 WebSocketMessage，实际: {type(message)}")
        return False
    
    try:
        # 将消息对象转换为 JSON 字符串
        message_json = message.to_json()
        
        # 尝试获取事件循环并发送消息
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，创建任务（非阻塞，异步执行）
                # 注意：任务会被调度到事件循环中，但不保证立即执行
                asyncio.create_task(broadcast(message_json))
                logger.debug(f"📤 消息任务已创建: {message.message_type}")
            else:
                # 如果事件循环未运行，直接运行（阻塞直到完成）
                loop.run_until_complete(broadcast(message_json))
                logger.debug(f"📤 消息已同步发送: {message.message_type}")
        except RuntimeError:
            # 如果没有事件循环，尝试创建新的（作为后备方案）
            try:
                asyncio.run(broadcast(message_json))
                logger.debug(f"📤 消息已通过新事件循环发送: {message.message_type}")
            except RuntimeError:
                logger.warning("⚠️ 无法发送消息：没有可用的 asyncio 事件循环")
                return False
        
        logger.info(f"📤 消息已发送: {message.message_type} (order_id: {message.order_id}, user_id: {message.user_id})")
        return True
        
    except Exception as e:
        logger.error(f"❌ 发送消息失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def send_message_async(message: WebSocketMessage) -> bool:
    """
    异步发送 WebSocket 消息
    
    Args:
        message: WebSocketMessage 对象
    
    Returns:
        bool: 是否成功发送
    """
    if not WEBSOCKET_MESSAGES_AVAILABLE:
        logger.error("❌ websocket_messages 模块不可用，无法发送消息")
        return False
    
    if not isinstance(message, WebSocketMessage):
        logger.error(f"❌ 消息类型错误，期望 WebSocketMessage，实际: {type(message)}")
        return False
    
    try:
        # 将消息对象转换为 JSON 字符串
        message_json = message.to_json()
        
        # 异步广播消息
        await broadcast(message_json)
        
        logger.info(f"📤 消息已发送: {message.message_type} (order_id: {message.order_id}, user_id: {message.user_id})")
        return True
        
    except Exception as e:
        logger.error(f"❌ 发送消息失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def main():
    """主函数，启动 WebSocket 服务器"""
    host = "0.0.0.0"
    port = 6789
    
    logger.info("=" * 60)
    logger.info("🚀 启动 WebSocket 通知服务器")
    logger.info(f"👂 监听地址: ws://{host}:{port}")
    logger.info(f"📋 功能特性:")
    logger.info("   - 实时订单状态推送")
    logger.info("   - Agent 连接状态通知")
    logger.info("   - 区块链交易确认通知")
    logger.info("   - 交付通知")
    logger.info("   - 广播模式（发送给所有连接）")
    logger.info("=" * 60)
    
    async with websockets.serve(handler, host, port):
        logger.info(f"✅ WebSocket 服务器已启动，等待连接...")
        # 保持服务器运行
        await asyncio.Future()  # 永久运行


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 收到中断信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"❌ 服务器启动失败: {e}")
        import traceback
        logger.error(traceback.format_exc()) 