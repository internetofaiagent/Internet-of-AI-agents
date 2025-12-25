import React, { useState } from "react";
import {
  Order,
  OrderStatus,
  ORDER_STATUS_DISPLAY,
} from "../types/order";

interface OrderDetailCardProps {
  order: Order;
  className?: string;
}

export const OrderDetailCard: React.FC<OrderDetailCardProps> = ({
  order,
  className = "",
}) => {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(["basic"])
  );

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(section)) {
        newSet.delete(section);
      } else {
        newSet.add(section);
      }
      return newSet;
    });
  };

  // 格式化时间戳
  const formatTimestamp = (timestamp: string | null | undefined) => {
    if (!timestamp) return "N/A";
    try {
      const date = new Date(timestamp);
      return date.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return timestamp;
    }
  };

  // 获取状态颜色
  const getStatusColor = () => {
    switch (order.status) {
      case OrderStatus.COMPLETED:
        return "text-neon-cyan bg-neon-cyan/10 border-neon-cyan/30";
      case OrderStatus.DELIVERED:
        return "text-night-purple bg-night-purple/10 border-night-purple/30";
      case OrderStatus.ACCEPTED:
      case OrderStatus.PROCESSING:
        return "text-blue-400 bg-blue-400/10 border-blue-400/30";
      case OrderStatus.CANCELLED:
        return "text-red-500 bg-red-500/10 border-red-500/30";
      default:
        return "text-text-secondary bg-text-secondary/10 border-text-secondary/20";
    }
  };

  // 获取区块链交易信息
  const getBlockchainTransactions = () => {
    const blockchainTxs = order.metadata?.blockchain_tx_hashes || {};
    const transactions = [];

    if (blockchainTxs.payment) {
      transactions.push({
        type: "payment",
        label: "支付交易",
        tx_hash: blockchainTxs.payment,
      });
    }
    if (blockchainTxs.delivery) {
      transactions.push({
        type: "delivery",
        label: "交付交易",
        tx_hash: blockchainTxs.delivery,
      });
    }
    if (blockchainTxs.completed) {
      transactions.push({
        type: "completed",
        label: "完成交易",
        tx_hash: blockchainTxs.completed,
      });
    }

    return transactions;
  };

  const blockchainTransactions = getBlockchainTransactions();

  // 信息项组件
  const InfoItem: React.FC<{
    label: string;
    value: React.ReactNode;
    className?: string;
  }> = ({ label, value, className = "" }) => (
    <div className={`flex justify-between items-start py-2 ${className}`}>
      <span className="text-text-secondary text-sm font-medium">{label}:</span>
      <span className="text-text-primary text-sm text-right ml-4 flex-1">
        {value}
      </span>
    </div>
  );

  // 可展开区域组件
  const ExpandableSection: React.FC<{
    title: string;
    sectionKey: string;
    icon: string;
    children: React.ReactNode;
  }> = ({ title, sectionKey, icon, children }) => {
    const isExpanded = expandedSections.has(sectionKey);

    return (
      <div className="border border-text-secondary/20 rounded-lg overflow-hidden mb-4">
        <button
          onClick={() => toggleSection(sectionKey)}
          className="w-full px-4 py-3 flex items-center justify-between bg-deep-black/30 hover:bg-deep-black/50 transition-colors"
        >
          <div className="flex items-center space-x-2">
            <span className="text-lg">{icon}</span>
            <h3 className="text-text-primary font-semibold">{title}</h3>
          </div>
          <svg
            className={`w-5 h-5 text-text-secondary transition-transform duration-300 ${
              isExpanded ? "transform rotate-180" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </button>
        {isExpanded && (
          <div className="px-4 py-3 bg-deep-black/20 animate-fade-in">
            {children}
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      className={`
        bg-deep-black/50 backdrop-blur-sm rounded-lg border border-night-purple/20 p-6
        ${className}
      `}
    >
      {/* 订单头部 */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xl font-bold text-text-primary flex items-center">
            <span className="mr-2">📦</span>
            Order Details
          </h2>
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor()}`}
          >
            {ORDER_STATUS_DISPLAY[order.status]}
          </span>
        </div>
        <p className="text-text-secondary text-sm font-mono">{order.order_id}</p>
      </div>

      {/* 基本信息 */}
      <ExpandableSection
        title="基本信息"
        sectionKey="basic"
        icon="ℹ️"
      >
        <div className="space-y-1">
          <InfoItem label="订单ID" value={<code className="text-neon-cyan">{order.order_id}</code>} />
          <InfoItem
            label="商品名称"
            value={order.product_info.product_name || "N/A"}
          />
          {order.product_info.product_description && (
            <InfoItem
              label="商品描述"
              value={
                <span className="text-text-secondary">
                  {order.product_info.product_description}
                </span>
              }
            />
          )}
          <InfoItem
            label="数量"
            value={`${order.product_info.quantity} 件`}
          />
          <InfoItem
            label="单价"
            value={`${order.product_info.unit_price.toFixed(2)} ${order.currency}`}
          />
          <InfoItem
            label="总金额"
            value={
              <span className="text-neon-cyan font-bold">
                {order.amount.toFixed(2)} {order.currency}
              </span>
            }
          />
          <InfoItem
            label="订单状态"
            value={
              <span className={`px-2 py-1 rounded text-xs ${getStatusColor()}`}>
                {ORDER_STATUS_DISPLAY[order.status]}
              </span>
            }
          />
          <InfoItem label="创建时间" value={formatTimestamp(order.created_at)} />
          {order.accepted_at && (
            <InfoItem label="接单时间" value={formatTimestamp(order.accepted_at)} />
          )}
          {order.delivered_at && (
            <InfoItem label="交付时间" value={formatTimestamp(order.delivered_at)} />
          )}
          {order.completed_at && (
            <InfoItem label="完成时间" value={formatTimestamp(order.completed_at)} />
          )}
        </div>
      </ExpandableSection>

      {/* 支付信息 */}
      {order.payment_info && (
        <ExpandableSection
          title="支付信息"
          sectionKey="payment"
          icon="💳"
        >
          <div className="space-y-1">
            {order.payment_info.payment_order_id && (
              <InfoItem
                label="支付订单ID"
                value={
                  <code className="text-neon-cyan">
                    {order.payment_info.payment_order_id}
                  </code>
                }
              />
            )}
            <InfoItem
              label="支付方式"
              value={
                order.payment_info.payment_method
                  ? order.payment_info.payment_method.toUpperCase()
                  : "N/A"
              }
            />
            <InfoItem
              label="支付金额"
              value={`${order.payment_info.payment_amount.toFixed(2)} ${order.payment_info.payment_currency}`}
            />
            <InfoItem
              label="支付状态"
              value={
                <span
                  className={`px-2 py-1 rounded text-xs ${
                    order.payment_info.payment_status === "paid"
                      ? "bg-neon-cyan/20 text-neon-cyan"
                      : "bg-text-secondary/10 text-text-secondary"
                  }`}
                >
                  {order.payment_info.payment_status === "paid"
                    ? "✅ 已支付"
                    : order.payment_info.payment_status || "⏸️ 未支付"}
                </span>
              }
            />
            {order.payment_info.paid_at && (
              <InfoItem
                label="支付时间"
                value={formatTimestamp(order.payment_info.paid_at)}
              />
            )}
            {order.payment_info.payment_transaction_hash && (
              <InfoItem
                label="支付交易哈希"
                value={
                  <code className="text-neon-cyan text-xs break-all">
                    {order.payment_info.payment_transaction_hash}
                  </code>
                }
              />
            )}
          </div>
        </ExpandableSection>
      )}

      {/* 交付信息 */}
      {order.delivery_info && (
        <ExpandableSection
          title="交付信息"
          sectionKey="delivery"
          icon="🚚"
        >
          <div className="space-y-1">
            {order.delivery_info.tracking_number && (
              <InfoItem
                label="物流追踪号"
                value={
                  <code className="text-neon-cyan">
                    {order.delivery_info.tracking_number}
                  </code>
                }
              />
            )}
            {order.delivery_info.carrier && (
              <InfoItem label="承运商" value={order.delivery_info.carrier} />
            )}
            {order.delivery_info.delivery_method && (
              <InfoItem
                label="交付方式"
                value={order.delivery_info.delivery_method}
              />
            )}
            {order.delivery_info.delivery_address && (
              <InfoItem
                label="交付地址"
                value={order.delivery_info.delivery_address}
              />
            )}
            {order.delivery_info.estimated_delivery_date && (
              <InfoItem
                label="预计交付日期"
                value={formatTimestamp(order.delivery_info.estimated_delivery_date)}
              />
            )}
            {order.delivery_info.actual_delivery_date && (
              <InfoItem
                label="实际交付日期"
                value={formatTimestamp(order.delivery_info.actual_delivery_date)}
              />
            )}
            {order.delivery_info.delivery_status && (
              <InfoItem
                label="交付状态"
                value={order.delivery_info.delivery_status}
              />
            )}
          </div>
        </ExpandableSection>
      )}

      {/* 区块链交易信息 */}
      {blockchainTransactions.length > 0 && (
        <ExpandableSection
          title="区块链交易"
          sectionKey="blockchain"
          icon="⛓️"
        >
          <div className="space-y-3">
            {blockchainTransactions.map((tx, index) => (
              <div
                key={index}
                className="p-3 bg-deep-black/50 rounded border border-night-purple/20"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-text-primary font-medium">{tx.label}</span>
                  <span className="text-xs text-text-secondary">
                    {tx.type.toUpperCase()}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <code className="text-neon-cyan text-xs break-all flex-1 mr-2">
                    {tx.tx_hash}
                  </code>
                  <a
                    href={`https://testnet.iotexscan.io/tx/${tx.tx_hash}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-2 py-1 bg-neon-cyan/20 text-neon-cyan rounded text-xs hover:bg-neon-cyan/30 transition-colors flex items-center space-x-1 flex-shrink-0"
                    title="在区块链浏览器中查看"
                  >
                    <span>🔗</span>
                    <span>View</span>
                  </a>
                </div>
              </div>
            ))}
          </div>
        </ExpandableSection>
      )}

      {/* 其他信息 */}
      {(order.notes || order.user_agent_url) && (
        <ExpandableSection
          title="其他信息"
          sectionKey="other"
          icon="📝"
        >
          <div className="space-y-1">
            {order.notes && (
              <InfoItem
                label="订单备注"
                value={<span className="text-text-secondary">{order.notes}</span>}
              />
            )}
            {order.user_agent_url && (
              <InfoItem
                label="用户 Agent URL"
                value={
                  <code className="text-neon-cyan text-xs break-all">
                    {order.user_agent_url}
                  </code>
                }
              />
            )}
          </div>
        </ExpandableSection>
      )}

      {/* 添加 CSS 动画 */}
      <style>{`
        @keyframes fade-in {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fade-in {
          animation: fade-in 0.3s ease-out;
        }
      `}</style>
    </div>
  );
};

export default OrderDetailCard;

