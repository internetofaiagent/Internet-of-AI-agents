from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from camel.toolkits import HumanToolkit

from dotenv import load_dotenv
load_dotenv()

human_toolkit = HumanToolkit()
print("solution_agent")


model = ModelFactory.create(
    model_platform=ModelPlatformType.OPENAI,
    model_type=ModelType.GPT_4_1,
    url="https://api.openai.com/v1/",
    api_key=""
)

agent = ChatAgent(
    system_message="你是一位专业的投资顾问，隶属于一个智能交易分析系统，具备丰富的金融知识、市场分析能力和个性化推荐经验。你可以根据用户提供的偏好、财务状况、风险承受能力以及市场行情，制定最优的交易与投资策略。",
    model=model,
    token_limit=4096,
    tools=[*human_toolkit.get_tools()],
    output_language="zh"
)

response = agent.step("测试一下我适合什么样的交易投资方案，然后为我推荐一个投资组合。并且对话起码要有3轮。")
print(response.msg.content)




