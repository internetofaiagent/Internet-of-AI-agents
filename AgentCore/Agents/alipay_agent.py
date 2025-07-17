import os
import asyncio
from datetime import datetime
import random
from camel.toolkits import MCPToolkit, HumanToolkit
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.types import (
    ModelPlatformType,
    ModelType,
    OpenAIBackendRole,
    RoleType,
    TaskType,
)


class AlipayOrderService:
    def __init__(self, model=None):
        """初始化支付宝订单服务"""
        self.model = model or ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.GPT_4_1,
            url="https://api.openai.com/v1/",
        )

    def generate_order_number(self):
        """生成唯一的订单号"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = str(random.randint(1000, 9999))
        return f"ORDER{timestamp}{random_suffix}"

    def calculate_rmb_amount(self, usd_amount: float, exchange_rate: float = 7.26):
        """计算美元转人民币金额"""
        return round(usd_amount * exchange_rate, 2)

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


if __name__ == "__main__":
    asyncio.run(main())