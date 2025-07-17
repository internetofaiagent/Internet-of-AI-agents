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
    config_path = "E:\EnjoyAI\Web3-Agent-Protocal\workspace_new\AgentCore\Mcp\paypal_server.json"
    
    # Connect to the MCP server
    async with MCPToolkit(config_path=str(config_path)) as mcp_toolkit:
        alipay_agent = ChatAgent(
            system_message="""
            你是一个经验丰富的Paypal交易员，请根据用户的需求，查询订单以及支付操作。
            """,
            model=model,
            token_limit=32768,
            tools=[*mcp_toolkit.get_tools()],
            output_language="zh"
        )
        # response = await alipay_agent.astep("创建一张金额为 $450 的房屋粉刷服务发票，添加 8% 的税费，并应用 5% 的折扣。")
        response = await alipay_agent.astep("支付订单购买1个“故事创造”，单价为 $9.99")
        print(response.msgs[0].content)
        print(response.info['tool_calls'])
        print("====================================")
        print(response)

if __name__ == "__main__":
    asyncio.run(run_example())