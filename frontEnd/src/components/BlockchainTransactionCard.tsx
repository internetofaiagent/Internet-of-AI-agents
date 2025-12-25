import React, { useState } from "react";
import {
  BlockchainTransaction,
  BlockchainTransactionStatus,
} from "../types/order";

interface BlockchainTransactionCardProps {
  transactions: BlockchainTransaction[];
  orderId?: string;
  className?: string;
}

interface TransactionItemProps {
  transaction: BlockchainTransaction;
  index: number;
}

const TransactionItem: React.FC<TransactionItemProps> = ({
  transaction,
  index,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showFullHash, setShowFullHash] = useState(false);

  const isConfirmed = transaction.status === BlockchainTransactionStatus.CONFIRMED;
  const isPending = transaction.status === BlockchainTransactionStatus.PENDING;
  const isFailed = transaction.status === BlockchainTransactionStatus.FAILED;

  // 获取交易类型显示文本
  const getTransactionTypeLabel = () => {
    switch (transaction.transaction_type) {
      case "payment":
        return "💰 支付交易";
      case "delivery":
        return "🚚 交付交易";
      case "completed":
        return "✅ 完成交易";
      default:
        return "⛓️ 区块链交易";
    }
  };

  // 获取状态颜色
  const getStatusColor = () => {
    if (isConfirmed) return "text-neon-cyan bg-neon-cyan/10 border-neon-cyan/30";
    if (isPending) return "text-night-purple bg-night-purple/10 border-night-purple/30";
    if (isFailed) return "text-red-500 bg-red-500/10 border-red-500/30";
    return "text-text-secondary bg-text-secondary/10 border-text-secondary/20";
  };

  // 获取状态文本
  const getStatusText = () => {
    if (isConfirmed) return "✅ Confirmed";
    if (isPending) return "⏳ Pending";
    if (isFailed) return "❌ Failed";
    return "Unknown";
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

  // 格式化地址（缩短显示）
  const formatAddress = (address: string | null | undefined) => {
    if (!address) return "N/A";
    if (address.length <= 20) return address;
    return `${address.slice(0, 10)}...${address.slice(-8)}`;
  };

  // 获取浏览器链接
  const getExplorerUrl = () => {
    if (transaction.explorer_url) {
      return transaction.explorer_url;
    }
    // 默认使用 IoTeX 测试网浏览器
    if (transaction.tx_hash) {
      return `https://testnet.iotexscan.io/tx/${transaction.tx_hash}`;
    }
    return null;
  };

  const explorerUrl = getExplorerUrl();

  return (
    <div
      className={`
        border rounded-lg overflow-hidden mb-4 transition-all duration-300
        ${isConfirmed ? "border-neon-cyan/30" : isPending ? "border-night-purple/30" : "border-text-secondary/20"}
        ${isExpanded ? "bg-deep-black/50" : "bg-deep-black/30"}
      `}
    >
      {/* 交易头部 */}
      <div
        className="px-4 py-3 cursor-pointer hover:bg-deep-black/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div
              className={`
                w-10 h-10 rounded-full flex items-center justify-center
                border-2 transition-all duration-300
                ${getStatusColor()}
                ${isConfirmed ? "shadow-lg shadow-neon-cyan/20" : ""}
                ${isPending ? "animate-pulse" : ""}
              `}
            >
              <span className="text-lg">
                {transaction.transaction_type === "payment" ? "💰" : 
                 transaction.transaction_type === "delivery" ? "🚚" : 
                 transaction.transaction_type === "completed" ? "✅" : "⛓️"}
              </span>
            </div>
            <div>
              <h4 className="text-text-primary font-semibold">
                {getTransactionTypeLabel()}
              </h4>
              <p className="text-text-secondary text-xs">
                {formatTimestamp(transaction.timestamp)}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {/* 状态徽章 */}
            <span
              className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor()}`}
            >
              {getStatusText()}
            </span>

            {/* 展开/收起按钮 */}
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
          </div>
        </div>
      </div>

      {/* 交易详情（展开时显示） */}
      {isExpanded && (
        <div className="px-4 py-3 border-t border-text-secondary/20 bg-deep-black/30 animate-fade-in">
          <div className="space-y-3">
            {/* 交易哈希 */}
            <div>
              <label className="text-text-secondary text-xs font-medium mb-1 block">
                交易哈希 (TX Hash):
              </label>
              <div className="flex items-center space-x-2">
                <code
                  className="text-neon-cyan text-xs font-mono break-all flex-1 bg-deep-black/50 p-2 rounded"
                  title={transaction.tx_hash}
                >
                  {showFullHash
                    ? transaction.tx_hash
                    : `${transaction.tx_hash.slice(0, 20)}...${transaction.tx_hash.slice(-16)}`}
                </code>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowFullHash(!showFullHash);
                  }}
                  className="px-2 py-1 text-xs text-text-secondary hover:text-neon-cyan transition-colors"
                  title={showFullHash ? "显示简短" : "显示完整"}
                >
                  {showFullHash ? "简" : "全"}
                </button>
                {explorerUrl && (
                  <a
                    href={explorerUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="px-3 py-1 bg-neon-cyan/20 text-neon-cyan rounded text-xs hover:bg-neon-cyan/30 transition-colors flex items-center space-x-1"
                    title="在区块链浏览器中查看"
                  >
                    <span>🔗</span>
                    <span>View on Explorer</span>
                  </a>
                )}
              </div>
            </div>

            {/* 交易信息网格 */}
            <div className="grid grid-cols-2 gap-3">
              {/* 区块号 */}
              {transaction.block_number && (
                <div>
                  <label className="text-text-secondary text-xs font-medium mb-1 block">
                    区块号:
                  </label>
                  <p className="text-text-primary text-sm font-mono">
                    #{transaction.block_number.toLocaleString()}
                  </p>
                </div>
              )}

              {/* 交易状态 */}
              <div>
                <label className="text-text-secondary text-xs font-medium mb-1 block">
                  状态:
                </label>
                <p className="text-text-primary text-sm">{getStatusText()}</p>
              </div>

              {/* 发送地址 */}
              {transaction.from_address && (
                <div>
                  <label className="text-text-secondary text-xs font-medium mb-1 block">
                    发送地址:
                  </label>
                  <p
                    className="text-text-primary text-xs font-mono break-all"
                    title={transaction.from_address}
                  >
                    {formatAddress(transaction.from_address)}
                  </p>
                </div>
              )}

              {/* 接收地址 */}
              {transaction.to_address && (
                <div>
                  <label className="text-text-secondary text-xs font-medium mb-1 block">
                    接收地址:
                  </label>
                  <p
                    className="text-text-primary text-xs font-mono break-all"
                    title={transaction.to_address}
                  >
                    {formatAddress(transaction.to_address)}
                  </p>
                </div>
              )}

              {/* 交易金额 */}
              {transaction.amount !== null && transaction.amount !== undefined && (
                <div>
                  <label className="text-text-secondary text-xs font-medium mb-1 block">
                    交易金额:
                  </label>
                  <p className="text-text-primary text-sm font-bold text-neon-cyan">
                    {transaction.amount.toFixed(4)} {transaction.currency || "IOTX"}
                  </p>
                </div>
              )}

              {/* 交易时间 */}
              {transaction.timestamp && (
                <div>
                  <label className="text-text-secondary text-xs font-medium mb-1 block">
                    交易时间:
                  </label>
                  <p className="text-text-primary text-xs">
                    {formatTimestamp(transaction.timestamp)}
                  </p>
                </div>
              )}
            </div>

            {/* 数据哈希 */}
            {transaction.data_hash && (
              <div>
                <label className="text-text-secondary text-xs font-medium mb-1 block">
                  数据哈希 (Data Hash):
                </label>
                <code className="text-neon-cyan text-xs font-mono break-all bg-deep-black/50 p-2 rounded block">
                  {transaction.data_hash}
                </code>
              </div>
            )}

            {/* 交易数据预览 */}
            {transaction.metadata && Object.keys(transaction.metadata).length > 0 && (
              <div>
                <label className="text-text-secondary text-xs font-medium mb-2 block">
                  交易数据预览:
                </label>
                <details className="bg-deep-black/50 rounded p-3">
                  <summary className="text-text-secondary text-xs cursor-pointer hover:text-neon-cyan transition-colors mb-2">
                    📋 查看交易数据
                  </summary>
                  <pre className="text-xs text-text-secondary overflow-x-auto mt-2">
                    {JSON.stringify(transaction.metadata, null, 2)}
                  </pre>
                </details>
              </div>
            )}

            {/* 错误信息（如果交易失败） */}
            {isFailed && transaction.metadata?.error_message && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded">
                <p className="text-red-500 text-xs font-medium mb-1">错误信息:</p>
                <p className="text-red-400 text-xs">{transaction.metadata.error_message}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export const BlockchainTransactionCard: React.FC<BlockchainTransactionCardProps> = ({
  transactions,
  orderId,
  className = "",
}) => {
  if (!transactions || transactions.length === 0) {
    return (
      <div
        className={`
          bg-deep-black/50 backdrop-blur-sm rounded-lg border border-night-purple/20 p-6
          ${className}
        `}
      >
        <div className="text-center py-8">
          <span className="text-4xl mb-4 block">⛓️</span>
          <h3 className="text-lg font-bold text-text-primary mb-2">
            Blockchain Transactions
          </h3>
          <p className="text-text-secondary text-sm">
            暂无区块链交易记录
          </p>
        </div>
      </div>
    );
  }

  // 按交易类型排序：payment -> delivery -> completed
  const sortedTransactions = [...transactions].sort((a, b) => {
    const order = { payment: 0, delivery: 1, completed: 2 };
    const aOrder = order[a.transaction_type as keyof typeof order] ?? 999;
    const bOrder = order[b.transaction_type as keyof typeof order] ?? 999;
    return aOrder - bOrder;
  });

  // 统计交易状态
  const confirmedCount = transactions.filter(
    (tx) => tx.status === BlockchainTransactionStatus.CONFIRMED
  ).length;
  const pendingCount = transactions.filter(
    (tx) => tx.status === BlockchainTransactionStatus.PENDING
  ).length;
  const failedCount = transactions.filter(
    (tx) => tx.status === BlockchainTransactionStatus.FAILED
  ).length;

  return (
    <div
      className={`
        bg-deep-black/50 backdrop-blur-sm rounded-lg border border-night-purple/20 p-6
        ${className}
      `}
    >
      {/* 头部 */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xl font-bold text-text-primary flex items-center">
            <span className="mr-2">⛓️</span>
            Blockchain Transactions
          </h2>
          <span className="text-text-secondary text-sm">
            {transactions.length} {transactions.length === 1 ? "transaction" : "transactions"}
          </span>
        </div>
        {orderId && (
          <p className="text-text-secondary text-sm font-mono">{orderId}</p>
        )}

        {/* 交易状态统计 */}
        <div className="flex items-center space-x-4 mt-3 text-xs">
          {confirmedCount > 0 && (
            <span className="px-2 py-1 bg-neon-cyan/20 text-neon-cyan rounded">
              ✅ {confirmedCount} Confirmed
            </span>
          )}
          {pendingCount > 0 && (
            <span className="px-2 py-1 bg-night-purple/20 text-night-purple rounded animate-pulse">
              ⏳ {pendingCount} Pending
            </span>
          )}
          {failedCount > 0 && (
            <span className="px-2 py-1 bg-red-500/20 text-red-500 rounded">
              ❌ {failedCount} Failed
            </span>
          )}
        </div>
      </div>

      {/* 交易列表 */}
      <div>
        {sortedTransactions.map((transaction, index) => (
          <TransactionItem
            key={transaction.tx_hash || index}
            transaction={transaction}
            index={index}
          />
        ))}
      </div>

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

export default BlockchainTransactionCard;

