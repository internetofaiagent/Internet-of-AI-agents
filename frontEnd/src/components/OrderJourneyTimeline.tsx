import React, { useState } from "react";
import {
  OrderStage,
  OrderStageStatus,
  mapOrderStatusToStages,
  Order,
} from "../types/order";

interface OrderJourneyTimelineProps {
  order: Order;
  className?: string;
}

interface StageItemProps {
  stage: OrderStage;
  index: number;
  isLast: boolean;
  expandedStages: Set<string>;
  onToggleExpand: (stageId: string) => void;
}

const StageItem: React.FC<StageItemProps> = ({
  stage,
  index,
  isLast,
  expandedStages,
  onToggleExpand,
}) => {
  const isExpanded = expandedStages.has(stage.stage_id);
  const isCompleted = stage.status === OrderStageStatus.COMPLETED;
  const isProcessing = stage.status === OrderStageStatus.PROCESSING;
  const isPending = stage.status === OrderStageStatus.PENDING;

  // 状态颜色
  const getStatusColor = () => {
    if (isCompleted) return "text-neon-cyan border-neon-cyan";
    if (isProcessing) return "text-night-purple border-night-purple";
    return "text-text-secondary border-text-secondary";
  };

  // 状态背景色
  const getStatusBg = () => {
    if (isCompleted) return "bg-neon-cyan/10 border-neon-cyan/30";
    if (isProcessing) return "bg-night-purple/10 border-night-purple/30";
    return "bg-deep-black/50 border-text-secondary/20";
  };

  // 连接线颜色
  const getLineColor = () => {
    if (isCompleted) return "bg-neon-cyan";
    if (isProcessing) return "bg-night-purple";
    return "bg-text-secondary/20";
  };

  // 格式化时间戳
  const formatTimestamp = (timestamp: string | null | undefined) => {
    if (!timestamp) return null;
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

  return (
    <div className="relative flex items-start">
      {/* 左侧图标和连接线 */}
      <div className="flex flex-col items-center mr-4">
        {/* 阶段图标 */}
        <div
          className={`
            w-12 h-12 rounded-full flex items-center justify-center
            border-2 transition-all duration-500 ease-out
            ${getStatusColor()} ${getStatusBg()}
            ${isCompleted ? "shadow-lg shadow-neon-cyan/20 animate-pulse-glow" : ""}
            ${isProcessing ? "animate-pulse" : ""}
            ${isPending ? "opacity-50" : "opacity-100"}
          `}
        >
          <span className="text-2xl">{stage.icon || "○"}</span>
        </div>

        {/* 连接线 */}
        {!isLast && (
          <div
            className={`
              w-0.5 h-full min-h-[60px] mt-2 transition-all duration-500
              ${getLineColor()}
              ${isCompleted ? "opacity-100" : "opacity-30"}
            `}
          />
        )}
      </div>

      {/* 右侧内容 */}
      <div className="flex-1 pb-8">
        <div
          className={`
            rounded-lg p-4 transition-all duration-300
            ${getStatusBg()} border
            ${isExpanded ? "border-opacity-50" : "border-opacity-30"}
            hover:border-opacity-50 cursor-pointer
          `}
          onClick={() => onToggleExpand(stage.stage_id)}
        >
          {/* 标题和状态 */}
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-3">
              <h3
                className={`
                  font-semibold text-lg transition-colors duration-300
                  ${isCompleted ? "text-neon-cyan" : isProcessing ? "text-night-purple" : "text-text-secondary"}
                `}
              >
                {stage.title}
              </h3>
              {/* 状态指示器 */}
              <span
                className={`
                  px-2 py-1 rounded text-xs font-medium
                  ${isCompleted ? "bg-neon-cyan/20 text-neon-cyan" : ""}
                  ${isProcessing ? "bg-night-purple/20 text-night-purple animate-pulse" : ""}
                  ${isPending ? "bg-text-secondary/10 text-text-secondary" : ""}
                `}
              >
                {isCompleted ? "✅ 已完成" : isProcessing ? "⏳ 进行中" : "⏸️ 等待中"}
              </span>
            </div>

            {/* 展开/收起按钮 */}
            <button
              className={`
                text-text-secondary hover:text-neon-cyan transition-colors
                ${isExpanded ? "transform rotate-180" : ""}
              `}
              onClick={(e) => {
                e.stopPropagation();
                onToggleExpand(stage.stage_id);
              }}
            >
              <svg
                className="w-5 h-5 transition-transform duration-300"
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
          </div>

          {/* 描述 */}
          <p className="text-text-secondary text-sm mb-2">{stage.description}</p>

          {/* 时间戳 */}
          {stage.timestamp && (
            <p className="text-text-secondary/70 text-xs">
              {formatTimestamp(stage.timestamp)}
            </p>
          )}

          {/* 展开详情 */}
          {isExpanded && (
            <div
              className="mt-4 pt-4 border-t border-text-secondary/20 animate-fade-in"
            >
              <div className="space-y-2 text-sm">
                <div>
                  <span className="text-text-secondary">阶段ID:</span>
                  <span className="text-text-primary ml-2 font-mono">
                    {stage.stage_id}
                  </span>
                </div>
                {stage.timestamp && (
                  <div>
                    <span className="text-text-secondary">完成时间:</span>
                    <span className="text-text-primary ml-2">
                      {formatTimestamp(stage.timestamp)}
                    </span>
                  </div>
                )}
                {stage.metadata && Object.keys(stage.metadata).length > 0 && (
                  <div>
                    <span className="text-text-secondary">详细信息:</span>
                    <pre className="mt-2 p-2 bg-deep-black rounded text-xs text-text-secondary overflow-x-auto">
                      {JSON.stringify(stage.metadata, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const OrderJourneyTimeline: React.FC<OrderJourneyTimelineProps> = ({
  order,
  className = "",
}) => {
  const [expandedStages, setExpandedStages] = useState<Set<string>>(new Set());

  // 将订单状态映射到阶段
  const stages = mapOrderStatusToStages(order);

  const toggleExpand = (stageId: string) => {
    setExpandedStages((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(stageId)) {
        newSet.delete(stageId);
      } else {
        newSet.add(stageId);
      }
      return newSet;
    });
  };

  return (
    <div
      className={`
        bg-deep-black/50 backdrop-blur-sm rounded-lg border border-night-purple/20 p-6
        ${className}
      `}
    >
      <div className="mb-6">
        <h2 className="text-xl font-bold text-text-primary mb-2 flex items-center">
          <span className="mr-2">📋</span>
          Order Journey Timeline
        </h2>
        <p className="text-text-secondary text-sm">
          订单流程进度追踪 - {order.order_id}
        </p>
      </div>

      <div className="relative">
        {stages.map((stage, index) => (
          <StageItem
            key={stage.stage_id}
            stage={stage}
            index={index}
            isLast={index === stages.length - 1}
            expandedStages={expandedStages}
            onToggleExpand={toggleExpand}
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
        @keyframes pulse-glow {
          0%, 100% {
            box-shadow: 0 0 0 0 rgba(0, 255, 209, 0.4);
          }
          50% {
            box-shadow: 0 0 20px 5px rgba(0, 255, 209, 0.2);
          }
        }
        .animate-pulse-glow {
          animation: pulse-glow 2s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
};

export default OrderJourneyTimeline;

