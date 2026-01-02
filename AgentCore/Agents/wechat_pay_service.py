#!/usr/bin/env python3
"""
微信支付服务 - WeChat Pay Order Service

提供微信支付订单创建、查询等功能，支持跨境支付的美元到人民币转换。
使用 MCP (Model Context Protocol) 工具包与微信支付 API 集成。

主要功能：
- 创建微信支付订单
- 查询支付状态
- 美元到人民币汇率转换
- 与 Amazon Agent 集成
"""

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


class WeChatPayOrderService:
    """微信支付订单服务类"""
    
    def __init__(self, model=None):
        """
        初始化微信支付订单服务
        
        Args:
            model: 可选的模型实例，如果为None则使用默认的ModelFactory创建模型
        """
        # 设置环境变量（如果未设置）
        if not os.environ.get('MODELSCOPE_SDK_TOKEN'):
            os.environ['MODELSCOPE_SDK_TOKEN'] = 'ms-8fa443fb-2162-45da-b88d-d7d3582e4ad8'
            print("🔧 设置MODELSCOPE_SDK_TOKEN环境变量")
        
        # 初始化模型
        self.model = model or ModelFactory.create(
            model_platform=ModelPlatformType.MODELSCOPE,
            model_type='Qwen/Qwen2.5-72B-Instruct',
            model_config_dict={'temperature': 0.2},
            api_key=os.environ.get('MODELSCOPE_SDK_TOKEN'),
        )
        
        print("✅ [WeChatPayOrderService] 微信支付服务初始化完成")
    
    def generate_order_number(self):
        """
        生成唯一的订单号
        
        Returns:
            str: 格式为 ORDER{timestamp}{random_suffix} 的订单号
                - timestamp: YYYYMMDDHHMMSS 格式的时间戳
                - random_suffix: 4位随机数（1000-9999）
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = str(random.randint(1000, 9999))
        return f"ORDER{timestamp}{random_suffix}"
    
    def calculate_rmb_amount(self, usd_amount: float, exchange_rate: float = 7.26):
        """
        计算美元转人民币金额
        
        Args:
            usd_amount: 美元金额
            exchange_rate: 汇率，默认为 7.26
        
        Returns:
            float: 人民币金额，四舍五入到2位小数
        """
        return round(usd_amount * exchange_rate, 2)
    
    async def run_wechat_pay_query(self, query: str, product_info: dict = None):
        """
        执行微信支付查询和订单创建
        
        Args:
            query: 用户查询字符串
            product_info: 产品信息字典，包含：
                - name: 产品名称
                - usd_price: 美元价格
                - exchange_rate: 汇率（可选，默认7.26）
        
        Returns:
            dict: 包含支付订单创建结果的字典
                - success: 是否成功
                - order_number: 订单号
                - rmb_amount: 人民币金额
                - response_content: 响应内容
                - tool_calls: 工具调用列表
                - error: 错误信息（如果失败）
        """
        # 使用绝对路径来定位 MCP 配置文件
        config_path = os.path.join(os.path.dirname(__file__), "..", "Mcp", "wechat_pay_server.json")
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
                wechat_pay_agent = ChatAgent(
                    system_message=f"""
                    You are a WeChat Pay Agent for a cross-border payment service. Your task is to create a payment order in Chinese Yuan (RMB) for a product priced in US Dollars.

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

                    <div style="background: linear-gradient(135deg, #07C160, #06AD56); padding: 20px; border-radius: 12px; text-align: center; margin: 20px 0; box-shadow: 0 4px 12px rgba(7, 193, 96, 0.3);">
                        <h3 style="color: white; margin: 0 0 15px 0; font-size: 18px;">微信支付</h3>
                        <div style="background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px;">
                            <p style="margin: 5px 0; color: #333;"><strong>订单号:</strong> {order_number}</p>
                            <p style="margin: 5px 0; color: #333;"><strong>商品:</strong> {product_info["name"]}</p>
                            <p style="margin: 5px 0; color: #333;"><strong>金额:</strong> ¥{rmb_amount} (${product_info["usd_price"]} USD)</p>
                        </div>
                        <a href="[支付链接]" 
                           style="display: inline-block; background: #07C160; color: white; padding: 12px 30px; 
                                  text-decoration: none; border-radius: 6px; font-weight: bold; 
                                  transition: all 0.3s ease; box-shadow: 0 2px 8px rgba(7, 193, 96, 0.3);"
                           onmouseover="this.style.background='#06AD56'; this.style.transform='translateY(-2px)'"
                           onmouseout="this.style.background='#07C160'; this.style.transform='translateY(0)'"
                           target="_blank">
                            立即支付 - Pay Now
                        </a>
                    </div>

                    <div style="background: rgba(7, 193, 96, 0.1); border: 1px solid rgba(7, 193, 96, 0.3); 
                                border-radius: 6px; padding: 12px; margin: 1rem 0; font-size: 0.9em; color: #07C160;">
                        <strong>💡 支付说明 / Payment Instructions:</strong><br>
                        1. 点击支付按钮打开微信支付页面 / Click the button to open WeChat Pay payment page<br>
                        2. 使用微信App扫码或登录网页版完成支付 / Use WeChat App to scan QR code or login to web version<br>
                        3. 支付完成后页面会自动跳转 / Page will redirect automatically after payment completion
                    </div>
                    """,
                    model=self.model,
                    token_limit=32768,
                    tools=[*mcp_toolkit.get_tools()],
                    output_language="zh"
                )
                
                response = await wechat_pay_agent.astep(query)
                
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
                        "error": "Unable to get WeChat Pay response",
                        "order_number": order_number
                    }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "order_number": order_number
            }
    
    async def query_payment_status(self, order_number: str):
        """
        查询微信支付状态
        
        Args:
            order_number: 订单号字符串
        
        Returns:
            dict: 包含支付状态查询结果的字典
                - success: 是否成功
                - order_number: 订单号
                - status_info: 状态信息内容
                - tool_calls: 工具调用列表
                - error: 错误信息（如果失败）
        """
        # 构建 MCP 配置文件路径
        config_path = os.path.join(os.path.dirname(__file__), "..", "Mcp", "wechat_pay_server.json")
        config_path = os.path.abspath(config_path)
        
        try:
            async with MCPToolkit(config_path=config_path) as mcp_toolkit:
                wechat_pay_agent = ChatAgent(
                    system_message=f"""
                    You are a WeChat Pay Agent for querying payment status.

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
                
                response = await wechat_pay_agent.astep(f"查询订单 {order_number} 的支付状态")
                
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
                        "error": "Unable to query payment status",
                        "order_number": order_number
                    }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "order_number": order_number
            }



# 添加 A2A 服务器实现
class WeChatPayA2AServer(A2AServer):
    """
    微信支付 A2A 服务器，提供微信支付功能的 A2A 接口
    """
    def __init__(self, agent_card: AgentCard):
        super().__init__(agent_card=agent_card)
        self.wechat_pay_service = WeChatPayOrderService()
        print("✅ [WeChatPayA2AServer] Server initialized and ready.")

    def handle_task(self, task):
        """A2A 服务器的核心处理函数"""
        text = task.message.get("content", {}).get("text", "")
        print(f"📩 [WeChatPayA2AServer] Received task: '{text}'")

        # 处理健康检查请求，避免触发业务逻辑
        if text.lower().strip() in ["health check", "health", "ping", ""]:
            print("✅ [WeChatPayA2AServer] Health check request - returning healthy status")
            task.artifacts = [{"parts": [{"type": "text", "text": "healthy - Payment Agent (WeChat Pay) is operational"}]}]
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
                print("💬 [WeChatPayA2AServer] Processing complete.")

            except Exception as e:
                import traceback
                print(f"❌ [WeChatPayA2AServer] Critical error during task handling: {e}")
                traceback.print_exc()
                response_text = f"服务器内部错误: {e}"
                task.status = TaskStatus(state=TaskState.FAILED)

        task.artifacts = [{"parts": [{"type": "text", "text": str(response_text)}]}]
        return task
    
    async def process_payment_request(self, text: str):
        """处理支付请求 - 使用 WeChatPayOrderService"""
        print("💳 [WeChatPayA2AServer] 开始处理微信支付请求...")

        # 提取产品信息
        product_info = self.extract_product_info(text)

        # 使用 WeChatPayOrderService 创建支付订单
        try:
            result = await self.wechat_pay_service.run_wechat_pay_query(text, product_info)
            
            if result.get('success'):
                print(f"✅ [WeChatPayA2AServer] 微信支付订单创建成功: {result.get('order_number')}")
                return {
                    "success": True,
                    "response_content": result.get('response_content', '微信支付订单已创建'),
                    "order_number": result.get('order_number'),
                    "rmb_amount": result.get('rmb_amount')
                }
            else:
                error_msg = result.get('error', '未知错误')
                print(f"❌ [WeChatPayA2AServer] 微信支付订单创建失败: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "order_number": result.get('order_number')
                }
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"❌ [WeChatPayA2AServer] 处理支付请求时出错: {e}")
            return {
                "success": False,
                "error": str(e)
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
            print(f"⚠️ [WeChatPayA2AServer] 解析产品信息时出错: {e}，使用默认值")

        return product_info


def main():
    """主函数，用于配置和启动A2A服务器"""
    port = int(os.environ.get("WECHAT_PAY_A2A_PORT", 5006))
    
    agent_card = AgentCard(
        name="WeChat Pay Payment A2A Agent",
        description="An A2A agent that creates WeChat Pay payment orders for cross-border transactions.",
        url=f"http://localhost:{port}",
        skills=[
            AgentSkill(name="create_payment", description="Create a WeChat Pay payment order for a product.")
        ]
    )
    
    server = WeChatPayA2AServer(agent_card)
    
    print("\n" + "="*60)
    print("🚀 Starting WeChat Pay Payment A2A Server...")
    print(f"👂 Listening on http://localhost:{port}")
    print("="*60 + "\n")
    
    run_server(server, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
