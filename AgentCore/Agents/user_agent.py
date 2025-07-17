# import asyncio
import logging
import json
import time
from typing import Dict, List
from enum import Enum
from dataclasses import dataclass
import aiohttp
import asyncio
import nest_asyncio
nest_asyncio.apply()

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AmazonSmartAgent")

@dataclass
class AmazonProduct:
    asin: str
    title: str
    price: float
    currency: str
    merchant_id: str
    delivery_speed: int
    rating: float
    prime_eligible: bool
    url: str

class PurchaseStrategy(Enum):
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    BEST_RATED = "best_rated"
    PRIME = "prime"

class AmazonSmartAgent:
    def __init__(self, user_id: str, use_mock_pay: bool = False):
        self.user_id = user_id
        self.strategy = PurchaseStrategy.BEST_RATED
        self.session = aiohttp.ClientSession()
        self.cart = []
        self.use_mock_pay = use_mock_pay
        self.deepseek_config = {
            "api_key": " ",
            "api_url": "https://api.deepseek.com/v1"
        }
        self.amazon_search_api = "https://amazon-backend.replit.app/api/v1/search"
        self.recommended_urls = []  # 用于记录已推荐商品的 URL
        if not self.deepseek_config["api_key"]:
            raise ValueError("DeepSeek API key is required")

    async def close(self):
        await self.session.close()

    async def understand_intent(self, user_input: str) -> Dict:
        prompt = f"""
        请将以下购物请求解析为JSON格式，包含以下字段：
        - product_description
        - quantity（默认1）
        - max_price
        - min_rating（默认4.0）
        - delivery_urgency（low/medium/high）

        用户输入：{user_input}
        """
        try:
            async with self.session.post(
                f"{self.deepseek_config['api_url']}/chat/completions",
                headers={"Authorization": f"Bearer {self.deepseek_config['api_key']}"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300
                },
                timeout=10
            ) as resp:
                content = (await resp.json())["choices"][0]["message"]["content"]
                start = content.find('{')
                end = content.rfind('}') + 1
                return json.loads(content[start:end])
        except Exception as e:
            logger.error(f"意图理解失败: {str(e)}")
            return {
                "product_description": user_input,
                "quantity": 1,
                "max_price": None,
                "min_rating": 4.0,
                "delivery_urgency": "low"
            }

    async def set_strategy_from_intent(self, intent: Dict):
        urgency = intent.get("delivery_urgency", "low")
        if urgency == "high":
            self.strategy = PurchaseStrategy.FASTEST
        elif intent.get("min_rating", 4.0) >= 4.5:
            self.strategy = PurchaseStrategy.BEST_RATED
        elif intent.get("max_price") and float(intent["max_price"]) < 100:
            self.strategy = PurchaseStrategy.CHEAPEST
        else:
            self.strategy = PurchaseStrategy.PRIME
        logger.info(f"设置策略: {self.strategy.value}")

    def _calculate_delivery_speed(self, product_data: Dict) -> int:
        if product_data.get("brand", "").lower() in ["apple", "sony"]:
            return 5
        elif product_data.get("prime_eligible"):
            return 4
        else:
            return 2

    async def search_amazon_products(self, intent: Dict) -> List[AmazonProduct]:
        logger.info(f"通过 Amazon 搜索商品: {intent['product_description']}")
        try:
            async with self.session.get(
                self.amazon_search_api,
                params={
                    "q": intent["product_description"],
                    "domain": "amazon.com"
                },
                timeout=10
            ) as resp:
                data = await resp.json()
                products = []
                for item in data[:10]:
                    item_url = f"https://www.amazon.com/dp/{item.get('asin', '')}"
                    if item_url in self.recommended_urls:
                        continue  # 跳过已推荐商品的链接
                    try:
                        price = float(str(item["price"]).replace("$", "").replace(",", "").strip())
                        rating = float(item.get("rating", 4.0))
                    except Exception:
                        continue
                    if intent.get("max_price") and price > intent["max_price"]:
                        continue
                    if rating < intent.get("min_rating", 4.0):
                        continue
                    products.append(AmazonProduct(
                        asin=item.get("asin", "UNKNOWN"),
                        title=item["title"],
                        price=price,
                        currency="USD",
                        merchant_id="Amazon",
                        delivery_speed=self._calculate_delivery_speed(item),
                        rating=rating,
                        prime_eligible=item.get("is_prime", True),
                        url=item_url
                    ))
                if self.strategy == PurchaseStrategy.CHEAPEST:
                    products.sort(key=lambda x: x.price)
                elif self.strategy == PurchaseStrategy.FASTEST:
                    products.sort(key=lambda x: -x.delivery_speed)
                elif self.strategy == PurchaseStrategy.BEST_RATED:
                    products.sort(key=lambda x: -x.rating)
                else:
                    products.sort(key=lambda x: (not x.prime_eligible, -x.rating))
                return products
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    async def call_agent_pay(self, amount: float, merchant_id: str) -> Dict:
        logger.info(f"调用 Agent Pay 支付 ${amount} 给商户 {merchant_id}")
        if self.use_mock_pay:
            await asyncio.sleep(1)
            return {"status": "success", "transaction_id": "mock-tx-123456"}
        try:
            async with self.session.post(
                "https://agentpay.local/api/pay",
                json={
                    "payer_id": self.user_id,
                    "merchant_id": merchant_id,
                    "amount": amount,
                    "currency": "USD"
                },
                timeout=10
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception as e:
            logger.error(f"Agent Pay 支付失败: {e}")
            return {"status": "error", "message": str(e)}

    async def add_to_cart(self, product: AmazonProduct, quantity: int = 1):
        self.cart.append({
            "product": product,
            "quantity": quantity,
            "added_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        })
        logger.info(f"添加到购物车: {quantity}x {product.title}")

    async def checkout(self, shipping_address: Dict) -> Dict:
        if not self.cart:
            return {"status": "error", "message": "购物车为空"}
        total = sum(item["product"].price * item["quantity"] for item in self.cart)
        merchant_id = self.cart[0]["product"].merchant_id
        pay_result = await self.call_agent_pay(amount=total, merchant_id=merchant_id)
        if pay_result.get("status") != "success":
            return {"status": "error", "message": f"Agent Pay failed: {pay_result.get('message')}"}
        summary = {
            "status": "success",
            "order_id": "SIMULATED123456",
            "items": [{"title": item["product"].title, "url": item["product"].url} for item in self.cart],
            "total_amount": total,
            "currency": "USD"
        }
        self.cart = []
        return summary

    async def auto_purchase(self, user_input: str, shipping_address: Dict) -> Dict:
        logger.info(f"开始处理用户请求: {user_input}")
        intent = await self.understand_intent(user_input)
        logger.info(f"解析意图: {intent}")

        await self.set_strategy_from_intent(intent)

        while True:
            products = await self.search_amazon_products(intent)
            if not products:
                return {"status": "error", "message": "未找到符合要求的商品"}

            top3 = products[:3]
            print("\n为您找到以下商品，请选择您想购买的序号：")
            for idx, p in enumerate(top3):
                print(f"{idx + 1}. {p.title} - ${p.price} ({p.rating}⭐)\n   链接: {p.url}")
            print("0. 我不想要这三个，重新推荐")
            print("k. 更换搜索关键词")
            print("q. 退出购买")

            choice = input("请输入序号 (1-3)，或输入 0 重新搜索, k 更换关键词, q 退出: ").strip()
            if choice.lower() == 'q':
                return {"status": "cancelled", "message": "用户退出了购买流程"}
            if choice == '0':
                continue
            if choice.lower() == 'k':
                new_keyword = input("请输入新的搜索关键词: ").strip()
                if new_keyword:
                    intent["product_description"] = new_keyword
                continue
            if choice.isdigit() and 1 <= int(choice) <= len(top3):
                best_product = top3[int(choice) - 1]
                break
            print("输入无效，请重试。")

        logger.info(f"选择商品: {best_product.title} (价格: {best_product.price})")
        self.recommended_urls.append(best_product.url)  # 记录已选商品的 URL
        await self.add_to_cart(best_product, intent.get("quantity", 1))
        return await self.checkout(shipping_address)

# 示例调用
async def demo_amazon_purchase():
    agent = AmazonSmartAgent(user_id="user001", use_mock_pay=True)
    try:
        user_input = "我要黑颜色的中性笔"
        shipping_info = {
            "name": "张三",
            "street": "测试路99号",
            "city": "上海",
            "state": "上海",
            "zip": "200000",
            "country": "CN",
            "phone": "13800000000"
        }
        result = await agent.auto_purchase(user_input, shipping_info)
        if result["status"] == "success":
            print(f"\n✅ 购买成功！订单号: {result['order_id']}")
            print(f"商品: {result['items'][0]['title']}")
            print(f"链接: {result['items'][0]['url']}")
            print(f"总价: {result['total_amount']} {result['currency']}")
        else:
            print(f"\n❌ 购买失败: {result['message']}")
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(demo_amazon_purchase())
