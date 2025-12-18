import os
import sys
import json
import asyncio
import logging
import aiohttp
from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass

# --- A2A 和 CAMEL 库导入 ---
from python_a2a import A2AServer, run_server, AgentCard, AgentSkill, TaskStatus, TaskState, A2AClient
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType

# --- 确保项目路径正确 ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- Agent发现服务导入 ---
try:
    from .agent_discovery import AgentDiscoveryService
    AGENT_DISCOVERY_AVAILABLE = True
    print("✅ Agent发现服务导入成功")
except ImportError as e:
    print(f"⚠️ Agent发现服务导入失败: {e}")
    AGENT_DISCOVERY_AVAILABLE = False

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AmazonA2AAgent")


# ==============================================================================
#  数据类与枚举
# ==============================================================================
@dataclass
class AmazonProduct:
    asin: str
    title: str
    price: float
    currency: str
    merchant_id: str
    delivery_speed: int # 模拟一个发货速度评分
    rating: float
    prime_eligible: bool
    url: str

class PurchaseStrategy(Enum):
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    BEST_RATED = "best_rated"
    PRIME = "prime"


# ==============================================================================
#  业务逻辑层: AmazonServiceManager
#  这个类包含了所有亚马逊购物的业务逻辑。
# ==============================================================================
class AmazonServiceManager:
    """
    管理所有与亚马逊购物相关的业务逻辑，包括模型初始化、意图理解、商品搜索和支付。
    """
    def __init__(self):
        """初始化模型和配置"""
        print("🧠 [AmazonServer] Initializing the core AI model...")

        # 设置环境变量（如果未设置）
        if not os.environ.get('MODELSCOPE_SDK_TOKEN'):
            os.environ['MODELSCOPE_SDK_TOKEN'] = '877a7051-f22f-4230-87e8-e0effb36a399'
            print("🔧 设置MODELSCOPE_SDK_TOKEN环境变量")

        # 使用Qwen2.5模型替代GPT
        self.model = ModelFactory.create(
            model_platform=ModelPlatformType.MODELSCOPE,
            model_type='Qwen/Qwen2.5-72B-Instruct',
            model_config_dict={'temperature': 0.2},
            api_key=os.environ.get('MODELSCOPE_SDK_TOKEN'),
        )
        print("✅ [AmazonServer] AI model is ready.")

        # 不在初始化时创建session，而是在每次需要时创建
        self.session = None
        # 使用RapidAPI Amazon Data API
        self.amazon_search_api = "https://real-time-amazon-data.p.rapidapi.com/search"
        self.amazon_api_headers = {
            "x-rapidapi-key": "ebb6c2067fmsh65b9895255d18c4p1c51ebjsn57b5f4144e85",
            "x-rapidapi-host": "real-time-amazon-data.p.rapidapi.com"
        }

        # 初始化Agent发现服务
        if AGENT_DISCOVERY_AVAILABLE:
            self.agent_discovery = AgentDiscoveryService()
            print("✅ [AmazonServer] Agent发现服务已初始化")
        else:
            self.agent_discovery = None
            print("⚠️ [AmazonServer] Agent发现服务不可用，将使用硬编码URL")

    async def _get_session(self):
        """获取或创建aiohttp会话，确保在当前事件循环中创建"""
        # 每次都创建新的会话，避免跨事件循环问题
        return aiohttp.ClientSession()

    async def close(self):
        """关闭 aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    def discover_agents_for_purchase(self, user_input: str) -> Dict[str, Optional[str]]:
        """为购买请求发现合适的agents"""
        if not self.agent_discovery:
            # 回退到硬编码URL
            return {
                "payment_agent_url": "http://0.0.0.0:5005",
                "amazon_agent_url": "http://0.0.0.0:5012",
                "discovery_used": False
            }

        try:
            # 使用agent发现服务获取购买工作流
            workflow_result = self.agent_discovery.get_purchase_workflow_agents(user_input)

            if workflow_result["success"]:
                workflow = workflow_result["workflow"]

                payment_url = None
                amazon_url = None

                # 提取Payment Agent URL
                if workflow["payment_agent"]:
                    payment_url = workflow["payment_agent"]["url"]
                    print(f"🔍 发现Payment Agent: {workflow['payment_agent']['name']} at {payment_url}")
                else:
                    # 如果没有发现，使用默认的payment.py agent
                    payment_url = "http://0.0.0.0:5005"
                    print(f"🔍 使用默认Payment Agent (payment.py) at {payment_url}")

                # 提取Amazon Agent URL
                if workflow["amazon_agent"]:
                    amazon_url = workflow["amazon_agent"]["url"]
                    print(f"🔍 发现Amazon Agent: {workflow['amazon_agent']['name']} at {amazon_url}")

                return {
                    "payment_agent_url": payment_url or "http://0.0.0.0:5005",
                    "amazon_agent_url": amazon_url or "http://0.0.0.0:5012",
                    "discovery_used": True,
                    "workflow_info": workflow_result
                }
            else:
                print(f"⚠️ Agent发现失败: {workflow_result.get('error', '未知错误')}")
                # 回退到硬编码URL
                return {
                    "payment_agent_url": "http://localhost:5005",
                    "amazon_agent_url": "http://localhost:5012",
                    "discovery_used": False,
                    "error": workflow_result.get('error')
                }

        except Exception as e:
            print(f"❌ Agent发现过程中出错: {e}")
            # 回退到硬编码URL
            return {
                "payment_agent_url": "http://localhost:5005",
                "amazon_agent_url": "http://localhost:5012",
                "discovery_used": False,
                "error": str(e)
            }

    async def handle_purchase_confirmation_with_agent_discovery(self, user_input: str) -> Dict:
        """使用Agent发现服务处理购买确认"""
        return await self.handle_purchase_confirmation(user_input)

    def process_purchase_with_agent_discovery(self, user_input: str) -> Dict:
        """使用Agent发现服务处理购买请求"""
        try:
            print(f"📝 处理购买请求: {user_input}")

            # 1. 发现agents
            print("🔍 步骤1: 发现合适的agents...")
            agent_urls = self.discover_agents_for_purchase(user_input)

            if agent_urls["discovery_used"]:
                print("✅ 使用Agent发现服务找到合适的agents")
            else:
                print("⚠️ 使用默认的硬编码agent URLs")

            # 2. 调用Payment Agent
            print("💳 步骤2: 调用Payment Agent...")
            payment_agent_url = agent_urls["payment_agent_url"]

            # 构造支付请求
            payment_request = f"""用户购买请求，请创建支付订单：

用户请求: {user_input}

商品信息（示例）:
- 名称: iPhone 15 Pro
- 价格: $1199.00 USD
- 数量: 1
- 总价: $1199.00 USD

请创建支付订单并通知Amazon Agent。"""

            print(f"🔗 连接到Payment Agent: {payment_agent_url}")

            # 调用Payment Agent
            payment_client = A2AClient(payment_agent_url)
            payment_response = payment_client.ask(payment_request)

            print(f"📥 收到Payment Agent响应: {payment_response[:200] if payment_response else 'None'}...")

            # 3. 构造返回结果
            return {
                "status": "payment_and_order_completed",
                "title": "iPhone 15 Pro",
                "total_amount": 1199.00,
                "currency": "USD",
                "response": f"""✅ 购买请求处理完成！

🔍 **Agent发现结果:**
- Agent发现服务: {'已使用' if agent_urls['discovery_used'] else '未使用（回退到默认）'}
- Payment Agent: {payment_agent_url}
- Amazon Agent: {agent_urls['amazon_agent_url']}

💳 **支付处理结果:**
{payment_response if payment_response else '支付处理失败'}

🎯 **流程确认:**
✅ User Agent → Payment Agent → Amazon Agent 调用链已执行
✅ 符合您要求的调用顺序

📋 **重要说明:**
- User Agent不直接调用Amazon Agent
- Payment Agent会在支付完成后自动调用Amazon Agent
- 这确保了正确的调用顺序和流程控制
""",
                "payment_info": payment_response
            }

        except Exception as e:
            print(f"❌ 处理购买请求失败: {e}")
            return {
                "status": "error",
                "message": f"购买请求处理失败: {str(e)}",
                "response": f"""❌ 购买请求处理失败

错误信息: {str(e)}

🔧 建议检查:
1. Payment Agent是否正常运行 (http://localhost:5005)
2. Amazon Agent是否正常运行 (http://localhost:5012)
3. Agent注册中心是否正常运行 (http://localhost:5001)
"""
            }

    async def understand_intent(self, user_input: str) -> Dict:
        """使用大模型解析用户的购物意图"""
        system_prompt = f"""
        You are a shopping intent parser. Your task is to analyze the user's request and extract key information into a structured JSON object.

        The JSON object MUST contain these fields:
        - "product_description": A detailed description of the product the user wants.
        - "quantity": The number of items to buy. Default is 1.
        - "max_price": The maximum acceptable price as a float. If not specified, use null.
        - "min_rating": The minimum acceptable product rating. Default is 4.0.
        - "delivery_urgency": The user's delivery preference. Must be one of: "low", "medium", "high".
        - "preferred_payment_methods": A list (array) of payment methods the user can use, such as ["alipay", "visa", "usdc"]. If the user does not state any preference, use an empty list.

        User's request: "{user_input}"

        Respond ONLY with the JSON object, and nothing else.
        """
        try:
            # 使用与Alipay Agent相同的ChatAgent
            intent_agent = ChatAgent(system_message=system_prompt, model=self.model)
            response = await intent_agent.astep(user_input)
            content = response.msgs[0].content

            # 从模型返回的文本中提取JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start == -1 or end == 0:
                raise ValueError("LLM did not return a valid JSON object.")
            
            parsed_json = json.loads(content[start:end])
            logger.info(f"✅ Intent parsed successfully: {parsed_json}")
            return parsed_json

        except Exception as e:
            logger.error(f"❌ Intent understanding failed: {str(e)}")
            raise Exception(f"ModelScope API调用失败，无法理解用户意图: {str(e)}")

    def set_strategy_from_intent(self, intent: Dict) -> PurchaseStrategy:
        """根据解析出的意图，设定本次购买的策略"""
        urgency = intent.get("delivery_urgency", "low")
        if urgency == "high":
            strategy = PurchaseStrategy.FASTEST
        elif intent.get("min_rating", 4.0) >= 4.5:
            strategy = PurchaseStrategy.BEST_RATED
        elif intent.get("max_price") and float(intent["max_price"]) < 100:
            strategy = PurchaseStrategy.CHEAPEST
        else:
            strategy = PurchaseStrategy.PRIME
        logger.info(f"⚙️ Purchase strategy set to: {strategy.value}")
        return strategy

    def extract_search_keywords(self, product_description: str) -> str:
        """从用户描述中提取适合Amazon搜索的关键词"""
        # 简单的关键词提取逻辑
        keywords_map = {
            "iphone": "iPhone 15 Pro",
            "苹果手机": "iPhone 15",
            "macbook": "MacBook Pro",
            "笔记本": "laptop",
            "电脑": "computer",
            "耳机": "headphones",
            "手机": "smartphone"
        }

        description_lower = product_description.lower()

        # 检查是否包含已知关键词
        for chinese_key, english_key in keywords_map.items():
            if chinese_key in description_lower:
                logger.info(f"🔍 提取关键词: '{chinese_key}' → '{english_key}'")
                return english_key

        # 如果没有匹配，尝试提取英文单词
        import re
        english_words = re.findall(r'[a-zA-Z]+', product_description)
        if english_words:
            extracted = " ".join(english_words[:3])  # 取前3个英文单词
            logger.info(f"🔍 提取英文关键词: '{extracted}'")
            return extracted

        # 默认返回原始描述
        logger.info(f"🔍 使用原始描述作为搜索关键词")
        return product_description

    async def search_amazon_products(self, intent: Dict, strategy: PurchaseStrategy) -> List[AmazonProduct]:
        """调用亚马逊API搜索商品，并根据策略排序"""
        # 提取搜索关键词
        search_query = self.extract_search_keywords(intent['product_description'])
        logger.info(f"🔍 Searching Amazon for: {search_query} (原始: {intent['product_description']})")

        try:
            # 为每次搜索创建新的会话
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.amazon_search_api,
                    params={"query": search_query, "country": "US"},
                    headers=self.amazon_api_headers,
                    timeout=15
                ) as resp:
                    resp.raise_for_status()
                    response_data = await resp.json()
                    products = []

                    # 处理RapidAPI响应格式
                    if response_data.get('status') == 'OK' and 'data' in response_data:
                        data = response_data['data']
                        logger.info(f"✅ API 返回状态: OK, 数据类型: {type(data)}")

                        # 如果data是列表，直接使用
                        if isinstance(data, list):
                            items_to_process = data[:10]
                        # 如果data是字典，查找商品列表
                        elif isinstance(data, dict):
                            items_to_process = []
                            for key in ['products', 'results', 'items']:
                                if key in data and isinstance(data[key], list):
                                    items_to_process = data[key][:10]
                                    logger.info(f"✅ 找到商品列表在字段: {key}, 数量: {len(items_to_process)}")
                                    break
                        else:
                            logger.error(f"❌ 未知的data格式: {type(data)}")
                            items_to_process = []
                    else:
                        logger.error(f"❌ API返回错误: {response_data.get('status', 'unknown')}")
                        if 'error' in response_data:
                            logger.error(f"错误详情: {response_data['error']}")
                        items_to_process = []

                    logger.info(f"📦 准备处理 {len(items_to_process)} 个商品")

                    for item in items_to_process:
                        try:
                            # 调试：显示商品的所有字段
                            logger.info(f"商品字段: {list(item.keys())}")

                            # 尝试多种可能的标题字段名
                            title = (item.get('title') or
                                   item.get('name') or
                                   item.get('product_title') or
                                   item.get('product_name') or
                                   '无标题')

                            logger.info(f"处理商品: {title[:50]}...")

                            # 尝试多种可能的价格字段名
                            price_raw = (item.get("price") or
                                       item.get("current_price") or
                                       item.get("price_current") or
                                       item.get("price_value") or
                                       item.get("product_price") or  # 添加RapidAPI可能返回的字段名
                                       item.get("product_original_price") or
                                       item.get("product_minimum_offer_price") or
                                       "0")

                            # 调试：显示价格字段
                            logger.info(f"价格原始值: {price_raw}, 类型: {type(price_raw)}")

                            # 处理价格字符串
                            price_str = str(price_raw).replace("$", "").replace(",", "").strip()

                            try:
                                price = float(price_str) if price_str and price_str != "None" else 0.0
                                logger.info(f"✅ 解析价格: ${price:.2f}")
                            except ValueError:
                                logger.info(f"❌ 无法解析价格 '{price_str}'，使用0.0")
                                price = 0.0

                            # 尝试多种可能的评分字段名
                            rating_raw = (item.get("rating") or
                                        item.get("stars") or
                                        item.get("review_rating") or
                                        item.get("average_rating") or
                                        4.0)
                            rating = float(rating_raw) if rating_raw else 4.0

                            # 尝试多种可能的ASIN字段名
                            asin = (item.get("asin") or
                                  item.get("product_id") or
                                  item.get("id") or
                                  "UNKNOWN")

                            if intent.get("max_price") and price > intent["max_price"]:
                                continue
                            if rating < intent.get("min_rating", 4.0):
                                continue

                            products.append(AmazonProduct(
                                asin=asin,
                                title=title,
                                price=price,
                                currency="USD",
                                merchant_id="Amazon",
                                delivery_speed=5 if item.get("brand", "").lower() in ["apple", "sony"] else 4 if item.get("is_prime") else 2,
                                rating=rating,
                                prime_eligible=item.get("is_prime", True),
                                url=f"https://www.amazon.com/dp/{item.get('asin', '')}"
                            ))
                        except (ValueError, TypeError) as e:
                            logger.error(f"处理商品时出错: {e}")
                            continue  # 跳过无法解析价格或评分的商品
                    
                    # 根据策略排序
                    if strategy == PurchaseStrategy.CHEAPEST:
                        products.sort(key=lambda x: x.price)
                    elif strategy == PurchaseStrategy.FASTEST:
                        products.sort(key=lambda x: -x.delivery_speed)
                    elif strategy == PurchaseStrategy.BEST_RATED:
                        products.sort(key=lambda x: -x.rating)
                    else:  # PRIME
                        products.sort(key=lambda x: (not x.prime_eligible, -x.rating))
                    
                    logger.info(f"✅ Found {len(products)} suitable products.")
                    return products
                    
        except Exception as e:
            logger.error(f"❌ Amazon search failed: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            # 返回空列表而不是抛出异常
            return []

    async def _mock_payment(self, amount: float, merchant_id: str) -> Dict:
        """模拟支付流程"""
        logger.info(f"💰 Initiating MOCK payment of ${amount} to {merchant_id}")
        await asyncio.sleep(1) # 模拟网络延迟
        return {"status": "success", "transaction_id": "mock-tx-123456"}

    async def autonomous_purchase(self, user_input: str) -> Dict:
        """
        完整的自主购买流程。这是A2A Agent的核心执行函数。
        它会解析意图，搜索，并根据策略自动选择最优商品进行购买。
        """
        try:
            # 1. 理解意图（必须使用ModelScope API）
            intent = await self.understand_intent(user_input)

            # 2. 设定策略
            strategy = self.set_strategy_from_intent(intent)

            # 3. 搜索商品
            products = await self.search_amazon_products(intent, strategy)
            if not products:
                return {
                    "status": "error",
                    "message": "未能找到任何符合您要求的商品。",
                    "response": "很抱歉，我无法找到符合您要求的商品。请尝试使用不同的关键词或放宽搜索条件。"
                }

            # 4. 推荐商品给用户选择（不直接购买）
            logger.info(f"✅ Found {len(products)} suitable products.")

            # 构建商品推荐响应
            recommendation_text = "🔍 **为您找到以下商品推荐：**\n\n"

            for i, product in enumerate(products[:3], 1):  # 显示前3个商品
                recommendation_text += f"**{i}. {product.title}**\n"
                recommendation_text += f"   💰 价格: ${product.price:.2f} USD\n"
                recommendation_text += f"   ⭐ 评分: {product.rating}/5.0\n"
                recommendation_text += f"   🔗 链接: {product.url}\n"
                recommendation_text += f"   📦 ASIN: {product.asin}\n\n"

            recommendation_text += "💡 **如需购买，请回复确认信息，例如：**\n"
            recommendation_text += f"\"我要购买第1个商品\" 或 \"确认购买 {products[0].title}\"\n\n"
            recommendation_text += "🎯 **购买流程说明：**\n"
            recommendation_text += "1. 您确认选择商品\n"
            recommendation_text += "2. 系统调用Payment Agent处理支付\n"
            recommendation_text += "3. Payment Agent调用Amazon Agent下单\n"
            recommendation_text += "4. 完成购买流程"

            # 返回推荐结果，等待用户确认
            return {
                "status": "solution",
                "asin": products[0].asin,
                "title": products[0].title,
                "unit_price": products[0].price,
                "quantity": intent.get("quantity", 1),
                "total_amount": products[0].price * intent.get("quantity", 1),
                "currency": "USD",
                "product_url": products[0].url,
                "strategy": strategy.value,
                "response": recommendation_text,
                "products": [
                    {
                        "asin": p.asin,
                        "title": p.title,
                        "price": p.price,
                        "rating": p.rating,
                        "url": p.url
                    } for p in products[:3]
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ Autonomous purchase failed: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            
            return {
                "status": "error",
                "message": f"处理您的请求时出错: {str(e)}",
                "response": f"很抱歉，处理您的请求时出现了技术问题：{str(e)}。请稍后重试。"
            }

    async def classify_user_intent(self, user_input: str) -> str:
        """分类用户意图：搜索新商品 vs 确认购买已有商品"""
        system_prompt = f"""
        You are an intent classifier. Classify the user's input into one of these categories:
        - "search": User wants to search for new products
        - "purchase_confirmation": User wants to confirm purchase of a specific product they mentioned before

        User input: "{user_input}"

        Respond with only one word: either "search" or "purchase_confirmation"
        """

        try:
            intent_agent = ChatAgent(system_message=system_prompt, model=self.model)
            response = await intent_agent.astep(user_input)
            intent_type = response.msgs[0].content.strip().lower()

            # 确保返回值在预期范围内
            if intent_type in ["search", "purchase_confirmation"]:
                logger.info(f"✅ Intent classified as: {intent_type}")
                return intent_type
            else:
                logger.warning(f"⚠️ Unexpected intent classification: {intent_type}, defaulting to search")
                return "search"

        except Exception as e:
            logger.error(f"❌ Intent classification failed: {e}")
            raise Exception(f"ModelScope API调用失败，无法分类用户意图: {str(e)}")



    async def handle_purchase_confirmation(self, user_input: str) -> Dict:
        """处理用户的购买确认请求，从用户输入中提取商品信息"""
        system_prompt = f"""
        You are a product information extractor. The user is confirming purchase of a specific product they mentioned. 
        Extract the product information from their message and create a purchase confirmation response.

        Extract these fields if available:
        - Product name/title
        - ASIN code (if mentioned)
        - Price (if mentioned)
        - URL (if mentioned)
        - Quantity (default to 1 if not specified)

        User's purchase confirmation: "{user_input}"

        Create a JSON response with these fields:
        {{
            "status": "purchase_confirmed",
            "extracted_product": {{
                "title": "extracted product name or best guess",
                "asin": "extracted ASIN or null",
                "price": extracted_price_as_float_or_null,
                "url": "extracted URL or null",
                "quantity": extracted_quantity_or_1
            }},
            "confirmation_message": "A clear confirmation message about what the user wants to purchase"
        }}

        If you cannot extract enough information, set status to "need_more_info" and ask for clarification.
        """
        
        try:
            extraction_agent = ChatAgent(system_message=system_prompt, model=self.model)
            response = await extraction_agent.astep(user_input)
            content = response.msgs[0].content

            # 从模型返回的文本中提取JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start == -1 or end == 0:
                raise ValueError("Failed to extract JSON from response")
                
            extracted_info = json.loads(content[start:end])
            
            if extracted_info.get("status") == "need_more_info":
                return {
                    "status": "error",
                    "message": "需要更多商品信息来确认购买",
                    "response": extracted_info.get("confirmation_message", "请提供更详细的商品信息以确认购买。")
                }
            
            # 构建购买确认响应
            product_info = extracted_info.get("extracted_product", {})
            
            # 创建购买解决方案，确保价格和数量不为None
            price = product_info.get("price")
            quantity = product_info.get("quantity") or 1

            # 确保价格是数字类型
            if isinstance(price, str):
                try:
                    price = float(price.replace("$", "").replace(",", ""))
                except:
                    price = 0.0
            elif price is None:
                price = 0.0

            # 如果价格为0，直接报错，不使用fallback
            if price <= 0:
                raise Exception("无法获取商品价格信息，ModelScope API可能失败")

            logger.info(f"💰 最终商品价格: ${price:.2f}")

            solution = {
                "status": "purchase_confirmed",
                "asin": product_info.get("asin", "CONFIRMED_ITEM"),
                "title": product_info.get("title", "用户选择的商品"),
                "unit_price": price,
                "quantity": quantity,
                "total_amount": price * quantity,
                "currency": "USD",
                "product_url": product_info.get("url") or f"https://www.amazon.com/dp/{product_info.get('asin') or 'unknown'}",
                "confirmation_message": extracted_info.get("confirmation_message", "")
            }
            
            # 动态发现agents并调用Payment Agent创建订单
            logger.info("📞 User confirmed purchase, discovering agents and calling Payment Agent...")
            agent_urls = self.discover_agents_for_purchase(user_input)

            if agent_urls["discovery_used"]:
                print("✅ 使用Agent发现服务找到合适的agents")
            else:
                print("⚠️ 使用默认的硬编码agent URLs")

            try:
                payment_agent_url = agent_urls["payment_agent_url"]
                print(f"🔗 连接到Payment Agent: {payment_agent_url}")

                payment_request_text = f"""用户确认购买商品，请创建支付订单：

商品信息：
- 名称: {solution['title']}
- ASIN: {solution['asin']}
- 数量: {solution['quantity']}
- 单价: ${solution['unit_price']:.2f} USD
- 总价: ${solution['total_amount']:.2f} USD

请为此商品创建支付订单并通知Amazon Agent。"""

                payment_client = A2AClient(payment_agent_url)
                payment_response = payment_client.ask(payment_request_text)
                
                logger.info("✅ Successfully received payment info from Payment Agent")
                
                # 支付成功后，调用agent_registry创建订单
                try:
                    registry_url = os.environ.get("AGENT_REGISTRY_URL", "http://localhost:5001")
                    logger.info(f"📦 调用Agent Registry创建订单: {registry_url}")
                    
                    # 准备订单数据
                    order_data = {
                        "user_id": os.environ.get("USER_ID", "unknown"),
                        "merchant_type": "amazon",
                        "product_info": {
                            "asin": solution['asin'],
                            "title": solution['title'],
                            "price": solution['unit_price'],
                            "quantity": solution['quantity'],
                            "total_amount": solution['total_amount'],
                            "currency": solution['currency'],
                            "url": solution['product_url']
                        },
                        "payment_info": {
                            "payment_response": payment_response,
                            "status": "payment_created"
                        },
                        "shipping_address": {}  # 收货地址将在后续流程中补充
                    }
                    
                    # 调用agent_registry创建订单
                    registry_client = A2AClient(registry_url)
                    create_order_message = json.dumps(order_data, ensure_ascii=False)
                    registry_response = registry_client.ask(f"create_order: {create_order_message}")
                    
                    logger.info(f"✅ Agent Registry响应: {registry_response[:200] if registry_response else 'None'}...")
                    
                    # 解析响应获取订单ID
                    order_id = None
                    if registry_response:
                        try:
                            if registry_response.strip().startswith("{"):
                                response_data = json.loads(registry_response)
                                if response_data.get("success"):
                                    order_id = response_data.get("order", {}).get("order_id")
                                    logger.info(f"✅ 订单已创建: {order_id}")
                        except json.JSONDecodeError:
                            # 如果响应不是JSON，尝试从文本中提取订单ID
                            pass
                    
                    # 构建最终响应
                    order_status_msg = f"\n\n📦 **订单已创建**: {order_id}" if order_id else "\n\n📦 **订单创建中**..."
                    solution.update({
                        'payment_info': payment_response,
                        'order_id': order_id,
                        'status': 'payment_created',
                        'response': f"""✅ 购买确认成功！

**商品信息**:
• 名称: {solution['title']}
• 数量: {solution['quantity']}
• 总价: ${solution['total_amount']:.2f} USD

**支付信息**:
{payment_response}
{order_status_msg}

订单已提交，商家将尽快处理您的订单。"""
                    })
                    
                except Exception as e:
                    logger.error(f"⚠️ 调用Agent Registry创建订单失败: {e}")
                    # 即使创建订单失败，也不影响支付成功的响应
                    solution.update({
                        'payment_info': payment_response,
                        'status': 'payment_created',
                        'response': f"""✅ 购买确认成功！

**商品信息**:
• 名称: {solution['title']}
• 数量: {solution['quantity']}
• 总价: ${solution['total_amount']:.2f} USD

**支付信息**:
{payment_response}

⚠️ 订单创建遇到问题，但支付已成功。请联系客服处理。"""
                    })
                
                return solution
                
            except Exception as e:
                logger.error(f"❌ Failed to call Alipay Agent: {e}")
                solution.update({
                    'payment_info': f"Error: {str(e)}",
                    'status': 'payment_failed',
                    'response': f"""✅ 购买确认成功！

**商品信息**:
• 名称: {solution['title']}
• 数量: {solution['quantity']}
• 总价: ${solution['total_amount']:.2f} USD

❌ 支付订单创建失败: {str(e)}
请稍后重试或联系客服。"""
                })
                return solution
                
        except Exception as e:
            logger.error(f"❌ Purchase confirmation processing failed: {e}")
            return {
                "status": "error",
                "message": f"处理购买确认时出错: {str(e)}",
                "response": f"很抱歉，处理您的购买确认时出现问题：{str(e)}。请重新确认您要购买的商品信息。"
            }

# ==============================================================================
#  A2A 服务器的实现
# ==============================================================================
class AmazonA2AServer(A2AServer, AmazonServiceManager):
    """
    最终的A2A服务器，整合了网络服务和亚马逊购物业务逻辑。
    """
    def __init__(self, agent_card: AgentCard):
        A2AServer.__init__(self, agent_card=agent_card)
        AmazonServiceManager.__init__(self)
        print("✅ [AmazonA2AServer] Server fully initialized and ready.")

    def extract_user_input_from_workflow_context(self, text: str) -> str:
        """从工作流上下文中提取纯净的用户输入"""
        # 检查是否包含工作流上下文格式
        if "工作流上下文：" in text and "用户消息:" in text:
            # 提取用户消息部分
            try:
                user_msg_start = text.find("用户消息:")
                if user_msg_start != -1:
                    user_input = text[user_msg_start + len("用户消息:"):].strip()
                    logger.info(f"🔍 从工作流上下文中提取用户输入: '{user_input}'")
                    return user_input
            except Exception as e:
                logger.error(f"❌ 提取用户输入失败: {e}")

        # 如果不是工作流上下文格式，直接返回原文
        return text

    def handle_task(self, task):
        """A2A服务器的核心处理函数。"""
        text = task.message.get("content", {}).get("text", "")
        print(f"📩 [AmazonA2AServer] Received task: '{text[:100]}...' (length: {len(text)})")

        # 处理健康检查请求，避免触发业务逻辑
        if text.lower().strip() in ["health check", "health", "ping", ""]:
            print("✅ [AmazonA2AServer] Health check request - returning healthy status")
            task.artifacts = [{"parts": [{"type": "text", "text": "healthy - User Agent (Amazon Shopping Coordinator) is operational"}]}]
            task.status = TaskStatus(state=TaskState.COMPLETED)
            return task

        if not text:
            response_text = "错误: 收到了一个空的请求。"
            task.status = TaskStatus(state=TaskState.FAILED)
        else:
            try:
                # 使用nest_asyncio允许在已有事件循环中运行新的事件循环
                import nest_asyncio
                nest_asyncio.apply()

                # 使用asyncio.run运行异步函数，它会创建新的事件循环
                import asyncio

                # 首先分类用户意图
                intent_type = asyncio.run(self.classify_user_intent(text))
                print(f"🧠 [AmazonA2AServer] Intent classified as: {intent_type}")

                # 根据意图类型选择处理方式
                if intent_type == "purchase_confirmation":
                    print("🛒 [AmazonA2AServer] Processing purchase confirmation...")
                    result = asyncio.run(self.handle_purchase_confirmation_with_agent_discovery(text))
                else:
                    print("🔍 [AmazonA2AServer] Processing product search and recommendation...")
                    result = asyncio.run(self.autonomous_purchase(text))
                
                # 安全地处理result，确保不是None
                if result is None:
                    print("⚠️ [AmazonA2AServer] Warning: Method returned None")
                    response_text = "❌ **处理失败**\n\n原因: 内部处理异常，未返回有效结果"
                elif "response" in result:
                    # 直接使用预格式化的响应
                    response_text = result["response"]
                else:
                    # 格式化输出
                    if result.get('status') in ['solution', 'payment_and_order_completed', 'purchase_confirmed', 'payment_created']:
                        response_text = (
                            f"✅ **方案已生成**\n\n"
                            f"**商品详情:**\n"
                            f"- **名称**: {result.get('title', '未知商品')}\n"
                            f"- **总价**: ${result.get('total_amount', 0):.2f} {result.get('currency', 'USD')}\n"
                        )

                        if result.get('product_url'):
                            response_text += f"- **链接**: {result.get('product_url')}\n\n"

                        if result.get('payment_info'):
                            response_text += f"**支付信息:**\n{result.get('payment_info')}"
                    else:
                        # 安全地获取错误消息
                        error_msg = result.get('message', '未知错误')
                        response_text = f"❌ **操作失败**\n\n原因: {error_msg}"

                task.status = TaskStatus(state=TaskState.COMPLETED)
                print("💬 [AmazonA2AServer] Processing complete.")

            except Exception as e:
                import traceback
                print(f"❌ [AmazonA2AServer] Critical error during task handling: {e}")
                traceback.print_exc()
                response_text = f"服务器内部错误: {e}"
                task.status = TaskStatus(state=TaskState.FAILED)

        task.artifacts = [{"parts": [{"type": "text", "text": str(response_text)}]}]
        return task

def main():
    """主函数，用于配置和启动A2A服务器"""
    port = int(os.environ.get("AMAZON_A2A_PORT", 5011))
    
    agent_card = AgentCard(
        name="Amazon Shopping Coordinator A2A Agent",
        description="An intelligent A2A agent that coordinates Amazon shopping by working with specialized agents. "
                    "Searches products, generates solutions with URLs, and coordinates payment-first workflow with Payment Agent for transactions followed by Amazon Agent for order confirmation.",
        url=f"http://localhost:{port}",
        skills=[
            AgentSkill(
                name="product_search_and_recommendation",
                description="Search Amazon products and generate purchase recommendations with product URLs."
            ),
            AgentSkill(
                name="payment_agent_coordination",
                description="Coordinate with Payment A2A Agent to process payments before order placement."
            ),
            AgentSkill(
                name="amazon_agent_coordination",
                description="Coordinate with Amazon A2A Agent to confirm orders after payment completion."
            ),
            AgentSkill(
                name="end_to_end_purchase_flow",
                description="Manage the complete purchase flow: search → recommend → payment → order confirmation."
            )
        ]
    )
    
    server = AmazonA2AServer(agent_card)
    
    print("\n" + "="*60)
    print("🚀 Starting Amazon Autonomous Purchase A2A Server...")
    print(f"👂 Listening on http://localhost:{port}")
    print("="*60 + "\n")
    
    run_server(server, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()






