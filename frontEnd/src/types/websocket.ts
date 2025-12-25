/**
 * WebSocket 消息格式定义
 * 与后端 AgentCore/Agents/websocket_messages.py 保持一致
 */

/**
 * WebSocket 消息类型枚举
 */
export enum WebSocketMessageType {
  ORDER_STATUS_UPDATE = "order_status_update",      // 订单状态变更
  AGENT_CONNECTION = "agent_connection",            // Agent连接状态
  BLOCKCHAIN_TRANSACTION = "blockchain_transaction", // 链上交易确认
  DELIVERY_NOTIFICATION = "delivery_notification",  // 交付通知
  HEARTBEAT = "heartbeat",                          // 心跳消息
  ERROR = "error"                                   // 错误消息
}

/**
 * WebSocket 消息基础接口
 */
export interface WebSocketMessage {
  message_type: WebSocketMessageType;  // 消息类型
  timestamp: string;  // 消息时间戳（ISO格式）
  data: Record<string, any>;  // 消息数据
  user_id?: string | null;  // 用户ID（可选，用于消息路由）
  order_id?: string | null;  // 订单ID（可选，用于订单相关消息）
}

/**
 * 订单状态更新消息数据
 */
export interface OrderStatusUpdateData {
  order_id: string;
  old_status?: string | null;  // 旧状态
  new_status: string;  // 新状态
  order_data?: Record<string, any> | null;  // 完整订单数据（可选）
  status_display?: string | null;  // 状态显示文本
  updated_at?: string | null;  // 更新时间
}

/**
 * Agent连接状态消息数据
 */
export interface AgentConnectionData {
  agent_type: string;  // Agent类型：user, merchant, payment, amazon
  agent_name?: string | null;  // Agent名称
  connection_status: string;  // 连接状态：disconnected, connecting, connected, error
  url?: string | null;  // Agent URL
  connected_at?: string | null;  // 连接时间
  last_heartbeat?: string | null;  // 最后心跳时间
  error_message?: string | null;  // 错误信息（如果连接失败）
}

/**
 * 区块链交易状态枚举
 */
export enum BlockchainTransactionStatus {
  PENDING = "pending",      // 待确认
  CONFIRMED = "confirmed",  // 已确认
  FAILED = "failed"         // 失败
}

/**
 * 区块链交易消息数据
 */
export interface BlockchainTransactionData {
  order_id: string;
  tx_hash: string;  // 交易哈希
  transaction_type: string;  // 交易类型：payment, delivery, completed
  status: BlockchainTransactionStatus;  // 交易状态
  block_number?: number | null;  // 区块号
  data_hash?: string | null;  // 数据哈希
  timestamp?: string | null;  // 交易时间
  from_address?: string | null;  // 发送地址
  to_address?: string | null;  // 接收地址
  amount?: number | null;  // 交易金额
  currency?: string | null;  // 货币类型
  explorer_url?: string | null;  // 区块链浏览器链接
  error_message?: string | null;  // 错误信息（如果交易失败）
}

/**
 * 交付通知消息数据
 */
export interface DeliveryNotificationData {
  order_id: string;
  delivery_status: string;  // 交付状态
  tracking_number?: string | null;  // 物流追踪号
  carrier?: string | null;  // 承运商
  delivery_method?: string | null;  // 交付方式
  estimated_delivery_date?: string | null;  // 预计交付日期
  actual_delivery_date?: string | null;  // 实际交付日期
  delivery_address?: string | null;  // 交付地址
  delivery_proof?: Record<string, any> | null;  // 交付凭证
  delivery_proof_hash?: string | null;  // 交付凭证哈希
}

/**
 * 类型化的 WebSocket 消息接口
 */
export interface TypedWebSocketMessage<T = Record<string, any>> extends WebSocketMessage {
  data: T;
}

/**
 * 订单状态更新消息
 */
export interface OrderStatusUpdateMessage extends TypedWebSocketMessage<OrderStatusUpdateData> {
  message_type: WebSocketMessageType.ORDER_STATUS_UPDATE;
}

/**
 * Agent连接状态消息
 */
export interface AgentConnectionMessage extends TypedWebSocketMessage<AgentConnectionData> {
  message_type: WebSocketMessageType.AGENT_CONNECTION;
}

/**
 * 区块链交易消息
 */
export interface BlockchainTransactionMessage extends TypedWebSocketMessage<BlockchainTransactionData> {
  message_type: WebSocketMessageType.BLOCKCHAIN_TRANSACTION;
}

/**
 * 交付通知消息
 */
export interface DeliveryNotificationMessage extends TypedWebSocketMessage<DeliveryNotificationData> {
  message_type: WebSocketMessageType.DELIVERY_NOTIFICATION;
}

/**
 * 错误消息
 */
export interface ErrorMessage extends TypedWebSocketMessage<{ error: string; error_detail?: string }> {
  message_type: WebSocketMessageType.ERROR;
}

/**
 * 心跳消息
 */
export interface HeartbeatMessage extends TypedWebSocketMessage<{ ping: boolean }> {
  message_type: WebSocketMessageType.HEARTBEAT;
}

/**
 * 类型守卫函数：检查是否为订单状态更新消息
 */
export function isOrderStatusUpdateMessage(
  message: WebSocketMessage
): message is OrderStatusUpdateMessage {
  return message.message_type === WebSocketMessageType.ORDER_STATUS_UPDATE;
}

/**
 * 类型守卫函数：检查是否为Agent连接消息
 */
export function isAgentConnectionMessage(
  message: WebSocketMessage
): message is AgentConnectionMessage {
  return message.message_type === WebSocketMessageType.AGENT_CONNECTION;
}

/**
 * 类型守卫函数：检查是否为区块链交易消息
 */
export function isBlockchainTransactionMessage(
  message: WebSocketMessage
): message is BlockchainTransactionMessage {
  return message.message_type === WebSocketMessageType.BLOCKCHAIN_TRANSACTION;
}

/**
 * 类型守卫函数：检查是否为交付通知消息
 */
export function isDeliveryNotificationMessage(
  message: WebSocketMessage
): message is DeliveryNotificationMessage {
  return message.message_type === WebSocketMessageType.DELIVERY_NOTIFICATION;
}

/**
 * 类型守卫函数：检查是否为错误消息
 */
export function isErrorMessage(message: WebSocketMessage): message is ErrorMessage {
  return message.message_type === WebSocketMessageType.ERROR;
}

/**
 * 类型守卫函数：检查是否为心跳消息
 */
export function isHeartbeatMessage(message: WebSocketMessage): message is HeartbeatMessage {
  return message.message_type === WebSocketMessageType.HEARTBEAT;
}

/**
 * 解析 WebSocket 消息
 */
export function parseWebSocketMessage(messageStr: string): WebSocketMessage | null {
  try {
    const message = JSON.parse(messageStr) as WebSocketMessage;
    
    // 验证消息格式
    if (!message.message_type || !message.timestamp || !message.data) {
      console.error("❌ WebSocket 消息格式无效:", message);
      return null;
    }
    
    return message;
  } catch (error) {
    console.error("❌ 解析 WebSocket 消息失败:", error);
    return null;
  }
}

/**
 * WebSocket 连接状态枚举
 */
export enum WebSocketConnectionStatus {
  DISCONNECTED = "disconnected",  // 未连接
  CONNECTING = "connecting",      // 连接中
  CONNECTED = "connected",        // 已连接
  RECONNECTING = "reconnecting",  // 重连中
  ERROR = "error"                 // 连接错误
}

