#!/usr/bin/env python3
"""
Agent注册中心 - 支持agent动态注册、心跳检测和服务发现
"""

import os
import json
import time
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from python_a2a import A2AServer, run_server, AgentCard, AgentSkill, TaskStatus, TaskState, A2AClient


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
        
        # 预注册已知的agent
        self._preregister_known_agents()
    
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


class AgentRegistryServer(A2AServer):
    """Agent注册中心A2A服务器"""
    
    def __init__(self, agent_card: AgentCard):
        super().__init__(agent_card=agent_card)
        self.registry = AgentRegistry()
        self.registry.start_heartbeat_monitor()
        print("✅ Agent注册中心服务器初始化完成")
    
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
                
            else:
                response_text = """Agent注册中心支持的命令:
- list_all_agents: 列出所有注册的agent
- list_active_agents: 列出所有活跃的agent  
- find_agent_for: <能力描述> - 根据能力查找agent
- find_skill: <技能名称> - 根据技能查找agent
- health check: 健康检查"""
            
            task.status = TaskStatus(state=TaskState.COMPLETED)
            
        except Exception as e:
            print(f"❌ 处理请求失败: {e}")
            response_text = f"错误: {str(e)}"
            task.status = TaskStatus(state=TaskState.FAILED)
        
        task.artifacts = [{"parts": [{"type": "text", "text": response_text}]}]
        return task
    
    def shutdown(self):
        """关闭服务器"""
        self.registry.stop_heartbeat_monitor()


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
            AgentSkill(name="service_registry", description="Register and manage agent services.")
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
