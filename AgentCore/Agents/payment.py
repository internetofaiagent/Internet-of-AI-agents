import os
import asyncio
from datetime import datetime
import random
from camel.toolkits import MCPToolkit, HumanToolkit
from camel.agents import ChatAgent
from camel.models import ModelFactory
from openai import OpenAI
from camel.types import (
    ModelPlatformType,
    ModelType,
    OpenAIBackendRole,
    RoleType,
    TaskType,
)
# 添加 A2A 相关导入
from python_a2a import A2AServer, run_server, AgentCard, AgentSkill, TaskStatus, TaskState, A2AClient


class AlipayOrderService:
    def __init__(self, model=None):
        """初始化支付宝订单服务"""
        self.model = model or ModelFactory.create(
            model_platform=ModelPlatformType.MODELSCOPE,
            model_type='Qwen/Qwen2.5-72B-Instruct',
            model_config_dict={'temperature': 0.2},
            api_key='877a7051-f22f-4230-87e8-e0effb36a399',
        )

    def generate_order_number(self):
        """生成唯一的订单号"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = str(random.randint(1000, 9999))
        return f"ORDER{timestamp}{random_suffix}"

    def calculate_rmb_amount(self, usd_amount: float, exchange_rate: float = 7.26):
        """计算美元转人民币金额"""
        return round(usd_amount * exchange_rate, 2)

    async def call_amazon_agent_after_payment(self, payment_result: dict, product_info: dict = None):
        """支付完成后调用Amazon Agent确认订单"""
        if not payment_result.get("success"):
            return {"success": False, "error": "Payment failed, cannot proceed to Amazon Agent"}

        try:
            # Amazon Agent的URL
            amazon_agent_url = "http://localhost:5012"

            # 构造Amazon订单确认请求
            order_number = payment_result.get('order_number', 'UNKNOWN')
            rmb_amount = payment_result.get('rmb_amount', 0)

            # 从product_info或payment_result中获取商品信息
            product_name = "未知商品"
            usd_price = 0

            if product_info:
                product_name = product_info.get('name', '未知商品')
                usd_price = product_info.get('usd_price', 0)

            amazon_request = f"""支付已完成，请确认Amazon订单：

订单信息：
- 订单号: {order_number}
- 商品名称: {product_name}
- 商品价格: ${usd_price} USD
- 支付金额: ¥{rmb_amount} RMB
- 支付状态: 已完成

请处理此Amazon订单确认并返回订单详情。"""

            print(f"📞 [PaymentAgent] 调用Amazon Agent确认订单: {amazon_agent_url}")

            # 调用Amazon Agent
            amazon_client = A2AClient(amazon_agent_url)
            amazon_response = amazon_client.ask(amazon_request)

            print(f"📥 [PaymentAgent] 收到Amazon Agent响应: {amazon_response[:200] if amazon_response else 'None'}...")

            return {
                "success": True,
                "amazon_response": amazon_response,
                "order_number": order_number
            }

        except Exception as e:
            print(f"❌ [PaymentAgent] 调用Amazon Agent失败: {e}")
            return {
                "success": False,
                "error": f"Failed to call Amazon Agent: {str(e)}",
                "order_number": payment_result.get('order_number', 'UNKNOWN')
            }

    async def run_alipay_query(self, query: str, product_info: dict = None):
        """
        执行支付宝查询和订单创建

        Args:
            query: 用户查询
            product_info: 产品信息字典，包含：
                - name: 产品名称
                - usd_price: 美元价格
                - exchange_rate: 汇率（可选，默认7.26）
        """
        # 使用绝对路径来定位 MCP 配置文件
        config_path = os.path.join(os.path.dirname(__file__), "..", "Mcp", "alipay_server.json")
        config_path = os.path.abspath(config_path)

        # 如果没有提供产品信息，使用默认值
        if product_info is None:
            product_info = {
                "name": "PolyAgent edX Course - Primary Python",
                "usd_price": 49.99,
                "exchange_rate": 7.26
            }

        # 生成订单信息
        order_number = self.generate_order_number()
        rmb_amount = self.calculate_rmb_amount(
            product_info["usd_price"],
            product_info.get("exchange_rate", 7.26)
        )

        try:
            async with MCPToolkit(config_path=config_path) as mcp_toolkit:
                alipay_agent = ChatAgent(
                    system_message=f"""
                    You are an Alipay Agent for a cross-border payment service. Your task is to create a payment order in Chinese Yuan (RMB) for a product priced in US Dollars.

                    **Current Order Information:**
                    - Order Number: {order_number}
                    - Product: {product_info["name"]}
                    - USD Price: ${product_info["usd_price"]}
                    - RMB Amount: ¥{rmb_amount}
                    - Exchange Rate: {product_info.get("exchange_rate", 7.26)}

                    **Action: Create Payment Order (`create_payment`)**
                    - When a user wants to pay, call the `create_payment` function.
                    - Use these parameters:
                        - `outTradeNo`: '{order_number}'
                        - `totalAmount`: '{rmb_amount}'
                        - `orderTitle`: '{product_info["name"]}'

                    **Response Format:**
                    You MUST return an HTML block with a payment link. Use this exact format:

                    <div style="background: linear-gradient(135deg, #1677ff, #69c0ff); padding: 20px; border-radius: 12px; text-align: center; margin: 20px 0; box-shadow: 0 4px 12px rgba(22, 119, 255, 0.3);">
                        <h3 style="color: white; margin: 0 0 15px 0; font-size: 18px;">支付宝支付</h3>
                        <div style="background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px;">
                            <p style="margin: 5px 0; color: #333;"><strong>订单号:</strong> {order_number}</p>
                            <p style="margin: 5px 0; color: #333;"><strong>商品:</strong> {product_info["name"]}</p>
                            <p style="margin: 5px 0; color: #333;"><strong>金额:</strong> ¥{rmb_amount} (${product_info["usd_price"]} USD)</p>
                        </div>
                        <a href="[支付链接]" 
                           style="display: inline-block; background: #ff6900; color: white; padding: 12px 30px; 
                                  text-decoration: none; border-radius: 6px; font-weight: bold; 
                                  transition: all 0.3s ease; box-shadow: 0 2px 8px rgba(255, 105, 0, 0.3);"
                           onmouseover="this.style.background='#e55a00'; this.style.transform='translateY(-2px)'"
                           onmouseout="this.style.background='#ff6900'; this.style.transform='translateY(0)'"
                           target="_blank">
                            立即支付 - Pay Now
                        </a>
                    </div>

                    <div style="background: rgba(74, 144, 226, 0.1); border: 1px solid rgba(74, 144, 226, 0.3); 
                                border-radius: 6px; padding: 12px; margin: 1rem 0; font-size: 0.9em; color: #4a90e2;">
                        <strong>💡 支付说明 / Payment Instructions:</strong><br>
                        1. 点击支付按钮打开支付宝支付页面 / Click the button to open Alipay payment page<br>
                        2. 使用支付宝App扫码或登录网页版完成支付 / Use Alipay App to scan QR code or login to web version<br>
                        3. 支付完成后页面会自动跳转 / Page will redirect automatically after payment completion
                    </div>
                    """,
                    model=self.model,
                    token_limit=32768,
                    tools=[*mcp_toolkit.get_tools()],
                    output_language="zh"
                )

                response = await alipay_agent.astep(query)

                if response and response.msgs:
                    return {
                        "success": True,
                        "order_number": order_number,
                        "rmb_amount": rmb_amount,
                        "response_content": response.msgs[0].content,
                        "tool_calls": response.info.get('tool_calls', [])
                    }
                else:
                    return {
                        "success": False,
                        "error": "Unable to get Alipay response",
                        "order_number": order_number
                    }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "order_number": order_number
            }

    async def query_payment_status(self, order_number: str):
        """查询支付状态"""
        config_path = os.path.join(os.path.dirname(__file__), "..", "Mcp", "alipay_server.json")
        config_path = os.path.abspath(config_path)

        try:
            async with MCPToolkit(config_path=config_path) as mcp_toolkit:
                alipay_agent = ChatAgent(
                    system_message=f"""
                    You are an Alipay Agent for querying payment status.

                    **Action: Query Payment Status (`query_payment`)**
                    - Call the `query_payment` function with:
                        - `outTradeNo`: '{order_number}'

                    **Response Format:**
                    Return the payment status information in a clear format including:
                    - Transaction ID
                    - Payment Status
                    - Amount
                    - Transaction Time (if available)
                    """,
                    model=self.model,
                    token_limit=32768,
                    tools=[*mcp_toolkit.get_tools()],
                    output_language="zh"
                )

                response = await alipay_agent.astep(f"查询订单 {order_number} 的支付状态")

                if response and response.msgs:
                    return {
                        "success": True,
                        "order_number": order_number,
                        "status_info": response.msgs[0].content,
                        "tool_calls": response.info.get('tool_calls', [])
                    }
                else:
                    return {
                        "success": False,
                        "error": "Unable to query payment status"
                    }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# 使用示例
async def main():
    """主函数示例"""
    alipay_service = AlipayOrderService()

    # 示例1: 创建默认订单
    print("=== 创建默认订单 ===")
    result1 = await alipay_service.run_alipay_query("我要支付课程费用")
    print(f"订单号: {result1.get('order_number')}")
    print(f"状态: {'成功' if result1.get('success') else '失败'}")
    if result1.get('success'):
        print(f"金额: ¥{result1.get('rmb_amount')}")
    print()

    # 示例2: 创建自定义产品订单
    print("=== 创建自定义订单 ===")
    custom_product = {
        "name": "Advanced AI Course - Machine Learning",
        "usd_price": 99.99,
        "exchange_rate": 7.20
    }
    result2 = await alipay_service.run_alipay_query(
        "创建新的课程订单",
        product_info=custom_product
    )
    print(f"订单号: {result2.get('order_number')}")
    print(f"状态: {'成功' if result2.get('success') else '失败'}")
    if result2.get('success'):
        print(f"金额: ¥{result2.get('rmb_amount')}")
    print()

    # 示例3: 查询支付状态
    if result1.get('success'):
        print("=== 查询支付状态 ===")
        status_result = await alipay_service.query_payment_status(result1.get('order_number'))
        print(f"查询状态: {'成功' if status_result.get('success') else '失败'}")
        if status_result.get('success'):
            print("状态信息:")
            print(status_result.get('status_info'))


# 添加 A2A 服务器实现
class AlipayA2AServer(A2AServer):
    """
    支付宝 A2A 服务器，提供支付宝支付功能的 A2A 接口
    """
    def __init__(self, agent_card: AgentCard):
        super().__init__(agent_card=agent_card)
        self.alipay_service = AlipayOrderService()
        print("✅ [AlipayA2AServer] Server initialized and ready.")

    def handle_task(self, task):
        """A2A 服务器的核心处理函数"""
        text = task.message.get("content", {}).get("text", "")
        print(f"📩 [AlipayA2AServer] Received task: '{text}'")

        # 处理健康检查请求，避免触发业务逻辑
        if text.lower().strip() in ["health check", "health", "ping", ""]:
            print("✅ [AlipayA2AServer] Health check request - returning healthy status")
            task.artifacts = [{"parts": [{"type": "text", "text": "healthy - Payment Agent (Alipay) is operational"}]}]
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
                
                # 使用asyncio.run运行异步函数
                result = asyncio.run(self.process_payment_request(text))
                
                # 使用结果构建响应
                if result.get('success'):
                    response_text = result.get('response_content', '支付订单已创建')
                else:
                    error_msg = result.get('error', '未知错误')
                    response_text = f"❌ 支付处理错误: {error_msg}"
                
                task.status = TaskStatus(state=TaskState.COMPLETED)
                print("💬 [AlipayA2AServer] Processing complete.")

            except Exception as e:
                import traceback
                print(f"❌ [AlipayA2AServer] Critical error during task handling: {e}")
                traceback.print_exc()
                response_text = f"服务器内部错误: {e}"
                task.status = TaskStatus(state=TaskState.FAILED)

        task.artifacts = [{"parts": [{"type": "text", "text": str(response_text)}]}]
        return task
    
    async def process_payment_request(self, text: str):
        """处理支付请求 - 模拟支付成功流程"""
        print("💳 开始处理支付请求（模拟模式）...")

        # 提取产品信息
        product_info = self.extract_product_info(text)

        # 生成模拟支付订单号 - 使用标准格式
        import datetime
        import random
        import string

        # 生成13位标准订单号 (Amazon标准格式)
        order_number = ''.join(random.choices(string.digits, k=13))

        # 计算价格
        usd_price = product_info.get("usd_price", 999.00)
        rmb_price = usd_price * 7.26  # 汇率

        print(f"💰 商品价格: ${usd_price:.2f} USD = ¥{rmb_price:.2f} RMB")
        print(f"📋 生成订单号: {order_number}")

        # 模拟支付成功
        mock_payment_response = f"""✅ 支付宝支付成功！

**订单信息:**
- 订单号: {order_number}
- 商品: {product_info.get('name', 'iPhone 15 Pro')}
- 金额: ${usd_price:.2f} USD (¥{rmb_price:.2f} RMB)
- 支付时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 支付状态: 已完成

**支付方式:** 支付宝余额支付
**交易流水号:** {order_number}_TXN"""

        print("✅ 模拟支付成功，正在调用Amazon Agent确认订单...")

        # 调用Amazon Agent进行订单确认
        amazon_result = await self.call_amazon_agent_mock(product_info, order_number)

        if amazon_result.get("success"):
            # 合并支付和Amazon响应
            combined_response = f"""{mock_payment_response}

**Amazon订单确认:**
{amazon_result.get("amazon_response", "Amazon订单确认成功")}"""

            return {
                "success": True,
                "response_content": combined_response,
                "order_number": order_number,
                "payment_amount_usd": usd_price,
                "payment_amount_rmb": rmb_price
            }
        else:
            return {
                "success": False,
                "error": f"支付成功但Amazon订单确认失败: {amazon_result.get('error', '未知错误')}",
                "response_content": mock_payment_response
            }

    def extract_product_info(self, text: str):
        """提取产品信息"""
        product_info = {
            "name": "iPhone 15 Pro",  # 默认商品
            "usd_price": 999.00,      # 默认价格
            "quantity": 1
        }

        try:
            lines = text.split('\n')
            for line in lines:
                line_lower = line.lower()
                if "名称:" in line or "商品:" in line:
                    product_info["name"] = line.split(":", 1)[1].strip()
                elif "单价:" in line or "总价:" in line or "price:" in line_lower:
                    price_str = line.split(":", 1)[1].strip()
                    # 提取价格数字
                    import re
                    price_match = re.search(r'(\d+\.?\d*)', price_str.replace("$", "").replace("USD", ""))
                    if price_match:
                        product_info["usd_price"] = float(price_match.group(1))
                elif "数量:" in line or "quantity:" in line_lower:
                    quantity_str = line.split(":", 1)[1].strip()
                    import re
                    quantity_match = re.search(r'(\d+)', quantity_str)
                    if quantity_match:
                        product_info["quantity"] = int(quantity_match.group(1))
        except Exception as e:
            print(f"⚠️ 解析产品信息时出错: {e}，使用默认值")

        return product_info

    async def call_amazon_agent_mock(self, product_info: dict, payment_order_number: str):
        """调用Amazon Agent进行模拟订单确认"""
        try:
            from python_a2a import A2AClient

            amazon_agent_url = "http://localhost:5012"
            print(f"📞 [PaymentAgent] 调用Amazon Agent确认订单: {amazon_agent_url}")

            # 构造Amazon订单确认请求
            amazon_request = f"""支付已完成，请确认Amazon订单（模拟模式）：

**商品信息:**
- 名称: {product_info.get('name', 'iPhone 15 Pro')}
- 价格: ${product_info.get('usd_price', 999.00):.2f} USD
- 数量: {product_info.get('quantity', 1)}

**支付信息:**
- 支付订单号: {payment_order_number}
- 支付状态: 已完成
- 支付时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

请处理此订单确认并返回模拟的下单成功信息。"""

            # 调用Amazon Agent
            amazon_client = A2AClient(amazon_agent_url)
            amazon_response = amazon_client.ask(amazon_request)

            print(f"📥 [PaymentAgent] 收到Amazon Agent响应: {amazon_response[:100] if amazon_response else 'None'}...")

            return {
                "success": True,
                "amazon_response": amazon_response or "Amazon订单确认成功"
            }

        except Exception as e:
            print(f"❌ [PaymentAgent] 调用Amazon Agent失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }


def main():
    """主函数，用于配置和启动A2A服务器"""
    port = int(os.environ.get("ALIPAY_A2A_PORT", 5005))
    
    agent_card = AgentCard(
        name="Alipay Payment A2A Agent",
        description="An A2A agent that creates Alipay payment orders for cross-border transactions.",
        url=f"http://localhost:{port}",
        skills=[
            AgentSkill(name="create_payment", description="Create an Alipay payment order for a product.")
        ]
    )
    
    server = AlipayA2AServer(agent_card)
    
    print("\n" + "="*60)
    print("🚀 Starting Alipay Payment A2A Server...")
    print(f"👂 Listening on http://localhost:{port}")
    print("="*60 + "\n")
    
    run_server(server, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
