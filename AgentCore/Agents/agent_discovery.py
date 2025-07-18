#!/usr/bin/env python3
"""
Agent发现服务 - 智能路由和能力匹配
"""

import re
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from python_a2a import A2AClient


@dataclass
class AgentCapability:
    """Agent能力描述"""
    agent_name: str
    agent_url: str
    skill_name: str
    skill_description: str
    confidence_score: float = 0.0


class IntentClassifier:
    """用户意图分类器"""
    
    # 预定义的意图模式
    INTENT_PATTERNS = {
        "purchase": {
            "keywords": ["买", "购买", "purchase", "buy", "订购", "下单", "支付"],
            "patterns": [
                r"我想买.*",
                r"帮我购买.*",
                r"我要.*",
                r"buy.*",
                r"purchase.*"
            ]
        },
        "search": {
            "keywords": ["搜索", "查找", "找", "search", "find", "look for"],
            "patterns": [
                r"搜索.*",
                r"查找.*",
                r"找.*商品",
                r"search.*",
                r"find.*"
            ]
        },
        "payment": {
            "keywords": ["支付", "付款", "pay", "payment", "支付宝", "alipay"],
            "patterns": [
                r".*支付.*",
                r".*付款.*",
                r".*pay.*",
                r".*payment.*"
            ]
        },
        "amazon": {
            "keywords": ["amazon", "亚马逊", "amzn"],
            "patterns": [
                r".*amazon.*",
                r".*亚马逊.*"
            ]
        }
    }
    
    @classmethod
    def classify_intent(cls, user_input: str) -> List[str]:
        """分类用户意图"""
        user_input_lower = user_input.lower()
        detected_intents = []
        
        for intent, config in cls.INTENT_PATTERNS.items():
            # 检查关键词
            keyword_match = any(keyword in user_input_lower for keyword in config["keywords"])
            
            # 检查正则模式
            pattern_match = any(re.search(pattern, user_input_lower) for pattern in config["patterns"])
            
            if keyword_match or pattern_match:
                detected_intents.append(intent)
        
        return detected_intents if detected_intents else ["general"]


class AgentMatcher:
    """Agent匹配器"""
    
    # 能力映射规则
    CAPABILITY_MAPPING = {
        "purchase": {
            "primary_skills": ["purchase", "buy", "order", "shopping"],
            "secondary_skills": ["payment", "checkout"],
            "agent_preferences": ["amazon", "shopping"]
        },
        "payment": {
            "primary_skills": ["payment", "pay", "alipay", "transaction"],
            "secondary_skills": ["order", "checkout"],
            "agent_preferences": ["alipay", "payment"]
        },
        "search": {
            "primary_skills": ["search", "find", "product_search"],
            "secondary_skills": ["recommendation", "browse"],
            "agent_preferences": ["amazon", "shopping"]
        },
        "amazon": {
            "primary_skills": ["amazon", "shopping", "product"],
            "secondary_skills": ["search", "purchase"],
            "agent_preferences": ["amazon"]
        }
    }
    
    @classmethod
    def calculate_agent_score(cls, agent_info: Dict[str, Any], intents: List[str], user_input: str) -> float:
        """计算agent与用户需求的匹配分数"""
        total_score = 0.0
        max_possible_score = 0.0
        
        agent_name = agent_info.get("name", "").lower()
        agent_description = agent_info.get("description", "").lower()
        agent_skills = agent_info.get("skills", [])
        
        # 为每个意图计算分数
        for intent in intents:
            intent_config = cls.CAPABILITY_MAPPING.get(intent, {})
            intent_score = 0.0
            intent_max_score = 100.0  # 每个意图的最大分数
            
            # 1. 检查agent名称匹配 (30分)
            name_score = 0.0
            for pref in intent_config.get("agent_preferences", []):
                if pref in agent_name:
                    name_score = 30.0
                    break
            
            # 2. 检查主要技能匹配 (40分)
            primary_skill_score = 0.0
            for skill in agent_skills:
                skill_name = skill.get("name", "").lower()
                skill_desc = skill.get("description", "").lower()
                
                for primary_skill in intent_config.get("primary_skills", []):
                    if primary_skill in skill_name or primary_skill in skill_desc:
                        primary_skill_score = max(primary_skill_score, 40.0)
                        break
            
            # 3. 检查次要技能匹配 (20分)
            secondary_skill_score = 0.0
            for skill in agent_skills:
                skill_name = skill.get("name", "").lower()
                skill_desc = skill.get("description", "").lower()
                
                for secondary_skill in intent_config.get("secondary_skills", []):
                    if secondary_skill in skill_name or secondary_skill in skill_desc:
                        secondary_skill_score = max(secondary_skill_score, 20.0)
                        break
            
            # 4. 检查描述匹配 (10分)
            description_score = 0.0
            user_keywords = user_input.lower().split()
            matching_keywords = sum(1 for keyword in user_keywords 
                                  if len(keyword) > 2 and keyword in agent_description)
            if matching_keywords > 0:
                description_score = min(10.0, matching_keywords * 2)
            
            intent_score = name_score + primary_skill_score + secondary_skill_score + description_score
            total_score += intent_score
            max_possible_score += intent_max_score
        
        # 归一化分数到0-1范围
        if max_possible_score > 0:
            return min(1.0, total_score / max_possible_score)
        return 0.0
    
    @classmethod
    def rank_agents(cls, agents: List[Dict[str, Any]], intents: List[str], user_input: str) -> List[Dict[str, Any]]:
        """对agents按匹配度排序"""
        scored_agents = []
        
        for agent in agents:
            score = cls.calculate_agent_score(agent, intents, user_input)
            agent_copy = agent.copy()
            agent_copy["match_score"] = score
            agent_copy["matched_intents"] = intents
            scored_agents.append(agent_copy)
        
        # 按分数降序排序
        scored_agents.sort(key=lambda x: x["match_score"], reverse=True)
        return scored_agents


class AgentDiscoveryService:
    """Agent发现服务核心类"""
    
    def __init__(self, registry_url: str = "http://localhost:5001"):
        self.registry_url = registry_url
        self.intent_classifier = IntentClassifier()
        self.agent_matcher = AgentMatcher()
    
    def discover_agents_for_request(self, user_input: str) -> Dict[str, Any]:
        """为用户请求发现合适的agents"""
        try:
            # 1. 分类用户意图
            intents = self.intent_classifier.classify_intent(user_input)
            print(f"🧠 检测到的意图: {intents}")
            
            # 2. 从注册中心获取活跃的agents
            active_agents = self._get_active_agents()
            if not active_agents:
                return {
                    "success": False,
                    "error": "没有可用的活跃agents",
                    "intents": intents
                }
            
            # 3. 对agents进行匹配和排序
            ranked_agents = self.agent_matcher.rank_agents(active_agents, intents, user_input)
            
            # 4. 过滤低分数的agents
            filtered_agents = [agent for agent in ranked_agents if agent["match_score"] > 0.1]
            
            return {
                "success": True,
                "intents": intents,
                "total_agents_found": len(active_agents),
                "matching_agents": filtered_agents[:5],  # 返回前5个最匹配的
                "recommendation": self._generate_recommendation(filtered_agents, intents, user_input)
            }
            
        except Exception as e:
            print(f"❌ Agent发现失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "intents": []
            }
    
    def find_agent_for_capability(self, capability: str) -> Optional[Dict[str, Any]]:
        """为特定能力查找最佳agent"""
        try:
            discovery_result = self.discover_agents_for_request(capability)
            
            if discovery_result["success"] and discovery_result["matching_agents"]:
                return discovery_result["matching_agents"][0]  # 返回最匹配的
            
            return None
            
        except Exception as e:
            print(f"❌ 查找能力agent失败: {e}")
            return None
    
    def get_purchase_workflow_agents(self, user_input: str) -> Dict[str, Any]:
        """获取购买流程的agent工作流"""
        try:
            # 发现所有相关agents
            discovery_result = self.discover_agents_for_request(user_input)
            
            if not discovery_result["success"]:
                return discovery_result
            
            agents = discovery_result["matching_agents"]
            
            # 构建购买工作流
            workflow = {
                "user_agent": None,
                "payment_agent": None,
                "amazon_agent": None
            }
            
            # 查找各类型的agent
            for agent in agents:
                agent_name = agent["name"].lower()
                
                if "coordinator" in agent_name or "user" in agent_name:
                    workflow["user_agent"] = agent
                elif "alipay" in agent_name or "payment" in agent_name:
                    workflow["payment_agent"] = agent
                elif "amazon" in agent_name and "shopping" in agent_name:
                    workflow["amazon_agent"] = agent
            
            return {
                "success": True,
                "workflow": workflow,
                "execution_order": ["user_agent", "payment_agent", "amazon_agent"],
                "all_agents": agents
            }
            
        except Exception as e:
            print(f"❌ 获取购买工作流失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_active_agents(self) -> List[Dict[str, Any]]:
        """从注册中心获取活跃的agents"""
        try:
            client = A2AClient(self.registry_url)
            response = client.ask("list_active_agents")
            
            if response:
                data = json.loads(response)
                return data.get("active_agents", [])
            
            return []
            
        except Exception as e:
            print(f"❌ 获取活跃agents失败: {e}")
            return []
    
    def _generate_recommendation(self, agents: List[Dict[str, Any]], intents: List[str], user_input: str) -> str:
        """生成推荐说明"""
        if not agents:
            return "未找到匹配的agents"
        
        best_agent = agents[0]
        recommendation = f"推荐使用 '{best_agent['name']}' (匹配度: {best_agent['match_score']:.2f})"
        
        if "purchase" in intents:
            recommendation += "\n建议的购买流程: User Agent → Payment Agent → Amazon Agent"
        
        return recommendation


# 便捷函数
def discover_agents(user_input: str, registry_url: str = "http://localhost:5001") -> Dict[str, Any]:
    """便捷的agent发现函数"""
    service = AgentDiscoveryService(registry_url)
    return service.discover_agents_for_request(user_input)


def find_best_agent(capability: str, registry_url: str = "http://localhost:5001") -> Optional[Dict[str, Any]]:
    """查找最佳agent的便捷函数"""
    service = AgentDiscoveryService(registry_url)
    return service.find_agent_for_capability(capability)


def get_purchase_agents(user_input: str, registry_url: str = "http://localhost:5001") -> Dict[str, Any]:
    """获取购买流程agents的便捷函数"""
    service = AgentDiscoveryService(registry_url)
    return service.get_purchase_workflow_agents(user_input)


if __name__ == "__main__":
    # 测试代码
    service = AgentDiscoveryService()
    
    test_inputs = [
        "我想买一个iPhone",
        "帮我搜索笔记本电脑",
        "创建支付宝订单",
        "在Amazon上购买商品"
    ]
    
    print("🧪 测试Agent发现服务:")
    for test_input in test_inputs:
        print(f"\n📝 测试输入: {test_input}")
        result = service.discover_agents_for_request(test_input)
        
        if result["success"]:
            print(f"✅ 发现 {len(result['matching_agents'])} 个匹配的agents")
            for i, agent in enumerate(result["matching_agents"][:3]):
                print(f"   {i+1}. {agent['name']} (分数: {agent['match_score']:.2f})")
        else:
            print(f"❌ 发现失败: {result['error']}")
