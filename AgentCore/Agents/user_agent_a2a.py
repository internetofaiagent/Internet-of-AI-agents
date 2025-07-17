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
from python_a2a import A2AServer, run_server, AgentCard, AgentSkill, TaskStatus, TaskState
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
        # 改用与Alipay Agent相同的模型工厂
        self.model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.GPT_4_1,
            # 建议将API密钥放在环境变量或配置文件中
            url="https://api.openai.com/v1/",
        )
        print("✅ [AmazonServer] AI model is ready.")

        # 初始化 aiohttp session
        self.session = aiohttp.ClientSession()
        self.amazon_search_api = "https://amazon-backend.replit.app/api/v1/search"

    async def close(self):
        """关闭 aiohttp session"""
        await self.session.close()

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
                "product_description": user_input, "quantity": 1,
                "max_price": None, "min_rating": 4.0, "delivery_urgency": "low"
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
            async with self.session.get(
                self.amazon_search_api,
                params={"q": intent["product_description"], "domain": "amazon.com"},
                timeout=15
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                products = []
                for item in data[:10]: # 只处理前10个结果
                    try:
                        price = float(str(item.get("price", "0")).replace("$", "").replace(",", "").strip())
                        rating = float(item.get("rating", 4.0))
                    except (ValueError, TypeError):
                        continue # 跳过无法解析价格或评分的商品

                    if intent.get("max_price") and price > intent["max_price"]:
                        continue
                    if rating < intent.get("min_rating", 4.0):
                        continue
                    
                    products.append(AmazonProduct(
                        asin=item.get("asin", "UNKNOWN"), title=item.get("title", "No Title"), price=price,
                        currency="USD", merchant_id="Amazon",
                        delivery_speed=5 if item.get("brand", "").lower() in ["apple", "sony"] else 4 if item.get("is_prime") else 2,
                        rating=rating, prime_eligible=item.get("is_prime", True),
                        url=f"https://www.amazon.com/dp/{item.get('asin', '')}"
                    ))
                
                # 根据策略排序
                if strategy == PurchaseStrategy.CHEAPEST:
                    products.sort(key=lambda x: x.price)
                elif strategy == PurchaseStrategy.FASTEST:
                    products.sort(key=lambda x: -x.delivery_speed)
                elif strategy == PurchaseStrategy.BEST_RATED:
                    products.sort(key=lambda x: -x.rating)
                else: # PRIME
                    products.sort(key=lambda x: (not x.prime_eligible, -x.rating))
                
                logger.info(f"✅ Found {len(products)} suitable products.")
                return products
        except Exception as e:
            logger.error(f"❌ Amazon search failed: {e}")
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
        # 1. 理解意图
        intent = await self.understand_intent(user_input)

        # 2. 设定策略
        strategy = self.set_strategy_from_intent(intent)

        # 3. 搜索商品
        products = await self.search_amazon_products(intent, strategy)
        if not products:
            return {"status": "error", "message": "未能找到任何符合您要求的商品。"}

        # 4. 自主选择最优商品（根据策略排序后的第一个）
        best_product = products[0]
        logger.info(f"🤖 Agent autonomously selected best product: {best_product.title}")

        # 5. 模拟支付
        payment_result = await self._mock_payment(
            amount=best_product.price * intent.get("quantity", 1),
            merchant_id=best_product.merchant_id
        )

        if payment_result.get("status") != "success":
            return {"status": "error", "message": f"支付失败: {payment_result.get('message')}"}

        # 6. 返回成功结果
        return {
            "status": "success",
            "order_id": f"ORDER-{best_product.asin}",
            "product_title": best_product.title,
            "product_url": best_product.url,
            "total_amount": best_product.price * intent.get("quantity", 1),
            "currency": "USD",
            "message": f"已根据'{strategy.value}'策略，为您自动购买了评分最高的商品。"
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

        if not text:
            response_text = "错误: 收到了一个空的请求。"
            task.status = TaskStatus(state=TaskState.FAILED)
        else:
            try:
                # 路由到自主购买流程
                # 在更复杂的场景中，这里可以有更复杂的路由逻辑（如仅搜索）
                result = asyncio.run(self.autonomous_purchase(text))
                
                # 格式化输出
                if result['status'] == 'success':
                    response_text = (
                        f"✅ **购买成功**\n\n"
                        f"🎉 **订单号**: {result['order_id']}\n"
                        f"📦 **商品**: {result['product_title']}\n"
                        f"🔗 **链接**: {result['product_url']}\n"
                        f"💵 **总金额**: ${result['total_amount']:.2f} {result['currency']}\n\n"
                        f"💡 **备注**: {result['message']}"
                    )
                else:
                    response_text = f"❌ **操作失败**\n\n原因: {result['message']}"

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
        name="Amazon Autonomous Purchase A2A Agent",
        description="An A2A agent that autonomously understands shopping requests, "
                    "searches Amazon, and purchases the best product based on a smart strategy.",
        url=f"http://localhost:{port}",
        skills=[
            AgentSkill(name="autonomous_purchase", description="Handle the entire purchase flow from a single user request.")
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