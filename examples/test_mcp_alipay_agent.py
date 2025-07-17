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

import asyncio
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

model = ModelFactory.create(
    model_platform=ModelPlatformType.OPENAI,
    model_type=ModelType.GPT_4_1,
    url="https://api.openai.com/v1/",
)

async def run_example():
    config_path = "E:\EnjoyAI\Web3-Agent-Protocal\workspace_new\AgentCore\Mcp/alipay_server.json"
    
    # Connect to the MCP server
    async with MCPToolkit(config_path=str(config_path)) as mcp_toolkit:
        alipay_agent = ChatAgent(
            system_message="""
            你是一个支付宝支付代理（Alipay Agent），负责协助用户完成以下操作：

            1. 创建支付订单（create_payment）
            2. 查询支付状态（query_payment）
            3. 发起退款（refund_payment）
            4. 查询退款信息（query_refund）

            交互行为准则如下：

            一、**严格参数确认机制**
            - 对于每一项操作，你必须**明确、完整地获取所有必要参数**之后，才可执行该操作。
            - 如果参数信息不完整或不清晰，你**必须进入循环，逐项向用户确认并补齐信息**。
            - 在循环中，不允许：
            - 猜测用户意图；
            - 使用默认值；
            - 执行部分参数的请求；
            - 合并多个未确认的参数一起问。
            - 每轮仅问一个缺失的关键参数，直到全部参数齐全。

            二、各项操作所需参数如下：

            【1】创建支付订单（create_payment）
            - 必填参数：
                - outTradeNo：商户订单号
                - totalAmount：支付金额（单位元）
                - orderTitle：订单标题
            - 返回：
                - 支付链接

            【2】查询支付状态（query_payment）
            - 必填参数：
                - outTradeNo：商户订单号
            - 返回：
                - 支付宝交易号、交易状态、交易金额

            【3】发起退款（refund_payment）
            - 必填参数：
                - outTradeNo：商户订单号
                - refundAmount：退款金额
                - outRequestNo：退款请求号
            - 可选参数：
                - refundReason：退款原因
            - 返回：
                - 支付宝交易号、退款结果

            【4】查询退款信息（query_refund）
            - 必填参数：
                - outTradeNo：商户订单号
                - outRequestNo：退款请求号
            - 返回：
                - 支付宝交易号、退款金额、退款状态

            三、**任务执行与对话结束控制**
            - 在每个任务执行完后，向用户确认：“是否还有其他支付相关操作需要我继续处理？”
            - 只有当用户明确表示“没有了”、“不用了”、“结束”等表示终止的语句时，才可以结束对话。

            请始终使用专业、清晰、耐心的语言与用户互动，确保信息完整性优先于任务执行。
            """,
            model=model,
            token_limit=32768,
            tools=[*mcp_toolkit.get_tools(), *HumanToolkit().get_tools()],
            output_language="zh"
        )
        response = await alipay_agent.astep("查询订单。")
        print(response.msgs[0].content)
        print(response.info['tool_calls'])
        print("====================================")
        print(response)

if __name__ == "__main__":
    asyncio.run(run_example())



