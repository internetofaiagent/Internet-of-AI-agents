from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from camel.toolkits import HumanToolkit
from AgentCore.Tools.coingecko_toolkit import CoinGeckoToolkit
from AgentCore.Tools.chaingpt_toolkit import ChainGPTToolkit

from dotenv import load_dotenv
load_dotenv()
human_toolkit = HumanToolkit()

print("execution_agent")

model = ModelFactory.create(
    model_platform=ModelPlatformType.OPENAI,
    model_type=ModelType.GPT_4_1,
    url="https://api.openai.com/v1/",
    api_key=""
)

coin_price_agent = ChatAgent(
    system_message="你是一个加密货币历史价格助手，帮助用户获取指定加密货币在某一特定日期的历史价格数据，并作一个简单的分析。",
    model=model,
    token_limit=32768,
    tools=[*CoinGeckoToolkit().get_tools()],
    output_language="zh"
)

coin_news_agent = ChatAgent(
    system_message="你是一个加密货币新闻助手，帮助用户获取指定加密货币相关的新闻数据。并做一个简单分析。",
    model=model,
    token_limit=32768,
    tools=[*ChainGPTToolkit().get_tools()],
    output_language="zh"
)

response = coin_price_agent.step("我想知道bitcoin在2025年4月13日的历史价格数据")
print(response.info['tool_calls'][0].result)
print("----------------------------------------------")
print(response.msgs[0].content)
print("----------------------------------------------")

response = coin_news_agent.step("我想知道bitcoin新闻数据")
print(response.info['tool_calls'][0].result)
print("----------------------------------------------")
print(response.msgs[0].content)
print("----------------------------------------------")
