import React from "react";
import {
  AgentConnection,
  AgentConnectionStatus,
  AgentType,
} from "../types/order";

interface AgentConnectionCardProps {
  userAgent?: AgentConnection | null;
  merchantAgent?: AgentConnection | null;
  className?: string;
}

interface AgentNodeProps {
  agent: AgentConnection;
  position: "left" | "right";
}

const AgentNode: React.FC<AgentNodeProps> = ({ agent, position }) => {
  const isConnected = agent.connection_status === AgentConnectionStatus.CONNECTED;
  const isConnecting = agent.connection_status === AgentConnectionStatus.CONNECTING;
  const isError = agent.connection_status === AgentConnectionStatus.ERROR;
  const isDisconnected = agent.connection_status === AgentConnectionStatus.DISCONNECTED;

  // 获取 Agent 图标
  const getAgentIcon = () => {
    switch (agent.agent_type) {
      case AgentType.USER:
        return "👤";
      case AgentType.MERCHANT:
        return "🏪";
      case AgentType.PAYMENT:
        return "💳";
      case AgentType.AMAZON:
        return "🛒";
      default:
        return "🤖";
    }
  };

  // 获取 Agent 名称
  const getAgentName = () => {
    return agent.agent_name || agent.agent_type.toUpperCase() + " Agent";
  };

  // 获取状态颜色
  const getStatusColor = () => {
    if (isConnected) return "text-neon-cyan border-neon-cyan";
    if (isConnecting) return "text-night-purple border-night-purple";
    if (isError) return "text-red-500 border-red-500";
    return "text-text-secondary border-text-secondary";
  };

  // 获取状态背景色
  const getStatusBg = () => {
    if (isConnected) return "bg-neon-cyan/10 border-neon-cyan/30";
    if (isConnecting) return "bg-night-purple/10 border-night-purple/30";
    if (isError) return "bg-red-500/10 border-red-500/30";
    return "bg-deep-black/50 border-text-secondary/20";
  };

  // 获取状态文本
  const getStatusText = () => {
    if (isConnected) return "✅ Connected";
    if (isConnecting) return "⏳ Connecting";
    if (isError) return "❌ Error";
    return "⏸️ Disconnected";
  };

  // 格式化时间戳
  const formatTimestamp = (timestamp: string | null | undefined) => {
    if (!timestamp) return null;
    try {
      const date = new Date(timestamp);
      return date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return timestamp;
    }
  };

  return (
    <div
      className={`
        flex flex-col items-center
        ${position === "left" ? "mr-auto" : "ml-auto"}
        max-w-[200px]
      `}
    >
      {/* Agent 头像 */}
      <div
        className={`
          w-16 h-16 rounded-full flex items-center justify-center
          border-2 transition-all duration-300 mb-3
          ${getStatusColor()} ${getStatusBg()}
          ${isConnected ? "shadow-lg shadow-neon-cyan/20" : ""}
          ${isConnecting ? "animate-pulse" : ""}
        `}
      >
        <span className="text-3xl">{getAgentIcon()}</span>
      </div>

      {/* Agent 名称 */}
      <h3 className="text-sm font-semibold text-text-primary mb-1 text-center">
        {getAgentName()}
      </h3>

      {/* 连接状态 */}
      <div
        className={`
          px-3 py-1 rounded-full text-xs font-medium mb-2
          ${isConnected ? "bg-neon-cyan/20 text-neon-cyan" : ""}
          ${isConnecting ? "bg-night-purple/20 text-night-purple animate-pulse" : ""}
          ${isError ? "bg-red-500/20 text-red-500" : ""}
          ${isDisconnected ? "bg-text-secondary/10 text-text-secondary" : ""}
        `}
      >
        {getStatusText()}
      </div>

      {/* Agent URL */}
      {agent.url && (
        <div className="text-xs text-text-secondary/70 text-center mb-2 break-all">
          <span className="block truncate max-w-[180px]" title={agent.url}>
            {agent.url.replace(/^https?:\/\//, "").replace(/\/$/, "")}
          </span>
        </div>
      )}

      {/* 连接时间 */}
      {agent.connected_at && isConnected && (
        <div className="text-xs text-text-secondary/60 text-center">
          {formatTimestamp(agent.connected_at)}
        </div>
      )}

      {/* 最后心跳时间 */}
      {agent.last_heartbeat && isConnected && (
        <div className="text-xs text-text-secondary/50 text-center mt-1">
          ♥ {formatTimestamp(agent.last_heartbeat)}
        </div>
      )}
    </div>
  );
};

const ConnectionLine: React.FC<{
  isConnected: boolean;
  isConnecting: boolean;
}> = ({ isConnected, isConnecting }) => {
  return (
    <div className="flex-1 flex items-center justify-center px-4 relative">
      {/* 连接线 */}
      <div
        className={`
          w-full h-0.5 transition-all duration-500
          ${isConnected ? "bg-neon-cyan" : isConnecting ? "bg-night-purple" : "bg-text-secondary/20"}
          ${isConnected ? "opacity-100" : "opacity-30"}
        `}
      />

      {/* 流动动画点 */}
      {isConnected && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="connection-pulse-dot w-2 h-2 bg-neon-cyan rounded-full animate-connection-pulse" />
        </div>
      )}

      {/* 连接中动画 */}
      {isConnecting && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-2 h-2 bg-night-purple rounded-full animate-pulse" />
        </div>
      )}

      {/* 协议标识 */}
      <div
        className={`
          absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2
          px-2 py-1 rounded text-xs font-medium
          ${isConnected ? "bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/30" : ""}
          ${isConnecting ? "bg-night-purple/20 text-night-purple border border-night-purple/30" : ""}
          ${!isConnected && !isConnecting ? "bg-deep-black/50 text-text-secondary border border-text-secondary/20" : ""}
        `}
      >
        🔗 A2A
      </div>
    </div>
  );
};

export const AgentConnectionCard: React.FC<AgentConnectionCardProps> = ({
  userAgent,
  merchantAgent,
  className = "",
}) => {
  // 默认 Agent 连接对象
  const defaultUserAgent: AgentConnection = {
    agent_type: AgentType.USER,
    agent_name: "User Agent",
    connection_status: AgentConnectionStatus.DISCONNECTED,
  };

  const defaultMerchantAgent: AgentConnection = {
    agent_type: AgentType.MERCHANT,
    agent_name: "Merchant Agent",
    connection_status: AgentConnectionStatus.DISCONNECTED,
  };

  const user = userAgent || defaultUserAgent;
  const merchant = merchantAgent || defaultMerchantAgent;

  const isUserConnected = user.connection_status === AgentConnectionStatus.CONNECTED;
  const isMerchantConnected = merchant.connection_status === AgentConnectionStatus.CONNECTED;
  const isUserConnecting = user.connection_status === AgentConnectionStatus.CONNECTING;
  const isMerchantConnecting = merchant.connection_status === AgentConnectionStatus.CONNECTING;

  const bothConnected = isUserConnected && isMerchantConnected;
  const eitherConnecting = isUserConnecting || isMerchantConnecting;

  return (
    <div
      className={`
        bg-deep-black/50 backdrop-blur-sm rounded-lg border border-night-purple/20 p-6
        ${className}
      `}
    >
      <div className="mb-4">
        <h3 className="text-lg font-bold text-text-primary mb-1 flex items-center">
          <span className="mr-2">🔗</span>
          Agent Connection Status
        </h3>
        <p className="text-text-secondary text-sm">
          Real-time connection status between agents
        </p>
      </div>

      {/* Agent 连接展示 */}
      <div className="flex items-center justify-between">
        {/* User Agent */}
        <AgentNode agent={user} position="left" />

        {/* 连接线 */}
        <ConnectionLine
          isConnected={bothConnected}
          isConnecting={eitherConnecting}
        />

        {/* Merchant Agent */}
        <AgentNode agent={merchant} position="right" />
      </div>

      {/* 连接信息 */}
      <div className="mt-6 pt-4 border-t border-text-secondary/20">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-text-secondary">Connection Protocol:</span>
            <span className="text-text-primary ml-2 font-mono">A2A Protocol</span>
          </div>
          <div>
            <span className="text-text-secondary">Connection Type:</span>
            <span className="text-text-primary ml-2">Direct Connection</span>
          </div>
        </div>
      </div>

      {/* 添加 CSS 动画 */}
      <style>{`
        @keyframes connection-pulse {
          0% {
            transform: translateX(-100px);
            opacity: 0;
          }
          50% {
            opacity: 1;
          }
          100% {
            transform: translateX(100px);
            opacity: 0;
          }
        }
        .animate-connection-pulse {
          animation: connection-pulse 2s ease-in-out infinite;
        }
        .connection-pulse-dot {
          box-shadow: 0 0 10px rgba(0, 255, 209, 0.8);
        }
      `}</style>
    </div>
  );
};

export default AgentConnectionCard;

