import os
import re
import sys
import asyncio
from datetime import datetime
import random

# --- A2A 和 CAMEL 库导入 ---
# 假设您已经安装了 python_a2a
# pip install python-a2a
from python_a2a import A2AServer, run_server, AgentCard, AgentSkill, TaskStatus, TaskState
from camel.toolkits import MCPToolkit
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType

# --- 确保项目路径正确 ---
# 如果需要，可以添加路径设置
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


# ==============================================================================
#  业务逻辑层: AlipayServiceManager
#  这个类包含了所有原始的支付宝订单创建和查询逻辑。
# ==============================================================================
class AlipayServiceManager:
    """
    管理所有与支付宝服务相关的业务逻辑，包括模型初始化、Agent创建和核心功能实现。
    """
    def __init__(self):
        """初始化模型和配置"""
        print("🧠 [AlipayServer] Initializing the core AI model...")
        self.model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            # 注意: GPT_4_1 可能是一个自定义类型或拼写错误，标准库中通常是 GPT_4, GPT_4_TURBO等
            # 这里我们保留它，假设您的环境中是有效的。
            model_type=ModelType.GPT_4_1,
            # 建议将API密钥和URL放在环境变量或配置文件中，而不是硬编码
            api_key=os.environ.get("OPENAI_API_KEY"),
            url="https://api.openai.com/v1/",
        )
        print("✅ [AlipayServer] AI model is ready.")

    def generate_order_number(self):
        """生成唯一的订单号"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = str(random.randint(1000, 9999))
        return f"ORDER{timestamp}{random_suffix}"

    def calculate_rmb_amount(self, usd_amount: float, exchange_rate: float = 7.26):
        """计算美元转人民币金额"""
        return round(usd_amount * exchange_rate, 2)

    async def create_alipay_order(self, query: str, product_info: dict = None):
        """
        执行支付宝查询和订单创建。这是原始 run_alipay_query 的核心。

        Args:
            query: 用户查询，用于触发Agent。
            product_info: 产品信息字典。
        """
        # 使用绝对路径来定位 MCP 配置文件
        # 确保路径相对于当前文件位置是正确的
        config_path = os.path.join(os.path.dirname(__file__), "..", "Mcp", "alipay_server.json")
        config_path = os.path.abspath(config_path)

        if not os.path.exists(config_path):
            return {"success": False, "error": f"MCP config file not found at: {config_path}"}

        # 如果没有提供产品信息，使用默认值
        if product_info is None:
            product_info = {
                "name": "PolyAgent edX Course - Primary Python",
                "usd_price": 49.99,
                "exchange_rate": 7.26
            }

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
                           style="display: inline-block; background: #ff6900; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; transition: all 0.3s ease; box-shadow: 0 2px 8px rgba(255, 105, 0, 0.3);"
                           onmouseover="this.style.background='#e55a00'; this.style.transform='translateY(-2px)'"
                           onmouseout="this.style.background='#ff6900'; this.style.transform='translateY(0)'"
                           target="_blank">立即支付 - Pay Now</a>
                    </div>
                    <div style="background: rgba(74, 144, 226, 0.1); border: 1px solid rgba(74, 144, 226, 0.3); border-radius: 6px; padding: 12px; margin: 1rem 0; font-size: 0.9em; color: #4a90e2;">
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
                        "success": True, "order_number": order_number, "rmb_amount": rmb_amount,
                        "response_content": response.msgs[0].content,
                        "tool_calls": response.info.get('tool_calls', [])
                    }
                else:
                    return {"success": False, "error": "Unable to get Alipay response", "order_number": order_number}
        except Exception as e:
            return {"success": False, "error": str(e), "order_number": order_number}

    async def query_alipay_status(self, order_number: str):
        """查询支付状态。这是原始 query_payment_status 的核心。"""
        config_path = os.path.join(os.path.dirname(__file__), "..", "Mcp", "alipay_server.json")
        config_path = os.path.abspath(config_path)

        if not os.path.exists(config_path):
            return {"success": False, "error": f"MCP config file not found at: {config_path}"}

        try:
            async with MCPToolkit(config_path=config_path) as mcp_toolkit:
                alipay_agent = ChatAgent(
                    system_message=f"""
                    You are an Alipay Agent for querying payment status.
                    **Action: Query Payment Status (`query_payment`)**
                    - Call the `query_payment` function with: `outTradeNo`: '{order_number}'
                    **Response Format:**
                    Return the payment status information in a clear Chinese format.
                    """,
                    model=self.model,
                    token_limit=32768,
                    tools=[*mcp_toolkit.get_tools()],
                    output_language="zh"
                )
                response = await alipay_agent.astep(f"查询订单 {order_number} 的支付状态")
                if response and response.msgs:
                    return {
                        "success": True, "order_number": order_number,
                        "status_info": response.msgs[0].content,
                        "tool_calls": response.info.get('tool_calls', [])
                    }
                else:
                    return {"success": False, "error": "Unable to query payment status", "order_number": order_number}
        except Exception as e:
            return {"success": False, "error": str(e), "order_number": order_number}


# ==============================================================================
#  A2A 服务器的实现
#  通过多重继承，同时获得了 A2AServer 的网络服务能力和 AlipayServiceManager 的业务逻辑能力。
# ==============================================================================
class AlipayA2AServer(A2AServer, AlipayServiceManager):
    """
    最终的A2A服务器，整合了网络服务和支付宝业务逻辑。
    """
    def __init__(self, agent_card: AgentCard):
        # 1. 初始化 A2AServer 部分 (网络服务)
        A2AServer.__init__(self, agent_card=agent_card)
        # 2. 初始化 AlipayServiceManager 部分 (业务逻辑)
        AlipayServiceManager.__init__(self)
        print("✅ [AlipayA2AServer] Server fully initialized and ready.")

    def handle_task(self, task):
        """
        A2A服务器的核心处理函数。当收到来自客户端的请求时，此方法被调用。
        """
        text = task.message.get("content", {}).get("text", "")
        print(f"📩 [AlipayA2AServer] Received task: '{text}'")
        
        if not text:
            response_text = "错误: 收到了一个空的请求。"
            task.status = TaskStatus(state=TaskState.FAILED)
        else:
            response_text = ""
            try:
                # --- 智能路由: 根据用户输入决定调用哪个函数 ---
                # 检查是否是查询状态的请求
                query_keywords = ["查询", "状态", "query", "status"]
                # 正则表达式用于从 "查询订单 ORDER..." 这样的文本中提取订单号
                order_match = re.search(r'order\s*([a-z0-9]+)|订单\s*([a-z0-9]+)', text, re.IGNORECASE)

                if any(keyword in text.lower() for keyword in query_keywords) and order_match:
                    order_number = order_match.group(1) or order_match.group(2)
                    print(f"⚙️ Routing to: query_alipay_status for order {order_number}")
                    # 使用 asyncio.run() 安全地运行异步函数
                    result = asyncio.run(self.query_alipay_status(order_number))
                    if result.get("success"):
                        response_text = result.get("status_info", "成功获取状态，但无详细信息。")
                    else:
                        response_text = f"❌ 查询失败: {result.get('error')}"
                else:
                    # 默认创建订单
                    print(f"⚙️ Routing to: create_alipay_order")
                    # 在A2A场景下，product_info可以从更复杂的请求中解析，这里为了简化，使用默认值
                    result = asyncio.run(self.create_alipay_order(query=text))
                    if result.get("success"):
                        response_text = result.get("response_content", "订单创建成功，但无详细响应。")
                    else:
                        response_text = f"❌ 创建订单失败: {result.get('error')}"
                
                print("💬 [AlipayA2AServer] Processing complete.")
                task.status = TaskStatus(state=TaskState.COMPLETED)

            except Exception as e:
                import traceback
                print(f"❌ [AlipayA2AServer] Critical error during task handling: {e}")
                traceback.print_exc()
                response_text = f"服务器内部错误: {e}"
                task.status = TaskStatus(state=TaskState.FAILED)

        # 将最终结果打包成 A2A 响应
        task.artifacts = [{"parts": [{"type": "text", "text": str(response_text)}]}]
        return task


def main():
    """主函数，用于配置和启动A2A服务器"""
    # 定义服务器的端口，可以从环境变量或配置文件读取
    port = int(os.environ.get("ALIPAY_A2A_PORT", 5005))
    
    # 定义服务器的“名片”，用于服务发现和能力声明
    agent_card = AgentCard(
        name="Alipay A2A Service Agent",
        description="An A2A agent that handles Alipay payment order creation and status queries.",
        url=f"http://localhost:{port}",
        skills=[
            AgentSkill(name="create_payment_order", description="Creates an Alipay payment order for a product."),
            AgentSkill(name="query_payment_status", description="Queries the status of an existing Alipay order by its order number.")
        ]
    )
    
    # 创建并准备启动服务器
    server = AlipayA2AServer(agent_card)
    
    print("\n" + "="*60)
    print("🚀 Starting Alipay A2A Server...")
    print(f"👂 Listening on http://localhost:{port}")
    print("   This server provides Alipay payment functionalities via A2A protocol.")
    print("="*60 + "\n")
    
    # 运行服务器，使其开始监听请求
    run_server(server, host="0.0.0.0", port=port)


if __name__ == "__main__":
    # 确保Mcp目录和alipay_server.json文件存在于上一级目录
    # 例如，你的目录结构应该是：
    # project/
    # ├── Mcp/
    # │   └── alipay_server.json
    # └── scripts/
    #     └── alipay_a2a_server.py  (当前文件)
    main()