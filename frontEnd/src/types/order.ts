/**
 * 订单状态数据模型
 * 与后端 AgentCore/Agents/merchant_agent.py 保持一致
 */

/**
 * 订单状态枚举
 */
export enum OrderStatus {
  PENDING = "PENDING",           // 待接单
  ACCEPTED = "ACCEPTED",         // 已接单
  PROCESSING = "PROCESSING",     // 处理中
  DELIVERED = "DELIVERED",       // 已交付
  COMPLETED = "COMPLETED",       // 已完成
  CANCELLED = "CANCELLED"         // 已取消
}

/**
 * 订单阶段状态（用于时间线展示）
 */
export enum OrderStageStatus {
  PENDING = "pending",           // 等待中
  PROCESSING = "processing",     // 进行中
  COMPLETED = "completed"        // 已完成
}

/**
 * 用户信息接口
 */
export interface UserInfo {
  user_id: string;
  user_name?: string | null;
  user_address?: string | null;
  user_email?: string | null;
  user_phone?: string | null;
  user_wallet_address?: string | null;  // 用户钱包地址（用于区块链支付）
}

/**
 * 商品信息接口
 */
export interface ProductInfo {
  product_id?: string | null;
  product_name: string;
  product_description?: string | null;
  product_url?: string | null;
  quantity: number;
  unit_price: number;
  category?: string | null;
  attributes?: Record<string, any>;  // 其他商品属性
}

/**
 * 支付信息接口
 */
export interface PaymentInfo {
  payment_order_id?: string | null;
  payment_method?: string | null;  // 支付方式，如 "alipay", "blockchain"
  payment_amount: number;
  payment_currency: string;
  payment_status?: string | null;  // 支付状态
  payment_transaction_hash?: string | null;  // 区块链交易哈希（如果使用区块链支付）
  paid_at?: string | null;  // 支付时间（ISO格式）
}

/**
 * 交付信息接口
 */
export interface DeliveryInfo {
  delivery_method?: string | null;  // 交付方式，如 "express", "standard"
  tracking_number?: string | null;  // 物流追踪号
  carrier?: string | null;  // 承运商
  estimated_delivery_date?: string | null;  // 预计交付日期
  actual_delivery_date?: string | null;  // 实际交付日期
  delivery_address?: string | null;  // 交付地址
  delivery_status?: string | null;  // 交付状态
}

/**
 * 订单接口
 */
export interface Order {
  order_id: string;
  user_info: UserInfo;
  product_info: ProductInfo;
  amount: number;  // 订单总金额
  currency: string;
  status: OrderStatus;
  payment_info?: PaymentInfo | null;
  delivery_info?: DeliveryInfo | null;
  
  // 时间戳
  created_at: string;
  updated_at: string;
  accepted_at?: string | null;  // 接单时间
  delivered_at?: string | null;  // 交付时间
  completed_at?: string | null;  // 完成时间
  cancelled_at?: string | null;  // 取消时间
  
  // 其他元数据
  metadata?: Record<string, any>;  // 其他订单元数据
  notes?: string | null;  // 订单备注
  user_agent_url?: string | null;  // 用户 Agent URL（用于交付通知）
}

/**
 * 订单阶段接口（用于时间线展示）
 */
export interface OrderStage {
  stage_id: string;  // 阶段ID，如 "agent_match", "order_created", "merchant_accepted", "order_delivered", "order_confirmed", "on_chain"
  title: string;  // 阶段标题
  description?: string;  // 阶段描述
  status: OrderStageStatus;  // 阶段状态
  timestamp?: string | null;  // 阶段完成时间（ISO格式）
  icon?: string;  // 阶段图标（emoji或图标名称）
  metadata?: Record<string, any>;  // 阶段元数据
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
 * 区块链交易接口
 */
export interface BlockchainTransaction {
  tx_hash: string;  // 交易哈希
  block_number?: number | null;  // 区块号
  status: BlockchainTransactionStatus;  // 交易状态
  data_hash?: string | null;  // 数据哈希
  timestamp?: string | null;  // 交易时间（ISO格式）
  from_address?: string | null;  // 发送地址
  to_address?: string | null;  // 接收地址
  amount?: number | null;  // 交易金额
  currency?: string | null;  // 货币类型
  transaction_type?: string | null;  // 交易类型：payment, delivery, completed
  explorer_url?: string | null;  // 区块链浏览器链接
  metadata?: Record<string, any>;  // 交易元数据
}

/**
 * Agent类型枚举
 */
export enum AgentType {
  USER = "user",           // 用户Agent
  MERCHANT = "merchant",   // 商家Agent
  PAYMENT = "payment",     // 支付Agent
  AMAZON = "amazon"        // Amazon Agent
}

/**
 * Agent连接状态枚举
 */
export enum AgentConnectionStatus {
  DISCONNECTED = "disconnected",  // 未连接
  CONNECTING = "connecting",      // 连接中
  CONNECTED = "connected",        // 已连接
  ERROR = "error"                 // 连接错误
}

/**
 * Agent连接接口
 */
export interface AgentConnection {
  agent_type: AgentType;  // Agent类型
  agent_name?: string | null;  // Agent名称
  connection_status: AgentConnectionStatus;  // 连接状态
  url?: string | null;  // Agent URL
  connected_at?: string | null;  // 连接时间（ISO格式）
  last_heartbeat?: string | null;  // 最后心跳时间（ISO格式）
  metadata?: Record<string, any>;  // 连接元数据
}

/**
 * 订单状态显示文本映射
 */
export const ORDER_STATUS_DISPLAY: Record<OrderStatus, string> = {
  [OrderStatus.PENDING]: "待接单",
  [OrderStatus.ACCEPTED]: "已接单",
  [OrderStatus.PROCESSING]: "处理中",
  [OrderStatus.DELIVERED]: "已交付",
  [OrderStatus.COMPLETED]: "已完成",
  [OrderStatus.CANCELLED]: "已取消"
};

/**
 * 订单阶段定义（用于时间线展示）
 */
export const ORDER_STAGES: Omit<OrderStage, "status" | "timestamp">[] = [
  {
    stage_id: "agent_match",
    title: "Agent匹配",
    description: "User Agent ↔ Merchant Agent 连接成功",
    icon: "🔍"
  },
  {
    stage_id: "order_created",
    title: "下单支付",
    description: "订单已创建，支付已完成",
    icon: "🛒"
  },
  {
    stage_id: "merchant_accepted",
    title: "商家接单",
    description: "商家已接收订单",
    icon: "✅"
  },
  {
    stage_id: "order_delivered",
    title: "订单交付",
    description: "商家正在处理交付",
    icon: "🚚"
  },
  {
    stage_id: "order_confirmed",
    title: "确认收货",
    description: "等待用户确认",
    icon: "📦"
  },
  {
    stage_id: "on_chain",
    title: "上链存储",
    description: "订单完成后将上链",
    icon: "⛓️"
  }
];

/**
 * 订单状态到阶段的映射
 */
export function mapOrderStatusToStages(order: Order): OrderStage[] {
  const stages: OrderStage[] = [];
  const now = new Date().toISOString();
  
  // 阶段1: Agent匹配（订单创建时即完成）
  stages.push({
    ...ORDER_STAGES[0],
    status: OrderStageStatus.COMPLETED,
    timestamp: order.created_at
  });
  
  // 阶段2: 下单支付（支付完成时完成）
  const paymentCompleted = order.payment_info?.payment_status === "paid";
  stages.push({
    ...ORDER_STAGES[1],
    status: paymentCompleted ? OrderStageStatus.COMPLETED : OrderStageStatus.PENDING,
    timestamp: order.payment_info?.paid_at || null
  });
  
  // 阶段3: 商家接单（订单状态为ACCEPTED或更高时完成）
  const accepted = order.status !== OrderStatus.PENDING;
  stages.push({
    ...ORDER_STAGES[2],
    status: accepted ? OrderStageStatus.COMPLETED : OrderStageStatus.PENDING,
    timestamp: order.accepted_at || null
  });
  
  // 阶段4: 订单交付（订单状态为DELIVERED或更高时完成）
  const delivered = [OrderStatus.DELIVERED, OrderStatus.COMPLETED].includes(order.status);
  stages.push({
    ...ORDER_STAGES[3],
    status: delivered ? OrderStageStatus.COMPLETED : (accepted ? OrderStageStatus.PROCESSING : OrderStageStatus.PENDING),
    timestamp: order.delivered_at || null
  });
  
  // 阶段5: 确认收货（订单状态为COMPLETED时完成）
  const completed = order.status === OrderStatus.COMPLETED;
  stages.push({
    ...ORDER_STAGES[4],
    status: completed ? OrderStageStatus.COMPLETED : (delivered ? OrderStageStatus.PENDING : OrderStageStatus.PENDING),
    timestamp: order.completed_at || null
  });
  
  // 阶段6: 上链存储（根据metadata中的区块链交易信息判断）
  const blockchainTxs = order.metadata?.blockchain_tx_hashes || {};
  const hasOnChain = completed && (blockchainTxs.completed || blockchainTxs.delivery || blockchainTxs.payment);
  stages.push({
    ...ORDER_STAGES[5],
    status: hasOnChain ? OrderStageStatus.COMPLETED : (completed ? OrderStageStatus.PROCESSING : OrderStageStatus.PENDING),
    timestamp: completed ? order.completed_at || null : null
  });
  
  return stages;
}

