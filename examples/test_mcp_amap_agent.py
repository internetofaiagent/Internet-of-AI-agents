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
    config_path = "E:\EnjoyAI\Web3-Agent-Protocal\workspace_new\AgentCore\Mcp/amap_server.json"
    
    # Connect to the MCP server
    async with MCPToolkit(config_path=str(config_path)) as mcp_toolkit:
        alipay_agent = ChatAgent(
            system_message="""
            你是一个高德地图骑行助手，擅长分析用户的出行需求，并基于实时数据、路线安全性、景色美观度和道路类型，为用户推荐最优骑行路线。

            请根据用户的出发地、目的地，以及是否偏好快速到达、风景优美或避开车流等偏好，推荐一条骑行路线。

            你需要：
            1. 指出推荐的路线途经哪些关键路段或地标。
            2. 说明这条路线在时间、距离、风景、安全性等方面的优势。
            3. 简洁明了地解释为何这是当前最优选择。

            请以自然语言中文回答，条理清晰，重点突出。
            """,
            model=model,
            token_limit=32768,
            tools=[*mcp_toolkit.get_tools()],
            output_language="zh"
        )
        response = await alipay_agent.astep("给我推荐一条从北京到上海的骑行路线。")
        print(response.msgs[0].content)
        print(response.info['tool_calls'])
        print("====================================")
        print(response)

if __name__ == "__main__":
    asyncio.run(run_example())