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
        # 使用Qwen2.5模型替代GPT
        self.model = ModelFactory.create(
            model_platform=ModelPlatformType.MODELSCOPE,
            model_type='Qwen/Qwen2.5-72B-Instruct',
            model_config_dict={'temperature': 0.2},
            api_key='9d3aed4d-eca1-4e0c-9805-cb923ccbbf21',
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

    async def _get_session(self):
        """获取或创建aiohttp会话，确保在当前事件循环中创建"""
        # 每次都创建新的会话，避免跨事件循环问题
        return aiohttp.ClientSession()

    async def close(self):
        """关闭 aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

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
            logger.error(f"❌ Intent understanding failed: {str(e)}. Falling back to default.")
            return {
                "product_description": user_input,
                "quantity": 1,
                "max_price": None,
                "min_rating": 4.0,
                "delivery_urgency": "low",
                "preferred_payment_methods": []
            }

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

    async def search_amazon_products(self, intent: Dict, strategy: PurchaseStrategy) -> List[AmazonProduct]:
        """调用亚马逊API搜索商品，并根据策略排序"""
        logger.info(f"🔍 Searching Amazon for: {intent['product_description']}")
        try:
            # 为每次搜索创建新的会话
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.amazon_search_api,
                    params={"query": intent["product_description"], "country": "US"},
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
                                       "0")

                            price_str = str(price_raw).replace("$", "").replace(",", "").strip()
                            price = float(price_str) if price_str and price_str != "None" else 0.0

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
            # 1. 理解意图
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

            # 4. 选出最优商品
            best_product = products[0]
            solution = {
                "status": "solution",
                "asin": best_product.asin,
                "title": best_product.title,
                "unit_price": best_product.price,
                "quantity": intent.get("quantity", 1),
                "total_amount": best_product.price * intent.get("quantity", 1),
                "currency": "USD",
                "product_url": best_product.url,
                "strategy": strategy.value,
            }
            
            # 5. 先调用支付宝Agent支付，然后调用Amazon A2A Agent确认订单
            logger.info("📞 Step 1: Calling Alipay A2A Agent for payment...")
            try:
                # 第一步：调用支付宝Agent创建支付
                ALIPAY_AGENT_URL = "http://0.0.0.0:5005"
                logger.info(f"🔗 Connecting to Alipay A2A Agent at {ALIPAY_AGENT_URL}")
                print(f"🔗 正在连接支付宝 A2A Agent: {ALIPAY_AGENT_URL}")

                # 构造支付请求
                payment_request_text = f"""请为以下商品创建支付：
                                    商品: {solution['title']}
                                    ASIN: {solution['asin']}
                                    数量: {solution['quantity']}
                                    单价: ${solution['unit_price']:.2f} USD
                                    总价: ${solution['total_amount']:.2f} USD

                                    请创建支付宝支付订单。"""

                logger.info(f"📤 Sending payment request to Alipay...")
                print(f"📤 发送支付请求到支付宝...")

                # 使用A2AClient发送请求
                alipay_client = A2AClient(ALIPAY_AGENT_URL)
                payment_response = alipay_client.ask(payment_request_text)

                print(f"📥 收到支付宝 Agent 响应: {payment_response[:200]}...")
                logger.info("✅ Successfully received payment info from Alipay Agent.")

                # 第二步：支付成功后调用Amazon Agent确认订单
                logger.info("📞 Step 2: Calling Amazon A2A Agent to confirm order...")
                AMAZON_AGENT_URL = "http://0.0.0.0:5012"  # Amazon Agent端口
                logger.info(f"🔗 Connecting to Amazon A2A Agent at {AMAZON_AGENT_URL}")
                print(f"🔗 正在连接Amazon A2A Agent: {AMAZON_AGENT_URL}")

                # 构造Amazon订单确认请求，包含支付信息
                amazon_request_text = f"""请为以下商品确认订单（支付已完成）：
                                    商品URL: {solution['product_url']}
                                    商品名称: {solution['title']}
                                    ASIN: {solution['asin']}
                                    数量: {solution['quantity']}
                                    单价: ${solution['unit_price']:.2f} USD
                                    总价: ${solution['total_amount']:.2f} USD
                                    支付状态: 支付宝支付已完成

                                    请处理此订单确认并返回订单信息。"""

                logger.info(f"📤 Sending Amazon order confirmation request...")
                print(f"📤 发送Amazon订单确认请求...")

                # 使用A2AClient调用Amazon Agent
                amazon_client = A2AClient(AMAZON_AGENT_URL)
                amazon_response = amazon_client.ask(amazon_request_text)

                print(f"📥 收到Amazon Agent响应: {amazon_response[:200]}...")
                logger.info("✅ Successfully received response from Amazon Agent.")

                # 将支付和Amazon订单信息附加到最终结果中
                solution['payment_info'] = payment_response
                solution['amazon_order_info'] = amazon_response
                solution['status'] = 'payment_and_order_completed'
                solution['response'] = f"""✅ 支付完成并订单已确认！

                                    **商品信息**:
                                    • 名称: {solution['title']}
                                    • ASIN: {solution['asin']}
                                    • 总价: ${solution['total_amount']:.2f} USD
                                    • 商品链接: {solution['product_url']}

                **支付信息**:
                {payment_response[:300]}...

                **Amazon订单确认**:
                {amazon_response[:300]}..."""
                
                # 修复：添加缺失的return语句，确保成功情况下返回结果
                return solution
                
            except Exception as e:
                logger.error(f"❌ Failed to call Alipay or Amazon Agent: {e}")
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"详细错误: {error_details}")
                print(f"❌ 连接支付宝或Amazon Agent 失败: {e}")
                print(f"详细错误: {error_details}")

                solution['payment_info'] = f"Error: Could not complete payment process. {str(e)}"
                solution['amazon_order_info'] = f"Error: Could not connect to Amazon Agent."
                solution['status'] = 'payment_order_failed'
                solution['response'] = f"""❌ 支付和订单确认失败

                                    **商品**: {solution['title']}
                                    **总价**: ${solution['total_amount']:.2f} USD
                                    **商品链接**: {solution['product_url']}

                                    无法完成支付和Amazon订单确认流程，请稍后重试。
                                    错误：{str(e)}"""
            
                return solution
            
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
        You are a user intent classifier for an e-commerce system. Analyze the user's input and determine their intent.

        Intent Types:
        1. "search" - User wants to search for new products (e.g., "I want to buy a black pen", "find me headphones")
        2. "purchase_confirmation" - User wants to confirm purchase of a specific product already shown to them (e.g., "I want to buy the first one", "purchase this item", mentions specific ASIN/price/product name from previous results)

        Key indicators for "purchase_confirmation":
        - References to specific items by number ("第1个", "第一个", "first one", "item 1")
        - Mentions specific product names, ASINs, prices, or URLs from previous results
        - Phrases like "我想买这件商品", "purchase this", "buy this item", "创建订单", "下订单"
        - Contains specific product details like ASIN codes (e.g., "B004QHI43S")

        Key indicators for "search":
        - General product descriptions without specific references
        - No mention of specific items from previous results
        - Requests like "我想买笔", "find me a laptop", "search for phones"

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
            logger.error(f"❌ Intent classification failed: {e}, defaulting to search")
            return "search"

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
            
            # 创建购买解决方案
            solution = {
                "status": "purchase_confirmed",
                "asin": product_info.get("asin", "CONFIRMED_ITEM"),
                "title": product_info.get("title", "用户选择的商品"),
                "unit_price": product_info.get("price", 15.15),  # 默认价格，实际应从之前的搜索结果获取
                "quantity": product_info.get("quantity", 1),
                "total_amount": (product_info.get("price", 15.15) * product_info.get("quantity", 1)),
                "currency": "USD",
                "product_url": product_info.get("url", "https://www.amazon.com/dp/" + product_info.get("asin", "")),
                "confirmation_message": extracted_info.get("confirmation_message", "")
            }
            
            # 调用支付宝Agent创建订单
            logger.info("📞 User confirmed purchase, calling Alipay A2A Agent for payment...")
            try:
                ALIPAY_AGENT_URL = "http://0.0.0.0:5005"
                payment_request_text = f"""用户确认购买商品，请创建支付宝订单：
                
商品信息：
- 名称: {solution['title']}
- ASIN: {solution['asin']}
- 数量: {solution['quantity']}
- 单价: ${solution['unit_price']:.2f} USD
- 总价: ${solution['total_amount']:.2f} USD

请为此商品创建支付宝支付订单。"""

                alipay_client = A2AClient(ALIPAY_AGENT_URL)
                payment_response = alipay_client.ask(payment_request_text)
                
                logger.info("✅ Successfully received payment info from Alipay Agent")
                
                # 构建最终响应
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

请完成支付以继续订单处理。"""
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

    def handle_task(self, task):
        """A2A服务器的核心处理函数。"""
        text = task.message.get("content", {}).get("text", "")
        print(f"📩 [AmazonA2AServer] Received task: '{text}'")

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
                    result = asyncio.run(self.handle_purchase_confirmation(text))
                else:
                    print("🔍 [AmazonA2AServer] Processing product search...")
                    result = asyncio.run(self.autonomous_purchase(text))
                
                # 安全地处理result，确保不是None
                if result is None:
                    print("⚠️ [AmazonA2AServer] Warning: Method returned None")
                    response_text = "❌ **处理失败**\n\n原因: 内部处理异常，未返回有效结果"
                elif "response" in result:
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






