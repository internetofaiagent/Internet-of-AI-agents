#!/usr/bin/env python3
"""
Amazon购物Agent - Qwen3原生版本 (移除CAMEL框架)
使用Qwen3原生API + qwen-agent MCP工具，支持多轮对话
"""

import os
import json
import traceback
import uuid
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple

# 设置环境变量 - 确保在最早时机设置
if not os.environ.get('MODELSCOPE_SDK_TOKEN'):
    os.environ['MODELSCOPE_SDK_TOKEN'] = '9d3aed4d-eca1-4e0c-9805-cb923ccbbf21'
    print("🔧 设置MODELSCOPE_SDK_TOKEN环境变量")

if not os.environ.get('FEWSATS_API_KEY'):
    os.environ['FEWSATS_API_KEY'] = 'YOUR-API-KEY'
    print("🔧 设置FEWSATS_API_KEY环境变量")

# 尝试导入qwen-agent进行MCP工具调用
try:
    from qwen_agent.agents import Assistant
    QWEN_AGENT_AVAILABLE = True
    print("✅ qwen-agent导入成功")
except ImportError as e:
    print(f"⚠️ qwen-agent导入失败: {e}")
    QWEN_AGENT_AVAILABLE = False

# 使用OpenAI客户端调用ModelScope API（作为降级选项）
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
    print("✅ OpenAI客户端导入成功")
except ImportError as e:
    print(f"⚠️ OpenAI客户端导入失败: {e}")
    OPENAI_AVAILABLE = False

class ShoppingState(Enum):
    """购物状态枚举"""
    BROWSING = "browsing"           # 浏览商品
    SELECTED = "selected"           # 已选择商品
    COLLECTING_INFO = "collecting_info"  # 收集用户信息
    ORDERING = "ordering"           # 创建订单
    PAYING = "paying"              # 支付处理
    COMPLETED = "completed"        # 完成购买
    TRACKING = "tracking"          # 订单追踪

class ThinkingMode(Enum):
    """思考模式配置"""
    ENABLED = "enabled"     # 启用思考模式（复杂推理）
    DISABLED = "disabled"   # 禁用思考模式（快速响应）
    AUTO = "auto"          # 自动切换（根据任务复杂度）

@dataclass
class UserInfo:
    """用户信息数据结构"""
    full_name: str = ""
    email: str = ""
    shipping_address: Dict[str, str] = None
    
    def __post_init__(self):
        if self.shipping_address is None:
            self.shipping_address = {
                "full_name": "",
                "address": "",
                "city": "",
                "state": "",
                "country": "",
                "postal_code": ""
            }
    
    def is_complete(self) -> bool:
        """检查用户信息是否完整"""
        return (
            bool(self.full_name and self.email) and
            all(self.shipping_address.values())
        )

@dataclass
class ProductInfo:
    """商品信息数据结构 - 扩展支持MCP搜索结果"""
    asin: str = ""
    title: str = ""
    url: str = ""
    price: str = ""
    rating: str = ""
    reviews_count: str = ""
    image_url: str = ""
    description: str = ""
    availability: str = ""
    # 新增字段支持MCP搜索结果
    extracted_price: float = 0.0
    position: int = 0
    recent_sales: str = ""
    fulfillment: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.fulfillment is None:
            self.fulfillment = {}
    
    def to_display_dict(self) -> Dict[str, Any]:
        """转换为显示格式"""
        return {
            "商品标题": self.title,
            "价格": self.price,
            "评分": self.rating,
            "评论数": self.reviews_count,
            "可用性": self.availability,
            "商品链接": self.url,
            "ASIN": self.asin
        }
    
    @classmethod
    def from_amazon_search_result(cls, search_item: Dict[str, Any]) -> 'ProductInfo':
        """从Amazon搜索结果创建ProductInfo对象"""
        return cls(
            asin=search_item.get('asin', ''),
            title=search_item.get('title', ''),
            url=search_item.get('link', ''),
            price=search_item.get('price', ''),
            rating=str(search_item.get('rating', '')),
            reviews_count=str(search_item.get('reviews', '')),
            image_url=search_item.get('thumbnail', ''),
            extracted_price=search_item.get('extracted_price', 0.0),
            position=search_item.get('position', 0),
            recent_sales=search_item.get('recent_sales', ''),
            fulfillment=search_item.get('fulfillment', {})
        )

@dataclass
class PaymentInfo:
    """支付信息数据结构"""
    order_id: str = ""
    payment_offers: Dict[str, Any] = None
    payment_status: str = "pending"
    external_id: str = ""
    payment_context_token: str = ""
    
    def __post_init__(self):
        if self.payment_offers is None:
            self.payment_offers = {}

@dataclass
class ConversationTurn:
    """对话轮次数据结构"""
    user_input: str
    ai_response: str
    timestamp: datetime
    shopping_state: ShoppingState
    tools_used: List[str]
    thinking_content: str = ""  # Qwen3思考内容

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式用于序列化"""
        return {
            'user_input': self.user_input,
            'ai_response': self.ai_response,
            'timestamp': self.timestamp.isoformat(),
            'shopping_state': self.shopping_state.value,
            'tools_used': self.tools_used,
            'thinking_content': self.thinking_content
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationTurn':
        """从字典格式创建对象"""
        return cls(
            user_input=data['user_input'],
            ai_response=data['ai_response'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            shopping_state=ShoppingState(data['shopping_state']),
            tools_used=data['tools_used'],
            thinking_content=data.get('thinking_content', '')
        )

class MCPResponseParser:
    """MCP工具响应解析器 - 简化版本，专注于支付数据"""
    
    @staticmethod
    def parse_amazon_search_response(response_content: str, max_products: int = 6) -> List[ProductInfo]:
        """解析Amazon搜索响应，提取商品列表（默认最多6个）"""
        products = []
        try:
            import re
            import json
            
            # 改进的JSON提取策略：查找完整的JSON对象，支持嵌套结构
            # 使用更复杂的正则表达式来匹配包含"position"的完整JSON对象
            json_pattern = r'\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\})*)*\})*)*"position"[^}]*\}(?:\s*(?:\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\})*)*\})*)*\})*)*'
            
            # 简化版本：逐个字符匹配平衡的大括号
            lines = response_content.split('\n')
            current_json = ""
            in_json = False
            brace_count = 0
            
            for line_num, line in enumerate(lines):
                # 🔥 优化：如果已经找到足够的商品，停止解析
                if len(products) >= max_products:
                    print(f"🎯 已收集 {max_products} 个商品，停止解析以优化性能")
                    break
                
                stripped_line = line.strip()
                
                # 检测JSON开始：单独的{或包含关键字的{开头行
                if stripped_line == '{' or (stripped_line.startswith('{') and 
                    any(keyword in stripped_line for keyword in ['position', 'asin', 'title'])):
                    in_json = True
                    current_json = stripped_line
                    brace_count = stripped_line.count('{') - stripped_line.count('}')
                elif in_json:
                    current_json += '\n' + stripped_line
                    brace_count += stripped_line.count('{') - stripped_line.count('}')
                    
                    # JSON对象完成（大括号平衡）
                    if brace_count <= 0:
                        try:
                            # 清理和解析JSON
                            cleaned_json = current_json.strip()
                            
                            # 首先检查是否包含商品相关关键字
                            if not any(keyword in cleaned_json for keyword in ['position', 'asin', 'title', 'price']):
                                # 重置状态继续寻找
                                current_json = ""
                                in_json = False
                                brace_count = 0
                                continue
                            
                            # 尝试直接解析
                            product_data = json.loads(cleaned_json)
                            
                            # 验证这是一个有效的商品数据
                            if isinstance(product_data, dict) and ('position' in product_data or 'asin' in product_data):
                                product = ProductInfo.from_amazon_search_result(product_data)
                                if product.asin and product.title:  # 确保有必要信息
                                    products.append(product)
                                    print(f"✅ 成功解析商品: {product.title[:40]}... (ASIN: {product.asin})")
                                    
                                    # 🔥 性能优化：达到限制数量后立即退出
                                    if len(products) >= max_products:
                                        break
                                else:
                                    print(f"⚠️ 商品缺少必要信息: ASIN={product.asin}, Title={product.title[:20]}...")
                            else:
                                print(f"   ⚠️ JSON对象不是有效的商品数据")
                            
                        except json.JSONDecodeError as e:
                            print(f"⚠️ JSON解析失败: {e}")
                            print(f"   尝试解析内容: {current_json[:100]}...")
                        except Exception as e:
                            print(f"⚠️ 创建ProductInfo失败: {e}")
                        
                        # 重置状态
                        current_json = ""
                        in_json = False
                        brace_count = 0
            
            # 如果没有找到足够的JSON格式商品，尝试解析文本格式（但仍然限制数量）
            if len(products) < max_products:
                print("🔄 尝试解析文本格式的商品信息...")
                text_products = MCPResponseParser._parse_text_format_products(response_content, max_products - len(products))
                products.extend(text_products)
                
        except Exception as e:
            print(f"⚠️ 解析Amazon搜索响应失败: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")
        
        # 🔥 最终安全截断：确保不超过最大数量
        if len(products) > max_products:
            products = products[:max_products]
        
        print(f"📦 从响应中提取了 {len(products)} 个有效商品（限制：{max_products}个）")
        return products
    
    @staticmethod
    def _parse_text_format_products(content: str, max_products: int = 6) -> List[ProductInfo]:
        """解析文本格式的商品信息（限制数量）"""
        products = []
        try:
            lines = content.split('\n')
            current_product = {}
            
            for line in lines:
                # 🔥 优化：达到限制数量后停止解析
                if len(products) >= max_products:
                    print(f"🎯 文本格式解析已收集 {max_products} 个商品，停止解析")
                    break
                
                line = line.strip()
                if 'ASIN:' in line or 'asin:' in line:
                    current_product['asin'] = line.split(':')[-1].strip()
                elif '标题:' in line or 'title:' in line or 'Title:' in line:
                    current_product['title'] = line.split(':', 1)[-1].strip()
                elif '价格:' in line or 'price:' in line or 'Price:' in line:
                    current_product['price'] = line.split(':', 1)[-1].strip()
                elif '链接:' in line or 'link:' in line or 'Link:' in line:
                    current_product['url'] = line.split(':', 1)[-1].strip()
                elif '评分:' in line or 'rating:' in line or 'Rating:' in line:
                    current_product['rating'] = line.split(':', 1)[-1].strip()
                elif line.startswith('---') or line.startswith('==='):
                    # 商品分隔符，保存当前商品
                    if current_product.get('asin') and current_product.get('title'):
                        product = ProductInfo(
                            asin=current_product.get('asin', ''),
                            title=current_product.get('title', ''),
                            url=current_product.get('url', ''),
                            price=current_product.get('price', ''),
                            rating=current_product.get('rating', '')
                        )
                        products.append(product)
                        
                        # 🔥 检查是否达到限制
                        if len(products) >= max_products:
                            break
                    current_product = {}
            
            # 处理最后一个商品（如果还没达到限制）
            if len(products) < max_products and current_product.get('asin') and current_product.get('title'):
                product = ProductInfo(
                    asin=current_product.get('asin', ''),
                    title=current_product.get('title', ''),
                    url=current_product.get('url', ''),
                    price=current_product.get('price', ''),
                    rating=current_product.get('rating', '')
                )
                products.append(product)
                
        except Exception as e:
            print(f"⚠️ 解析文本格式商品失败: {e}")
        
        return products
    
    @staticmethod
    def parse_payment_offers_response(response_content: str) -> Dict[str, Any]:
        """解析支付报价响应"""
        try:
            import re
            import json
            
            # 改进的支付数据解析：使用平衡括号匹配
            lines = response_content.split('\n')
            current_json = ""
            in_json = False
            brace_count = 0
            
            for line in lines:
                stripped_line = line.strip()
                
                # 检测JSON开始：包含offers、payment等关键字的行且以{开头
                if (stripped_line.startswith('{') and 
                    any(keyword in stripped_line for keyword in ['offers', 'payment_context_token', 'amount'])):
                    in_json = True
                    current_json = stripped_line
                    brace_count = stripped_line.count('{') - stripped_line.count('}')
                elif in_json:
                    current_json += '\n' + stripped_line
                    brace_count += stripped_line.count('{') - stripped_line.count('}')
                    
                    # JSON对象完成（大括号平衡）
                    if brace_count <= 0:
                        try:
                            # 清理和解析JSON
                            cleaned_json = current_json.strip()
                            
                            # 尝试直接解析
                            payment_data = json.loads(cleaned_json)
                            
                            # 验证这是一个有效的支付数据
                            if isinstance(payment_data, dict) and ('offers' in payment_data or 'payment_context_token' in payment_data):
                                print(f"✅ 成功解析支付数据")
                                return payment_data
                            
                        except json.JSONDecodeError as e:
                            print(f"⚠️ 支付数据JSON解析失败: {e}")
                            print(f"   尝试解析内容: {current_json[:100]}...")
                        except Exception as e:
                            print(f"⚠️ 处理支付数据失败: {e}")
                        
                        # 重置状态
                        current_json = ""
                        in_json = False
                        brace_count = 0
            
            # 如果没有找到完整JSON，尝试提取关键字段
            print("🔄 尝试提取支付数据的关键字段...")
            
            # 更宽松的模式匹配
            offers_pattern = r'"offers":\s*\[(.*?)\]'
            token_pattern = r'"payment_context_token":\s*"([^"]+)"'
            version_pattern = r'"version":\s*"([^"]+)"'
            
            offers_match = re.search(offers_pattern, response_content, re.DOTALL)
            token_match = re.search(token_pattern, response_content)
            version_match = re.search(version_pattern, response_content)
            
            if offers_match or token_match:
                result = {}
                
                if offers_match:
                    try:
                        offers_content = offers_match.group(1).strip()
                        # 如果内容看起来像JSON对象
                        if offers_content.startswith('{'):
                            result["offers"] = [json.loads(offers_content)]
                        else:
                            result["offers"] = []
                    except json.JSONDecodeError:
                        result["offers"] = []
                
                if token_match:
                    result["payment_context_token"] = token_match.group(1)
                
                if version_match:
                    result["version"] = version_match.group(1)
                else:
                    result["version"] = "0.2.2"
                
                if result:
                    print(f"✅ 成功提取支付数据关键字段")
                    return result
                
        except Exception as e:
            print(f"⚠️ 解析支付报价响应失败: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")
        
        return {}
    
    @staticmethod
    def extract_mcp_tool_calls(qwen_responses: List) -> List[Dict[str, Any]]:
        """从qwen-agent响应中提取MCP工具调用信息"""
        tool_calls = []
        try:
            for response in qwen_responses:
                if isinstance(response, list) and len(response) > 1:
                    for item in response:
                        if isinstance(item, dict):
                            # 检查是否包含工具调用信息
                            if 'function_call' in item or 'tool_calls' in item:
                                tool_calls.append(item)
                            # 检查内容中是否包含MCP工具的返回结果
                            elif 'content' in item and item['content']:
                                content = item['content']
                                if any(keyword in content for keyword in ['asin', 'amazon', 'offers', 'payment']):
                                    tool_calls.append(item)
        except Exception as e:
            print(f"⚠️ 提取MCP工具调用失败: {e}")
        
        return tool_calls

@dataclass
class ShoppingContext:
    """购物会话上下文 - 简化版本，仅存储必要的支付信息"""
    payment_offers: Dict[str, Any] = None
    last_payment_timestamp: datetime = None
    
    def __post_init__(self):
        if self.payment_offers is None:
            self.payment_offers = {}
        if self.last_payment_timestamp is None:
            self.last_payment_timestamp = datetime.now()
    
    def update_payment_offers(self, payment_data: Dict[str, Any]):
        """更新支付信息"""
        self.payment_offers = payment_data
        self.last_payment_timestamp = datetime.now()
        print("💾 支付信息已更新")
    
    def get_context_summary(self) -> str:
        """获取上下文摘要 - 简化版本"""
        summary_parts = []
        
        if self.payment_offers:
            summary_parts.append("💳 支付信息已准备就绪")
        
        return "\n".join(summary_parts) if summary_parts else ""

class ConversationManager:
    """对话管理器 - 增强版，支持多轮对话历史和MCP数据存储"""
    
    def __init__(self, max_history: int = 10, user_id: str = "default_user", session_id: str = None):
        self.conversation_history: List[ConversationTurn] = []
        self.max_history = max_history
        self.current_state = ShoppingState.BROWSING
        self.user_intent_history: List[str] = []
        self.user_id = user_id
        self.session_id = session_id or str(uuid.uuid4())
        
        # 多轮对话历史（qwen-agent格式）
        self.chat_history: List[Dict[str, str]] = []
        
        # 购物会话上下文
        self.shopping_context = ShoppingContext()
        
        # 创建会话历史存储目录
        self.history_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "memory_storage", "history", user_id
        )
        os.makedirs(self.history_dir, exist_ok=True)
        
        # 加载历史对话
        self._load_conversation_history()
    
    def _get_history_file_path(self) -> str:
        """获取历史文件路径"""
        return os.path.join(self.history_dir, f"{self.session_id}.json")
    
    def _load_conversation_history(self):
        """加载对话历史"""
        try:
            history_file = self._get_history_file_path()
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.conversation_history = [
                        ConversationTurn.from_dict(turn_data) 
                        for turn_data in data.get('conversation_history', [])
                    ]
                    self.chat_history = data.get('chat_history', [])
                    print(f"✅ 加载对话历史: {len(self.conversation_history)} 轮对话")
        except Exception as e:
            print(f"⚠️ 加载对话历史失败: {e}")
            self.conversation_history = []
            self.chat_history = []
    
    def _save_conversation_history(self):
        """保存对话历史"""
        try:
            history_file = self._get_history_file_path()
            data = {
                'conversation_history': [turn.to_dict() for turn in self.conversation_history],
                'chat_history': self.chat_history,
                'session_id': self.session_id,
                'user_id': self.user_id,
                'current_state': self.current_state.value,
                'last_updated': datetime.now().isoformat()
            }
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存对话历史失败: {e}")
    
    def add_turn(self, user_input: str, ai_response: str, tools_used: List[str] = None, thinking_content: str = ""):
        """添加对话轮次"""
        turn = ConversationTurn(
            user_input=user_input,
            ai_response=ai_response,
            timestamp=datetime.now(),
            shopping_state=self.current_state,
            tools_used=tools_used or [],
            thinking_content=thinking_content
        )
        
        self.conversation_history.append(turn)
        
        # 添加到多轮对话历史（qwen-agent格式）
        self.chat_history.append({"role": "user", "content": user_input})
        self.chat_history.append({"role": "assistant", "content": ai_response})
        
        # 保持历史记录在限制范围内
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
            # 同时裁剪chat_history，保留系统消息
            if len(self.chat_history) > self.max_history * 2:
                # 保留前几条重要消息和最近的对话
                self.chat_history = self.chat_history[:-self.max_history * 2]
        
        # 保存历史
        self._save_conversation_history()
    
    def update_state(self, new_state: ShoppingState):
        """更新购物状态"""
        self.current_state = new_state
    
    def get_recent_context(self, turns: int = 3) -> str:
        """获取最近的对话上下文"""
        if not self.conversation_history:
            return ""
        
        recent_turns = self.conversation_history[-turns:]
        context_parts = [f"当前状态: {self.current_state.value}"]
        
        for turn in recent_turns:
            context_parts.append(f"用户: {turn.user_input}")
            if turn.thinking_content:
                context_parts.append(f"AI思考: {turn.thinking_content[:200]}...")
            context_parts.append(f"AI回复: {turn.ai_response[:300]}...")
            if turn.tools_used:
                context_parts.append(f"使用工具: {', '.join(turn.tools_used)}")
        
        return "\n".join(context_parts)
    
    def get_chat_messages(self) -> List[Dict[str, str]]:
        """获取完整的聊天消息列表（qwen-agent格式）- 简化版本"""
        # 直接返回聊天历史，不添加复杂的购物上下文
        return self.chat_history.copy()
    
    def clear_history(self):
        """清除对话历史"""
        self.conversation_history.clear()
        self.chat_history.clear()
        try:
            history_file = self._get_history_file_path()
            if os.path.exists(history_file):
                os.remove(history_file)
        except Exception as e:
            print(f"⚠️ 清除历史文件失败: {e}")

class AmazonShoppingAgentQwen3:
    """
    Amazon购物Agent - Qwen3原生版本 (移除CAMEL框架)
    
    主要特性：
    1. 优先使用qwen-agent调用真实MCP服务
    2. 完整的多轮对话历史管理
    3. 同步实现，兼容Flask应用
    4. 移除所有模拟响应，始终尝试真实工具调用
    """
    
    def __init__(self, thinking_mode: ThinkingMode = ThinkingMode.AUTO, user_id: str = "default_user", session_id: str = None):
        # 初始化基本参数
        self.thinking_mode = thinking_mode
        self.user_id = user_id
        self.session_id = session_id or str(uuid.uuid4())
        self._initialized = False
        
        # AI模型相关
        self.qwen_agent = None
        self.openai_client = None
        
        # MCP工具相关
        self.mcp_available = False
        
        # 组件初始化
        self.conversation_manager = ConversationManager(user_id=user_id, session_id=session_id)
        self.user_info = UserInfo()
        self.selected_product = ProductInfo()
        self.payment_info = PaymentInfo()
        
        # 设置系统提示词
        self._setup_system_messages()
        
        # 立即初始化
        self.initialize()
        
        print(f"🎯 Amazon购物Agent初始化完成 (用户: {user_id}, 会话: {session_id})")
    
    def initialize(self):
        """同步初始化方法"""
        if self._initialized:
            return
        
        print("🔄 开始初始化...")
        
        # 优先初始化qwen-agent（用于MCP工具调用）
        self._initialize_qwen_agent()
        
        # 备用方案：初始化OpenAI客户端
        if not self.mcp_available:
            self._initialize_openai_client()
        
        self._initialized = True
        print("✅ Amazon购物Agent初始化完成")
    
    def _initialize_qwen_agent(self):
        """初始化qwen-agent进行MCP工具调用"""
        if not QWEN_AGENT_AVAILABLE:
            print("⚠️ qwen-agent不可用，跳过MCP工具初始化")
            return
        
        try:
            print("🔄 初始化qwen-agent MCP工具...")
            
            # 再次确保环境变量设置
            modelscope_token = os.environ.get('MODELSCOPE_SDK_TOKEN')
            if not modelscope_token:
                os.environ['MODELSCOPE_SDK_TOKEN'] = '9d3aed4d-eca1-4e0c-9805-cb923ccbbf21'
                modelscope_token = '9d3aed4d-eca1-4e0c-9805-cb923ccbbf21'
                print("🔧 重新设置MODELSCOPE_SDK_TOKEN")
            
            fewsats_key = os.environ.get('FEWSATS_API_KEY')
            if not fewsats_key:
                os.environ['FEWSATS_API_KEY'] = '3q-t95sj95DywRNY4v4QsShXfyS1Gs4uvYRnwipK4Hg'
                fewsats_key = '3q-t95sj95DywRNY4v4QsShXfyS1Gs4uvYRnwipK4Hg'
                print("🔧 重新设置FEWSATS_API_KEY")
            
            print(f"📊 环境变量状态:")
            print(f"  MODELSCOPE_SDK_TOKEN: {'已设置' if modelscope_token else '未设置'}")
            print(f"  FEWSATS_API_KEY: {'已设置' if fewsats_key else '未设置'}")
            
            # 配置LLM（使用ModelScope）- 增加超时配置
            llm_cfg = {
                'model': 'Qwen/Qwen3-32B',  # 使用完整模型名称
                'model_server': 'https://api-inference.modelscope.cn/v1/',
                'api_key': modelscope_token,
                'generate_cfg': {
                    'temperature': 0.7,
                    'max_tokens': 4096,
                    'timeout': 300,  # API调用超时时间：5分钟
                }
            }
            
            # 尝试多种MCP配置格式
            print("🔧 尝试标准MCP配置格式...")
            
            # 格式1: 标准MCP配置（参考AgentScope文档）- 增加超时配置
            tools_config_1 = [{
                "mcpServers": {
                    "amazon": {
                        "command": "uvx",
                        "args": ["amazon-mcp"],
                        "timeout": 180,  # MCP服务启动超时：3分钟
                        "initTimeout": 60  # MCP初始化超时：1分钟
                    },
                    "fewsats": {
                        "command": "uvx",
                        "args": ["fewsats-mcp"],
                        "env": {
                            "FEWSATS_API_KEY": "3q-t95sj95DywRNY4v4QsShXfyS1Gs4uvYRnwipK4Hg"
                        },
                        "timeout": 180,  # MCP服务启动超时：3分钟
                        "initTimeout": 60  # MCP初始化超时：1分钟
                    }
                }
            }]
            
            # 首先尝试格式1
            try:
                print("📝 尝试MCP配置格式1（官方推荐格式）...")
                self.qwen_agent = Assistant(llm=llm_cfg, function_list=tools_config_1)
                self.mcp_available = True
                print("✅ qwen-agent MCP工具初始化成功 (格式1)")
                return
            except Exception as e1:
                print(f"⚠️ MCP配置格式1失败: {e1}")
                
                # 格式2: 简化配置（包含两个服务）
                tools_config_2 = [
                    {
                        "mcpServers": {
                            "amazon": {
                                "command": "uvx",
                                "args": ["amazon-mcp"]
                            },
                            "fewsats": {
                                "command": "uvx",
                                "args": ["fewsats-mcp"],
                                "env": {
                                    "FEWSATS_API_KEY": "3q-t95sj95DywRNY4v4QsShXfyS1Gs4uvYRnwipK4Hg"
                                }
                            }
                        }
                    }
                ]
                
                try:
                    print("📝 尝试MCP配置格式2（Amazon + Fewsats）...")
                    self.qwen_agent = Assistant(llm=llm_cfg, function_list=tools_config_2)
                    self.mcp_available = True
                    print("✅ qwen-agent MCP工具初始化成功 (格式2)")
                    return
                except Exception as e2:
                    print(f"⚠️ MCP配置格式2失败: {e2}")
                    
                    # 格式3: 仅Amazon配置
                    tools_config_3 = [
                        {
                            "mcpServers": {
                                "amazon": {
                                    "command": "uvx",
                                    "args": ["amazon-mcp"]
                                }
                            }
                        }
                    ]
                    
                    try:
                        print("📝 尝试MCP配置格式3（仅Amazon）...")
                        self.qwen_agent = Assistant(llm=llm_cfg, function_list=tools_config_3)
                        self.mcp_available = True
                        print("✅ qwen-agent MCP工具初始化成功 (格式3)")
                        return
                    except Exception as e3:
                        print(f"⚠️ MCP配置格式3失败: {e3}")
                        
                        # 格式4: 无MCP工具，仅使用基础Assistant
                        try:
                            print("📝 尝试无MCP工具的基础Assistant...")
                            self.qwen_agent = Assistant(llm=llm_cfg)
                            self.mcp_available = False
                            print("✅ qwen-agent基础模式初始化成功（无MCP工具）")
                            return
                        except Exception as e4:
                            print(f"❌ 所有qwen-agent配置都失败: {e4}")
                            raise e4
                    
        except Exception as e:
            print(f"⚠️ qwen-agent初始化失败: {e}")
            print(f"🔍 详细错误信息: {traceback.format_exc()}")
            self.qwen_agent = None
            self.mcp_available = False
    
    def _initialize_openai_client(self):
        """初始化OpenAI客户端作为降级选项"""
        if not OPENAI_AVAILABLE:
            print("⚠️ OpenAI客户端不可用")
            return
        
        try:
            print("🔄 初始化OpenAI客户端作为降级选项...")
            
            self.openai_client = OpenAI(
                base_url='https://api-inference.modelscope.cn/v1/',
                api_key='9d3aed4d-eca1-4e0c-9805-cb923ccbbf21'
            )
            
            print("✅ OpenAI客户端初始化成功")
            
        except Exception as e:
            print(f"❌ OpenAI客户端初始化失败: {e}")
            self.openai_client = None
    
    def _setup_system_messages(self):
        """设置系统提示词 - 基于AgentScope MCP实践经验优化"""
        self.system_message = """
你是专业的Amazon购物助手，基于Qwen3模型，具备完整的商品搜索、购买和支付功能。你能帮助用户从搜索商品到完成购买的整个流程。

🎯 **核心使命**：
为用户提供完整的Amazon购物服务，包括商品搜索、比价分析、订单创建、支付处理和订单追踪。

⚡ **一键购买原则**：
- 用户提供商品URL即可直接购买，无需复杂的商品搜索和选择流程
- 一次回复内完成：获取支付报价 → 立即执行支付
- 简化用户体验，快速完成购买

🛠️ **可用MCP工具详解**：

## 🛒 Amazon MCP工具

### 1. amazon_search - 商品搜索（可选）
**功能**：在Amazon上搜索商品
**参数**：
- q (必需)：搜索关键词或产品ASIN
- domain (可选)：Amazon域名，默认amazon.com
**使用场景**：用户表达购买意图时立即调用
**示例调用**：用户说"我想买黑笔"→ 调用amazon_search(q="black pen")

### 2. amazon_get_payment_offers - 获取支付报价 ⭐ **核心工具1**
**功能**：为指定商品URL生成支付报价信息
**参数**：
- product_url (必需)：Amazon商品链接
- shipping_address (必需)：收货地址对象
- user (必需)：用户信息对象
- asin (可选)：商品ASIN编号
- quantity (可选)：购买数量，默认1

## 💳 Fewsats MCP工具

### 1. pay_offer - 支付报价 ⭐ **核心工具2**
**功能**：从l402_offers中支付指定ID的报价
**参数**：
- offer_id (字符串)：报价的字符串标识符  
- l402_offer (对象)：包含以下内容的报价详情：
  - offers：包含ID、金额、货币、描述和标题的报价对象数组
  - payment_context_token：支付上下文令牌字符串
  - payment_request_url：支付请求URL
  - version：API版本字符串
**返回**：支付状态响应

### 2. balance - 查询钱包余额
### 3. payment_methods - 查询支付方式  
### 4. payment_info - 查询支付详情
### 5. billing_info - 查询账单信息
### 6. create_x402_payment_header - 创建X402支付头

🔄 **重要指导原则 (基于AgentScope MCP实践)**：

## 📋 一键购买操作程序 (SOP)
基于简化的购买流程，严格遵循以下操作程序：

### 🚀 **一键购买SOP**（推荐流程）：
**前提**：用户提供Amazon商品URL和基本信息

1. **信息验证阶段**：
   - 确认用户提供了Amazon商品URL
   - 收集或确认用户基本信息（姓名、邮箱）
   - 收集或确认收货地址信息

2. **一键购买执行阶段**：
   - 🔥 **关键**：在同一次回复中依次调用两个工具
   - 首先调用 `amazon_get_payment_offers` 获取支付报价
   - 立即解析支付报价中的offer_id和l402_offer数据
   - 然后调用 `pay_offer` 完成支付
   - 整个过程在一次AI回复中完成

### 🔍 **备用搜索SOP**（仅当无URL时使用）：
**前提**：用户没有提供具体商品URL

1. **商品搜索阶段**：
   - 调用 `amazon_search` 获取商品列表
   - 向用户展示搜索结果
   - 用户选择具体商品并提供URL

2. **转入一键购买流程**：
   - 获得商品URL后，立即转入上述一键购买SOP

## ⚠️ 关键约束 (一键购买模式)：

### 1. **简化假设原则**
- 用户提供商品URL即表示确认购买意图
- 默认购买数量为1（除非用户明确指定）
- 优先使用用户提供的地址和信息

### 2. **连续工具调用要求** 🔥
- **必须在同一次回复中调用两个工具**：
  1. `amazon_get_payment_offers` → 获取支付报价
  2. `pay_offer` → 立即完成支付
- 不要等待用户确认，直接执行完整流程
- 两个工具调用之间不要有任何停顿或等待

### 3. **数据流转要求**
- 从`amazon_get_payment_offers`的响应中提取：
  - offer_id（通常是offers数组中第一个offer的id）
  - 完整的l402_offer对象
- 立即将这些数据传递给`pay_offer`工具

### 4. **错误处理**
- 如果第一个工具调用失败，停止流程并说明问题
- 如果第二个工具调用失败，提供支付失败的具体信息
- 不要回退到模拟数据或分步执行

## 🎯 **一键购买执行指南**：

### 🔥 **核心流程**（必须严格遵循）：
```
用户提供商品URL + 地址信息 
↓
同一次回复内：
1. 调用 amazon_get_payment_offers(product_url, user_info, shipping_address)
2. 解析响应获取 offer_id 和 l402_offer
3. 调用 pay_offer(offer_id, l402_offer)
↓
返回完整的购买结果
```

### 📋 **具体实现要求**：
1. **不要分步骤**：必须在一次AI回复中完成所有工具调用
2. **不要等待确认**：用户提供URL即表示购买确认
3. **直接处理数据**：从第一个工具的响应直接提取数据给第二个工具
4. **完整错误处理**：任何步骤失败都要明确说明并停止流程

🚨 **重要**：
- 永远不要生成虚假的商品信息、价格或订单数据
- 如果MCP工具不可用，请明确告知用户并建议替代方案
- 严格遵循一键购买流程，在同一次回复中完成两个工具调用
- 不要将购买流程分解为多个步骤或等待用户确认

💡 **一键购买数据流示例**：
```
用户："请帮我购买这个商品：https://amazon.com/dp/B0XXXXX，寄到xxx地址"
↓
AI在同一次回复中：
1. 调用 amazon_get_payment_offers(product_url="https://amazon.com/dp/B0XXXXX", ...)
2. 从响应中提取 offer_id="test_offer_1" 和完整l402_offer对象
3. 调用 pay_offer(offer_id="test_offer_1", l402_offer={...})
4. 返回购买完成的结果
```

🎯 **你的目标**：提供最简化、最高效的Amazon一键购买体验！用户提供URL即可完成购买，无需复杂的搜索和选择流程！
"""
    
    def process_request(self, user_input: str) -> str:
        """处理用户请求 - 主入口（同步版本）"""
        try:
            print(f"📝 处理用户请求: {user_input}")
            
            # 获取对话消息历史
            messages = self.conversation_manager.get_chat_messages()
            messages.append({"role": "user", "content": user_input})
            
            response = ""
            tools_used = []
            thinking_content = ""
            
            # 优先使用qwen-agent进行MCP工具调用
            if self.mcp_available and self.qwen_agent:
                try:
                    print("🔧 使用qwen-agent调用MCP工具...")
                    
                    # 调用qwen-agent
                    responses = list(self.qwen_agent.run(messages=messages))
                    if responses:
                        # 获取最后一个响应
                        last_response = responses[-1]
                        if len(last_response) > 1 and isinstance(last_response[-1], dict):
                            response = last_response[-1].get('content', '')
                            tools_used = ["qwen_agent_mcp"]
                            
                            # 🔑 关键新增：解析MCP工具调用结果（限制存储数量）
                            print("🔍 解析MCP工具调用结果...")
                            self._process_mcp_responses(responses, user_input)
                            
                            print("✅ qwen-agent MCP工具调用成功")
                        else:
                            raise Exception("qwen-agent响应格式异常")
                    else:
                        raise Exception("qwen-agent返回空响应")
                except Exception as e:
                    print(f"⚠️ qwen-agent调用失败: {e}")
                    print(f"错误详情: {traceback.format_exc()}")
                    response = ""
            
            # 降级方案：使用OpenAI客户端（不使用工具）
            if not response and self.openai_client:
                try:
                    print("🤖 降级使用OpenAI客户端...")
                    
                    # 添加系统消息
                    api_messages = [{"role": "system", "content": self.system_message}]
                    api_messages.extend(messages)
                    
                    api_response = self.openai_client.chat.completions.create(
                        model='Qwen/Qwen3-32B',
                        messages=api_messages,
                        temperature=0.7,
                        max_tokens=4096,
                        extra_body={'enable_thinking': False}
                    )
                    
                    if api_response and api_response.choices:
                        response = api_response.choices[0].message.content.strip()
                        tools_used = ["openai_api_fallback"]
                        print("✅ OpenAI客户端调用成功")
                    else:
                        raise Exception("OpenAI API返回空响应")
                
                except Exception as e:
                    print(f"❌ OpenAI客户端调用失败: {e}")
                    response = ""
            
            # 最终错误处理
            if not response:
                response = """
抱歉，当前无法连接到Amazon和支付服务。

🔧 **技术状态**：
- MCP服务暂时不可用
- 无法执行真实的商品搜索和购买操作

🌟 **建议**：
1. 请稍后重试
2. 检查网络连接
3. 或直接访问 Amazon.com 进行购买

如需帮助，请联系技术支持。
"""
                tools_used = ["error_fallback"]
            
            # 记录对话轮次
            self.conversation_manager.add_turn(
                user_input=user_input,
                ai_response=response,
                tools_used=tools_used,
                thinking_content=thinking_content
            )
            
            print(f"✅ 响应生成完成，使用工具: {tools_used}")
            return response
            
        except Exception as e:
            print(f"❌ 请求处理失败: {e}")
            print(f"🔍 详细错误: {traceback.format_exc()}")
            
            error_response = f"""
抱歉，处理您的请求时发生了错误。

错误信息：{str(e)}

请稍后重试，或联系技术支持。
"""
            
            # 记录错误
            self.conversation_manager.add_turn(
                user_input=user_input,
                ai_response=error_response,
                tools_used=["error"],
                thinking_content=f"Error: {str(e)}"
            )
            
            return error_response
    
    def _process_mcp_responses(self, qwen_responses: List, user_input: str):
        """处理MCP工具调用的响应 - 简化版本，专注于支付流程"""
        try:
            # 提取所有响应内容
            all_content = ""
            for response in qwen_responses:
                if isinstance(response, list):
                    for item in response:
                        if isinstance(item, dict) and 'content' in item:
                            all_content += item['content'] + "\n"
            
            print(f"📄 分析响应内容长度: {len(all_content)} 字符")
            
            # 仅处理支付相关响应，不存储商品信息
            if self._is_payment_offers_response(all_content):
                print("💳 检测到支付报价响应，开始解析...")
                payment_data = MCPResponseParser.parse_payment_offers_response(all_content)
                if payment_data:
                    # 临时存储支付信息用于当前会话
                    self.payment_info.payment_offers = payment_data
                    if 'payment_context_token' in payment_data:
                        self.payment_info.payment_context_token = payment_data['payment_context_token']
                    print("💾 支付报价信息已临时存储")
            
            # 检测支付完成响应
            elif "payment" in all_content.lower() and ("success" in all_content.lower() or "completed" in all_content.lower()):
                print("✅ 检测到支付完成响应")
                self.payment_info.payment_status = "completed"
            
            print("🔄 响应处理完成（简化模式）")
            
        except Exception as e:
            print(f"⚠️ 处理MCP响应失败: {e}")
            print(f"🔍 详细错误: {traceback.format_exc()}")
    
    def _is_amazon_search_response(self, content: str, user_input: str) -> bool:
        """判断是否为Amazon搜索响应（简化版本）"""
        # 简化检测逻辑，仅用于备用搜索场景
        amazon_indicators = ['asin', 'amazon.com', 'position', 'rating', 'reviews', 'price']
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in amazon_indicators)
    
    def _is_payment_offers_response(self, content: str) -> bool:
        """判断是否为支付报价响应"""
        payment_indicators = ['offers', 'payment_context_token', 'payment_request_url', 'amount', 'currency']
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in payment_indicators)
    
    def _extract_search_query(self, user_input: str) -> str:
        """从用户输入中提取搜索查询（简化版本）"""
        # 简单的查询提取逻辑，仅用于备用搜索
        query_keywords = ['搜索', '找', '买', '购买', 'search', 'find', 'buy']
        for keyword in query_keywords:
            if keyword in user_input:
                parts = user_input.split(keyword, 1)
                if len(parts) > 1:
                    return parts[1].strip()
        return user_input.strip()
    
    def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            "agent_type": "Amazon Shopping Agent Qwen3 (MCP Native)",
            "version": "3.1.0",
            "thinking_mode": self.thinking_mode.value,
            "qwen_agent_available": QWEN_AGENT_AVAILABLE,
            "openai_available": OPENAI_AVAILABLE,
            "mcp_available": self.mcp_available,
            "conversation_turns": len(self.conversation_manager.conversation_history),
            "current_state": self.conversation_manager.current_state.value,
            "user_id": self.user_id,
            "session_id": self.session_id
        }
    
    def get_shopping_state(self) -> Dict[str, Any]:
        """获取购物状态"""
        return {
            "current_state": self.conversation_manager.current_state.value,
            "user_info_complete": self.user_info.is_complete(),
            "product_selected": bool(self.selected_product.asin),
            "conversation_turns": len(self.conversation_manager.conversation_history),
            "mcp_available": self.mcp_available,
            "thinking_mode": self.thinking_mode.value,
            "user_id": self.user_id,
            "session_id": self.session_id
        }
    
    def get_conversation_history(self) -> List[ConversationTurn]:
        """获取对话历史"""
        return self.conversation_manager.conversation_history
    
    def clear_conversation_history(self):
        """清除对话历史"""
        self.conversation_manager.clear_history()
        print("🧹 对话历史已清除")
    
    def create_new_session(self, title: str = None) -> str:
        """创建新会话"""
        new_session_id = str(uuid.uuid4())
        # 创建新的对话管理器
        self.conversation_manager = ConversationManager(user_id=self.user_id, session_id=new_session_id)
        self.session_id = new_session_id
        return new_session_id
    
    def get_sessions_list(self) -> List[Dict[str, Any]]:
        """获取会话列表"""
        try:
            sessions = []
            history_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "memory_storage", "history", self.user_id
            )
            if os.path.exists(history_dir):
                for filename in os.listdir(history_dir):
                    if filename.endswith('.json'):
                        session_id = filename[:-5]  # 移除.json后缀
                        filepath = os.path.join(history_dir, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                sessions.append({
                                    'session_id': session_id,
                                    'title': f"对话 {session_id[:8]}",
                                    'last_updated': data.get('last_updated', ''),
                                    'message_count': len(data.get('conversation_history', [])),
                                    'current_state': data.get('current_state', 'browsing')
                                })
                        except Exception as e:
                            print(f"⚠️ 读取会话文件失败 {filename}: {e}")
            
            # 按最后更新时间排序
            sessions.sort(key=lambda x: x['last_updated'], reverse=True)
            return sessions
            
        except Exception as e:
            print(f"⚠️ 获取会话列表失败: {e}")
            return []
    
    def delete_session(self, session_id: str) -> bool:
        """删除指定会话"""
        try:
            history_file = os.path.join(
                os.path.dirname(__file__), "..", "..", "memory_storage", "history", 
                self.user_id, f"{session_id}.json"
            )
            if os.path.exists(history_file):
                os.remove(history_file)
                return True
            return False
        except Exception as e:
            print(f"⚠️ 删除会话失败: {e}")
            return False
    
    def get_session_conversation_history(self) -> List[Dict[str, Any]]:
        """获取当前会话的对话历史"""
        history_data = []
        for turn in self.conversation_manager.conversation_history:
            history_data.append(turn.to_dict())
        return history_data

# 同步测试函数
def test_qwen3_agent():
    """测试Qwen3 Agent"""
    print("🧪 测试Amazon Shopping Agent Qwen3 (MCP Native)...")
    
    agent = AmazonShoppingAgentQwen3(ThinkingMode.AUTO)
    
    try:
        # 测试请求
        test_messages = [
            "你好",
            "我想买一个iPhone 15 Pro",
            "帮我搜索苹果手机"
        ]
        
        for message in test_messages:
            print(f"👤 用户: {message}")
            response = agent.process_request(message)
            print(f"🤖 Assistant: {response}")
    
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    test_qwen3_agent() 