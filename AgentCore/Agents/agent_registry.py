#!/usr/bin/env python3
"""
Agent注册中心 - 支持agent动态注册、心跳检测和服务发现
"""

import os
import json
import time
import threading
import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from python_a2a import A2AServer, run_server, AgentCard, AgentSkill, TaskStatus, TaskState, A2AClient
from AgentCore.Tools.iotextoken_toolkit import IotexTokenToolkit


class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = "pending"           # 待商家接单
    ACCEPTED = "accepted"         # 商家已接单
    PROCESSING = "processing"     # 处理中
    COMPLETED = "completed"       # 已完成
    CANCELLED = "cancelled"       # 已取消


@dataclass
class Order:
    """订单数据结构"""
    order_id: str
    user_id: str
    merchant_type: str = "amazon"  # 商家类型，目前只有amazon
    product_info: Dict[str, Any] = None
    payment_info: Dict[str, Any] = None
    shipping_address: Dict[str, Any] = None
    status: str = OrderStatus.PENDING.value
    created_at: datetime = None
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    merchant_agent_url: Optional[str] = None
    merchant_response: Optional[str] = None
    blockchain_tx_hash: Optional[str] = None  # 区块链交易哈希
    
    def __post_init__(self):
        if self.product_info is None:
            self.product_info = {}
        if self.payment_info is None:
            self.payment_info = {}
        if self.shipping_address is None:
            self.shipping_address = {}
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "order_id": self.order_id,
            "user_id": self.user_id,
            "merchant_type": self.merchant_type,
            "product_info": self.product_info,
            "payment_info": self.payment_info,
            "shipping_address": self.shipping_address,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "merchant_agent_url": self.merchant_agent_url,
            "merchant_response": self.merchant_response,
            "blockchain_tx_hash": self.blockchain_tx_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Order':
        """从字典格式创建对象"""
        order = cls(
            order_id=data["order_id"],
            user_id=data["user_id"],
            merchant_type=data.get("merchant_type", "amazon"),
            product_info=data.get("product_info", {}),
            payment_info=data.get("payment_info", {}),
            shipping_address=data.get("shipping_address", {}),
            status=data.get("status", OrderStatus.PENDING.value),
            merchant_agent_url=data.get("merchant_agent_url"),
            merchant_response=data.get("merchant_response"),
            blockchain_tx_hash=data.get("blockchain_tx_hash")
        )
        if data.get("created_at"):
            order.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("accepted_at"):
            order.accepted_at = datetime.fromisoformat(data["accepted_at"])
        if data.get("completed_at"):
            order.completed_at = datetime.fromisoformat(data["completed_at"])
        return order


@dataclass
class RegisteredAgent:
    """注册的Agent信息"""
    agent_card: AgentCard
    last_heartbeat: datetime
    status: str = "active"  # active, inactive, error
    response_time: float = 0.0
    error_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.agent_card.name,
            "description": self.agent_card.description,
            "url": self.agent_card.url,
            "version": getattr(self.agent_card, 'version', '1.0.0'),
            "skills": [{"name": skill.name, "description": skill.description} 
                      for skill in self.agent_card.skills] if self.agent_card.skills else [],
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "status": self.status,
            "response_time": self.response_time,
            "error_count": self.error_count
        }


class AgentRegistry:
    """Agent注册中心核心逻辑"""
    
    def __init__(self, heartbeat_interval: int = 30, timeout_threshold: int = 90):
        self.agents: Dict[str, RegisteredAgent] = {}
        self.heartbeat_interval = heartbeat_interval  # 心跳间隔（秒）
        self.timeout_threshold = timeout_threshold    # 超时阈值（秒）
        self.lock = threading.RLock()
        self.running = False
        self.heartbeat_thread = None
        
        # 订单管理
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.order_listener_thread = None
        self.order_listener_running = False
        
        # 商家agent映射（merchant_type -> agent_url）
        self.merchant_agents: Dict[str, str] = {
            "amazon": "http://localhost:5012"  # Amazon商家agent URL
        }
        
        # 区块链配置
        self.blockchain_enabled = os.environ.get("BLOCKCHAIN_ENABLED", "true").lower() == "true"
        self.iotex_rpc_url = os.environ.get("IOTEX_RPC_URL", "https://babel-api.testnet.iotex.io")
        self.iotex_chain_id = int(os.environ.get("IOTEX_CHAIN_ID", "4690"))
        self.blockchain_private_key = os.environ.get("BLOCKCHAIN_PRIVATE_KEY", "")
        self.blockchain_wallet_address = os.environ.get("BLOCKCHAIN_WALLET_ADDRESS", "")
        
        # ERC20 ABI（用于初始化IotexTokenToolkit）
        self.erc20_abi = [
            {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
            {"constant": False, "inputs": [{"name": "_from", "type": "address"}, {"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "transferFrom", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
            {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
            {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"}
        ]
        
        # 初始化IotexTokenToolkit
        self.blockchain_toolkit = None
        if self.blockchain_enabled:
            try:
                self.blockchain_toolkit = IotexTokenToolkit(
                    rpc_url=self.iotex_rpc_url,
                    erc20_abi=self.erc20_abi,
                    chain_id=self.iotex_chain_id
                )
                if self.blockchain_toolkit.web3.is_connected():
                    print(f"✅ 区块链工具包初始化成功: {self.iotex_rpc_url}")
                    if self.blockchain_private_key:
                        # 从私钥获取地址（如果未提供地址）
                        if not self.blockchain_wallet_address:
                            from eth_account import Account
                            account = Account.from_key(self.blockchain_private_key)
                            self.blockchain_wallet_address = account.address
                        print(f"📝 区块链钱包地址: {self.blockchain_wallet_address}")
                else:
                    print(f"⚠️ 区块链连接失败，上链功能将不可用")
                    self.blockchain_enabled = False
                    self.blockchain_toolkit = None
            except Exception as e:
                print(f"⚠️ 区块链工具包初始化失败: {e}，上链功能将不可用")
                self.blockchain_enabled = False
                self.blockchain_toolkit = None
        else:
            print("ℹ️ 区块链功能已禁用（BLOCKCHAIN_ENABLED=false）")
        
        # 预注册已知的agent
        self._preregister_known_agents()
        
        # 启动订单监听
        self.start_order_listener()
    
    def _preregister_known_agents(self):
        """预注册系统中已知的agent"""
        known_agents = [
            {
                "name": "Amazon Shopping Coordinator A2A Agent",
                "description": "An intelligent A2A agent that coordinates Amazon shopping by working with specialized agents.",
                "url": "http://localhost:5011",
                "skills": [
                    {"name": "product_search_and_recommendation", "description": "Search Amazon products and generate purchase recommendations with product URLs."},
                    {"name": "payment_agent_coordination", "description": "Coordinate with Payment A2A Agent to process payments before order placement."},
                    {"name": "amazon_agent_coordination", "description": "Coordinate with Amazon A2A Agent for order confirmation after payment."}
                ]
            },
            {
                "name": "Amazon Shopping Agent Qwen3 (A2A)",
                "description": "基于Qwen3模型的Amazon购物助手，支持商品搜索、购买和支付，完全兼容A2A协议。",
                "url": "http://localhost:5012",
                "skills": [
                    {"name": "amazon_product_search", "description": "在Amazon上搜索商品，支持关键词搜索和ASIN查询。"},
                    {"name": "amazon_one_click_purchase", "description": "一键购买功能：用户提供商品URL即可完成从支付报价到支付完成的整个流程。"},
                    {"name": "payment_processing", "description": "处理支付报价和支付执行，支持Fewsats支付系统。"}
                ]
            },
            {
                "name": "Alipay Payment A2A Agent",
                "description": "An A2A agent that creates Alipay payment orders for cross-border transactions and coordinates with Amazon Agent.",
                "url": "http://localhost:5005",
                "skills": [
                    {"name": "create_payment", "description": "Create an Alipay payment order for a product."},
                    {"name": "amazon_coordination", "description": "Coordinate with Amazon Agent after payment completion."}
                ]
            }
        ]
        
        for agent_info in known_agents:
            # 创建AgentCard
            skills = [AgentSkill(name=skill["name"], description=skill["description"]) 
                     for skill in agent_info["skills"]]
            agent_card = AgentCard(
                name=agent_info["name"],
                description=agent_info["description"],
                url=agent_info["url"],
                skills=skills
            )
            
            # 注册agent
            registered_agent = RegisteredAgent(
                agent_card=agent_card,
                last_heartbeat=datetime.now(),
                status="unknown"  # 初始状态为unknown，等待心跳检测
            )
            
            self.agents[agent_info["url"]] = registered_agent
            print(f"📝 预注册Agent: {agent_info['name']} at {agent_info['url']}")
    
    def register_agent(self, agent_card: AgentCard) -> bool:
        """注册新的agent"""
        with self.lock:
            try:
                registered_agent = RegisteredAgent(
                    agent_card=agent_card,
                    last_heartbeat=datetime.now(),
                    status="active"
                )
                
                self.agents[agent_card.url] = registered_agent
                print(f"✅ Agent注册成功: {agent_card.name} at {agent_card.url}")
                return True
                
            except Exception as e:
                print(f"❌ Agent注册失败: {e}")
                return False
    
    def unregister_agent(self, agent_url: str) -> bool:
        """注销agent"""
        with self.lock:
            if agent_url in self.agents:
                agent_name = self.agents[agent_url].agent_card.name
                del self.agents[agent_url]
                print(f"🗑️ Agent注销成功: {agent_name}")
                return True
            return False
    
    def update_heartbeat(self, agent_url: str, response_time: float = 0.0) -> bool:
        """更新agent心跳"""
        with self.lock:
            if agent_url in self.agents:
                self.agents[agent_url].last_heartbeat = datetime.now()
                self.agents[agent_url].response_time = response_time
                self.agents[agent_url].status = "active"
                self.agents[agent_url].error_count = 0
                return True
            return False
    
    def get_all_agents(self) -> List[Dict[str, Any]]:
        """获取所有注册的agent"""
        with self.lock:
            return [agent.to_dict() for agent in self.agents.values()]
    
    def get_active_agents(self) -> List[Dict[str, Any]]:
        """获取所有活跃的agent"""
        with self.lock:
            return [agent.to_dict() for agent in self.agents.values() 
                   if agent.status == "active"]
    
    def find_agents_by_skill(self, skill_name: str) -> List[Dict[str, Any]]:
        """根据技能查找agent"""
        with self.lock:
            matching_agents = []
            for agent in self.agents.values():
                if agent.status == "active" and agent.agent_card.skills:
                    for skill in agent.agent_card.skills:
                        if skill_name.lower() in skill.name.lower() or skill_name.lower() in skill.description.lower():
                            matching_agents.append(agent.to_dict())
                            break
            return matching_agents
    
    def find_agents_by_capability(self, capability_description: str) -> List[Dict[str, Any]]:
        """根据能力描述查找agent"""
        with self.lock:
            matching_agents = []
            keywords = capability_description.lower().split()
            
            for agent in self.agents.values():
                if agent.status != "active":
                    continue
                    
                # 检查agent描述
                agent_text = (agent.agent_card.description + " " + 
                             " ".join([skill.name + " " + skill.description 
                                     for skill in agent.agent_card.skills or []]))
                agent_text = agent_text.lower()
                
                # 计算匹配度
                match_count = sum(1 for keyword in keywords if keyword in agent_text)
                if match_count > 0:
                    agent_dict = agent.to_dict()
                    agent_dict["match_score"] = match_count / len(keywords)
                    matching_agents.append(agent_dict)
            
            # 按匹配度排序
            matching_agents.sort(key=lambda x: x["match_score"], reverse=True)
            return matching_agents
    
    def start_heartbeat_monitor(self):
        """启动心跳监控"""
        if self.running:
            return
            
        self.running = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_monitor_loop, daemon=True)
        self.heartbeat_thread.start()
        print(f"💓 心跳监控已启动，间隔: {self.heartbeat_interval}秒")
    
    def stop_heartbeat_monitor(self):
        """停止心跳监控"""
        self.running = False
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
        print("💓 心跳监控已停止")
    
    def _heartbeat_monitor_loop(self):
        """心跳监控循环"""
        while self.running:
            try:
                self._check_all_agents_health()
                time.sleep(self.heartbeat_interval)
            except Exception as e:
                print(f"❌ 心跳监控错误: {e}")
                time.sleep(5)
    
    def _check_all_agents_health(self):
        """检查所有agent的健康状态"""
        with self.lock:
            current_time = datetime.now()
            
            for agent_url, agent in list(self.agents.items()):
                try:
                    # 检查是否超时
                    time_since_heartbeat = (current_time - agent.last_heartbeat).total_seconds()
                    
                    if time_since_heartbeat > self.timeout_threshold:
                        # 尝试主动检查
                        if self._ping_agent(agent_url):
                            agent.last_heartbeat = current_time
                            agent.status = "active"
                            agent.error_count = 0
                        else:
                            agent.error_count += 1
                            if agent.error_count >= 3:
                                agent.status = "inactive"
                                print(f"⚠️ Agent标记为不活跃: {agent.agent_card.name}")
                            else:
                                agent.status = "error"
                    
                except Exception as e:
                    print(f"❌ 检查Agent健康状态失败 {agent_url}: {e}")
                    agent.error_count += 1
                    agent.status = "error"
    
    def _ping_agent(self, agent_url: str) -> bool:
        """ping指定的agent"""
        try:
            start_time = time.time()
            client = A2AClient(agent_url)
            response = client.ask("health check")
            response_time = time.time() - start_time
            
            if response and "healthy" in response.lower():
                self.update_heartbeat(agent_url, response_time)
                return True
            return False
            
        except Exception as e:
            print(f"❌ Ping Agent失败 {agent_url}: {e}")
            return False
    
    # ==================== 订单监听和管理功能 ====================
    
    def create_order(self, order_data: Dict[str, Any]) -> Optional[Order]:
        """创建新订单并加入监听队列"""
        try:
            order = Order(
                order_id=order_data.get("order_id", f"ORDER_{datetime.now().strftime('%Y%m%d%H%M%S')}_{int(time.time() * 1000) % 10000}"),
                user_id=order_data.get("user_id", "unknown"),
                merchant_type=order_data.get("merchant_type", "amazon"),
                product_info=order_data.get("product_info", {}),
                payment_info=order_data.get("payment_info", {}),
                shipping_address=order_data.get("shipping_address", {})
            )
            
            with self.lock:
                self.orders[order.order_id] = order
                print(f"📦 新订单已创建: {order.order_id} (商家: {order.merchant_type})")
            
            return order
            
        except Exception as e:
            print(f"❌ 创建订单失败: {e}")
            return None
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单信息"""
        with self.lock:
            return self.orders.get(order_id)
    
    def get_pending_orders(self, merchant_type: str = "amazon") -> List[Order]:
        """获取指定商家的待处理订单"""
        with self.lock:
            return [
                order for order in self.orders.values()
                if order.merchant_type == merchant_type and order.status == OrderStatus.PENDING.value
            ]
    
    def update_order_status(self, order_id: str, status: str, merchant_response: Optional[str] = None) -> bool:
        """更新订单状态"""
        with self.lock:
            if order_id not in self.orders:
                return False
            
            order = self.orders[order_id]
            old_status = order.status
            order.status = status
            
            if status == OrderStatus.ACCEPTED.value:
                order.accepted_at = datetime.now()
                # 查找对应的商家agent URL
                if order.merchant_type in self.merchant_agents:
                    order.merchant_agent_url = self.merchant_agents[order.merchant_type]
            
            if status == OrderStatus.COMPLETED.value:
                order.completed_at = datetime.now()
                # 订单完成时自动触发上链
                if old_status != OrderStatus.COMPLETED.value:
                    # 异步触发上链，避免阻塞
                    threading.Thread(
                        target=self._async_store_order_to_blockchain,
                        args=(order,),
                        daemon=True
                    ).start()
            
            if merchant_response:
                order.merchant_response = merchant_response
            
            print(f"📝 订单状态已更新: {order_id} -> {status}")
            return True
    
    def _async_store_order_to_blockchain(self, order: Order):
        """异步将订单信息存储到区块链"""
        try:
            tx_hash = self.store_order_to_blockchain(order)
            if tx_hash:
                with self.lock:
                    order.blockchain_tx_hash = tx_hash
                print(f"✅ 订单 {order.order_id} 已成功上链，交易哈希: {tx_hash}")
            else:
                print(f"⚠️ 订单 {order.order_id} 上链失败")
        except Exception as e:
            print(f"❌ 订单 {order.order_id} 上链时发生错误: {e}")
    
    def store_order_to_blockchain(self, order: Order) -> Optional[str]:
        """将订单信息存储到区块链
        
        通过调用IotexTokenToolkit的工具，将订单数据永久记录在区块链上。
        上链信息包括：订单ID、用户ID、商家类型、商品信息、支付信息、完成时间等。
        
        Args:
            order: 要上链的订单对象
            
        Returns:
            交易哈希字符串，如果失败则返回None
        """
        if not self.blockchain_enabled:
            print("⚠️ 区块链功能未启用，跳过上链")
            return None
        
        if not self.blockchain_toolkit:
            print("⚠️ 区块链工具包未初始化，无法上链")
            return None
        
        if not self.blockchain_private_key:
            print("⚠️ 未配置区块链私钥，无法上链")
            return None
        
        if order.blockchain_tx_hash:
            print(f"ℹ️ 订单 {order.order_id} 已经上链，交易哈希: {order.blockchain_tx_hash}")
            return order.blockchain_tx_hash
        
        try:
            # 准备订单数据，包含所有需要上链的信息
            order_data = {
                "order_id": order.order_id,
                "user_id": order.user_id,
                "merchant_type": order.merchant_type,
                "product_info": order.product_info,
                "payment_info": order.payment_info,
                "shipping_address": order.shipping_address,
                "status": order.status,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "accepted_at": order.accepted_at.isoformat() if order.accepted_at else None,
                "completed_at": order.completed_at.isoformat() if order.completed_at else None,
                "timestamp": datetime.now().isoformat()
            }
            
            print(f"🔗 开始将订单 {order.order_id} 上链...")
            print(f"   订单信息: 订单ID={order.order_id}, 用户ID={order.user_id}, 商家类型={order.merchant_type}")
            print(f"   完成时间: {order.completed_at.isoformat() if order.completed_at else 'N/A'}")
            
            # 调用IotexTokenToolkit的store_order_data方法
            result = self.blockchain_toolkit.store_order_data(
                private_key=self.blockchain_private_key,
                order_data=order_data
            )
            
            if result.get("success"):
                tx_hash = result.get("transaction_hash")
                block_number = result.get("block_number")
                order_hash = result.get("order_hash")
                explorer_url = result.get("explorer_url")
                
                print(f"✅ 订单上链成功!")
                print(f"   交易哈希: {tx_hash}")
                print(f"   区块号: {block_number}")
                print(f"   订单哈希: {order_hash}")
                print(f"   浏览器链接: {explorer_url}")
                
                return tx_hash
            else:
                error_msg = result.get("error", "未知错误")
                print(f"❌ 订单上链失败: {error_msg}")
                return None
                
        except Exception as e:
            import traceback
            print(f"❌ 上链失败: {e}")
            traceback.print_exc()
            return None
    
    def notify_merchant_agent(self, order: Order) -> bool:
        """通知商家agent接单"""
        try:
            merchant_url = self.merchant_agents.get(order.merchant_type)
            if not merchant_url:
                print(f"❌ 未找到商家agent URL: {order.merchant_type}")
                return False
            
            # 检查agent是否活跃
            agent = self.agents.get(merchant_url)
            if not agent or agent.status != "active":
                print(f"⚠️ 商家agent不可用: {merchant_url}")
                return False
            
            # 构建订单通知消息
            order_message = f"""新订单需要处理：

订单ID: {order.order_id}
用户ID: {order.user_id}
商品信息: {json.dumps(order.product_info, ensure_ascii=False, indent=2)}
支付信息: {json.dumps(order.payment_info, ensure_ascii=False, indent=2)}
收货地址: {json.dumps(order.shipping_address, ensure_ascii=False, indent=2)}

请确认接单并处理此订单。"""
            
            print(f"📤 通知商家agent接单: {merchant_url} (订单: {order.order_id})")
            
            # 异步调用商家agent
            client = A2AClient(merchant_url)
            response = client.ask(order_message)
            
            if response:
                # 更新订单状态为已接单
                self.update_order_status(
                    order.order_id,
                    OrderStatus.ACCEPTED.value,
                    merchant_response=response
                )
                print(f"✅ 商家agent已接单: {order.order_id}")
                return True
            else:
                print(f"⚠️ 商家agent无响应: {order.order_id}")
                return False
                
        except Exception as e:
            print(f"❌ 通知商家agent失败: {e}")
            return False
    
    def start_order_listener(self):
        """启动订单监听线程"""
        if self.order_listener_running:
            return
        
        self.order_listener_running = True
        self.order_listener_thread = threading.Thread(target=self._order_listener_loop, daemon=True)
        self.order_listener_thread.start()
        print("👂 订单监听已启动")
    
    def stop_order_listener(self):
        """停止订单监听线程"""
        self.order_listener_running = False
        if self.order_listener_thread:
            self.order_listener_thread.join(timeout=5)
        print("👂 订单监听已停止")
    
    def _order_listener_loop(self):
        """订单监听循环 - 定期检查待处理订单并通知商家agent"""
        while self.order_listener_running:
            try:
                # 获取所有待处理的订单
                pending_orders = self.get_pending_orders("amazon")
                
                for order in pending_orders:
                    # 检查订单创建时间，避免立即通知（给系统一些处理时间）
                    time_since_creation = (datetime.now() - order.created_at).total_seconds()
                    if time_since_creation >= 1:  # 至少等待1秒
                        print(f"🔔 发现待处理订单: {order.order_id}，通知商家agent...")
                        self.notify_merchant_agent(order)
                
                # 每5秒检查一次
                time.sleep(5)
                
            except Exception as e:
                print(f"❌ 订单监听循环错误: {e}")
                time.sleep(5)


class AgentRegistryServer(A2AServer):
    """Agent注册中心A2A服务器"""
    
    def __init__(self, agent_card: AgentCard):
        super().__init__(agent_card=agent_card)
        self.registry = AgentRegistry()
        self.registry.start_heartbeat_monitor()
        print("✅ Agent注册中心服务器初始化完成")
    
    def shutdown(self):
        """关闭服务器"""
        self.registry.stop_heartbeat_monitor()
        self.registry.stop_order_listener()
    
    def handle_task(self, task):
        """处理A2A请求"""
        text = task.message.get("content", {}).get("text", "")
        print(f"📩 [AgentRegistry] 收到请求: '{text}'")
        
        try:
            # 解析请求类型
            if text.lower().strip() in ["health check", "health", "ping"]:
                response_text = "healthy - Agent Registry is operational"
                
            elif "list_all_agents" in text.lower():
                agents = self.registry.get_all_agents()
                response_text = json.dumps({"agents": agents}, indent=2, ensure_ascii=False)
                
            elif "list_active_agents" in text.lower():
                agents = self.registry.get_active_agents()
                response_text = json.dumps({"active_agents": agents}, indent=2, ensure_ascii=False)
                
            elif "find_agent_for:" in text.lower():
                # 提取能力描述
                capability = text.lower().split("find_agent_for:")[-1].strip()
                agents = self.registry.find_agents_by_capability(capability)
                response_text = json.dumps({"matching_agents": agents}, indent=2, ensure_ascii=False)
                
            elif "find_skill:" in text.lower():
                # 提取技能名称
                skill_name = text.lower().split("find_skill:")[-1].strip()
                agents = self.registry.find_agents_by_skill(skill_name)
                response_text = json.dumps({"agents_with_skill": agents}, indent=2, ensure_ascii=False)
            
            elif "create_order:" in text.lower() or text.strip().startswith("{"):
                # 处理订单创建请求
                try:
                    # 尝试解析JSON格式的订单数据
                    if text.strip().startswith("{"):
                        order_data = json.loads(text)
                    else:
                        # 从命令中提取JSON
                        json_part = text.split("create_order:")[-1].strip()
                        order_data = json.loads(json_part)
                    
                    order = self.registry.create_order(order_data)
                    if order:
                        response_text = json.dumps({
                            "success": True,
                            "message": "订单已创建并加入监听队列",
                            "order": order.to_dict()
                        }, indent=2, ensure_ascii=False)
                    else:
                        response_text = json.dumps({
                            "success": False,
                            "error": "订单创建失败"
                        }, indent=2, ensure_ascii=False)
                except json.JSONDecodeError as e:
                    response_text = json.dumps({
                        "success": False,
                        "error": f"订单数据格式错误: {str(e)}"
                    }, indent=2, ensure_ascii=False)
            
            elif "get_order:" in text.lower():
                # 查询订单信息
                order_id = text.lower().split("get_order:")[-1].strip()
                order = self.registry.get_order(order_id)
                if order:
                    response_text = json.dumps({
                        "success": True,
                        "order": order.to_dict()
                    }, indent=2, ensure_ascii=False)
                else:
                    response_text = json.dumps({
                        "success": False,
                        "error": f"订单不存在: {order_id}"
                    }, indent=2, ensure_ascii=False)
            
            elif "get_pending_orders" in text.lower():
                # 获取待处理订单列表
                merchant_type = "amazon"  # 目前只有amazon
                if "merchant:" in text.lower():
                    merchant_type = text.lower().split("merchant:")[-1].strip()
                
                orders = self.registry.get_pending_orders(merchant_type)
                response_text = json.dumps({
                    "success": True,
                    "merchant_type": merchant_type,
                    "pending_orders": [order.to_dict() for order in orders],
                    "count": len(orders)
                }, indent=2, ensure_ascii=False)
            
            elif "notify_merchant:" in text.lower():
                # 手动触发商家agent通知
                order_id = text.lower().split("notify_merchant:")[-1].strip()
                order = self.registry.get_order(order_id)
                if order:
                    success = self.registry.notify_merchant_agent(order)
                    response_text = json.dumps({
                        "success": success,
                        "message": "已通知商家agent" if success else "通知商家agent失败",
                        "order_id": order_id
                    }, indent=2, ensure_ascii=False)
                else:
                    response_text = json.dumps({
                        "success": False,
                        "error": f"订单不存在: {order_id}"
                    }, indent=2, ensure_ascii=False)
                
            else:
                response_text = """Agent注册中心支持的命令:
- list_all_agents: 列出所有注册的agent
- list_active_agents: 列出所有活跃的agent  
- find_agent_for: <能力描述> - 根据能力查找agent
- find_skill: <技能名称> - 根据技能查找agent
- create_order: <JSON订单数据> - 创建新订单并加入监听队列
- get_order: <订单ID> - 查询订单信息
- get_pending_orders [merchant: <商家类型>] - 获取待处理订单列表
- notify_merchant: <订单ID> - 手动通知商家agent接单
- health check: 健康检查"""
            
            task.status = TaskStatus(state=TaskState.COMPLETED)
            
        except Exception as e:
            print(f"❌ 处理请求失败: {e}")
            import traceback
            traceback.print_exc()
            response_text = f"错误: {str(e)}"
            task.status = TaskStatus(state=TaskState.FAILED)
        
        task.artifacts = [{"parts": [{"type": "text", "text": response_text}]}]
        return task


def main():
    """启动Agent注册中心服务器"""
    port = int(os.environ.get("AGENT_REGISTRY_PORT", 5001))
    
    agent_card = AgentCard(
        name="Agent Registry Service",
        description="Central agent registry for service discovery, health monitoring, and capability matching.",
        url=f"http://localhost:{port}",
        skills=[
            AgentSkill(name="agent_discovery", description="Discover agents by capabilities and skills."),
            AgentSkill(name="health_monitoring", description="Monitor agent health and availability."),
            AgentSkill(name="service_registry", description="Register and manage agent services."),
            AgentSkill(name="order_listening", description="Listen for new orders and notify merchant agents to accept orders."),
            AgentSkill(name="order_management", description="Manage order lifecycle and status tracking.")
        ]
    )
    
    server = AgentRegistryServer(agent_card)
    
    print("\n" + "="*80)
    print("🚀 启动Agent注册中心服务器")
    print(f"👂 监听地址: http://localhost:{port}")
    print("🔍 功能特性:")
    print("   - Agent动态注册和发现")
    print("   - 心跳监控和健康检查")
    print("   - 基于技能的智能匹配")
    print("   - 订单监听和商家agent通知")
    print("   - 订单生命周期管理")
    print("   - A2A协议兼容")
    print("="*80 + "\n")
    
    try:
        run_server(server, host="0.0.0.0", port=port)
    except KeyboardInterrupt:
        print("\n🛑 正在关闭Agent注册中心...")
        server.shutdown()
        print("✅ Agent注册中心已关闭")


if __name__ == "__main__":
    main()
