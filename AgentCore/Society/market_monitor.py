# file: market_monitor_server.py

import sys
import os

# --- A2A 和 CAMEL 库导入 ---
from python_a2a import A2AServer, run_server, AgentCard, AgentSkill, TaskStatus, TaskState
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.types import ModelPlatformType

# --- 项目内部模块导入 ---
# 路径设置，确保能找到项目核心模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from AgentCore.Tools.coingecko_toolkit import CoinGeckoToolkit
from AgentCore.Tools.chaingpt_toolkit import ChainGPTToolkit
from AgentCore.config import config


# ==============================================================================
#  将 MarketMonitorAgent 的完整实现迁移到这里
# ==============================================================================
class MarketMonitorAgent:
    """
    这个类包含了所有原始的市场监控、路由和多Agent协作逻辑。
    它将作为我们服务器核心功能的基础。
    """
    def __init__(self, model):
        # 注意：这里的 model 是从 MarketMonitorServer 传递进来的
        self.model = model
        
        # --- 子 Agent 初始化 ---
        print("🤖 [MarketMonitorServer] Initializing sub-agents...")
        
        # 价格 Agent
        self.coin_price_agent = ChatAgent(
            system_message="You are a professional cryptocurrency market analysis assistant. You can help users get real-time cryptocurrency prices, historical price data, and provide professional market analysis and investment advice. Please respond in English.",
            model=self.model,
            token_limit=32768,
            tools=[*CoinGeckoToolkit().get_tools()],
            output_language="en"
        )

        # 新闻 Agent
        self.coin_news_agent = ChatAgent(
            system_message="You are a professional cryptocurrency news analysis assistant. You can help users get the latest cryptocurrency-related news and provide in-depth market insights and trend analysis. Please respond in English.",
            model=self.model,
            token_limit=32768,
            tools=[*ChainGPTToolkit().get_tools()],
            output_language="en"
        )
        
        # 路由 Agent
        self.router_agent = ChatAgent(
            system_message="""You are an intelligent routing assistant responsible for analyzing user questions and deciding which professional assistant to use.

Routing Rules:
1. If the user asks about prices, exchange rates, historical prices, technical analysis, price predictions, choose 'price'
2. If the user asks about news, market dynamics, policy impacts, industry developments, choose 'news'  
3. If the user asks comprehensive questions requiring both price and news information, choose 'both'
4. If uncertain, default to 'price'

Only respond with one word: 'price', 'news', or 'both'""",
            model=self.model,
            token_limit=1024,
            output_language="en"
        )
        print("✅ [MarketMonitorServer] Sub-agents are ready.")


    def _analyze_query_type(self, user_question: str) -> str:
        """分析用户问题类型"""
        try:
            response = self.router_agent.step(user_question)
            route_decision = response.msgs[0].content.strip().lower()
            
            if 'price' in route_decision:
                return 'price'
            elif 'news' in route_decision:
                return 'news'
            elif 'both' in route_decision:
                return 'both'
            else:
                return 'price'  # 默认选择价格查询
        except Exception as e:
            print(f"⚠️ [MarketMonitorServer] Router agent failed: {e}. Defaulting to 'price'.")
            return 'price'  # 出错时默认选择价格查询

    def run(self, user_question: str) -> str:
        """Intelligently route and process user questions"""
        try:
            # 1. 分析问题类型
            query_type = self._analyze_query_type(user_question)
            print(f"🧠 [MarketMonitorServer] Router decision: '{query_type}' for query: '{user_question}'")
            
            if query_type == 'price':
                # 只使用价格查询 agent
                response = self.coin_price_agent.step(user_question)
                return response.msgs[0].content if response.msgs else "Unable to get price information"
                
            elif query_type == 'news':
                # 只使用新闻查询 agent
                response = self.coin_news_agent.step(user_question)
                return response.msgs[0].content if response.msgs else "Unable to get news information"
                
            elif query_type == 'both':
                # 同时使用两个 agent 并整合结果
                print("🤝 [MarketMonitorServer] Executing 'both' agents in parallel...")
                price_response = self.coin_price_agent.step(f"Analyze from price perspective: {user_question}")
                news_response = self.coin_news_agent.step(f"Analyze from news perspective: {user_question}")
                
                price_content = price_response.msgs[0].content if price_response.msgs else "Price information failed"
                news_content = news_response.msgs[0].content if news_response.msgs else "News information failed"
                
                # 整合结果
                combined_result = f"""📊 **Market Price Analysis**
{price_content}

📰 **Market News Updates**  
{news_content}

---
*Comprehensive Analysis: Combining price data and market news for complete market insights*"""
                
                return combined_result
                
            else:
                # 这是一个永远不会到达的分支，因为_analyze_query_type总是有默认值
                return "Sorry, I cannot understand your question. Please rephrase it."
                
        except Exception as e:
            print(f"❌ [MarketMonitorServer] Error during run: {e}")
            return f"Error processing request: {str(e)}"

# ==============================================================================
#  A2A 服务器的实现
# ==============================================================================
class MarketMonitorServer(A2AServer, MarketMonitorAgent):
    """
    这个类是最终的A2A服务器。
    它通过多重继承，同时获得了 A2AServer 的网络服务能力 和 MarketMonitorAgent 的业务逻辑能力。
    """
    def __init__(self, agent_card: AgentCard):
        # 1. 初始化 A2AServer 部分
        A2AServer.__init__(self, agent_card=agent_card)

        # 2. 初始化模型，这个模型将被传递给 MarketMonitorAgent
        print("🧠 [MarketMonitorServer] Initializing the core AI model...")
        model = ModelFactory.create(
            model_platform=ModelPlatformType.MODELSCOPE,
            model_type='Qwen/Qwen2.5-72B-Instruct',
            model_config_dict={'temperature': 0.2},
            api_key='9d3aed4d-eca1-4e0c-9805-cb923ccbbf21',
        )
        print("✅ [MarketMonitorServer] AI model is ready.")

        # 3. 初始化 MarketMonitorAgent 部分，并将模型传递进去
        MarketMonitorAgent.__init__(self, model=model)
        
        print("✅ MarketMonitorServer fully initialized.")

    def handle_task(self, task):
        """
        这是 A2A 服务器的核心处理函数。
        当收到来自 app.py 的请求时，此方法会被调用。
        """
        text = task.message.get("content", {}).get("text", "")
        
        if not text:
            response_text = "Error: Received an empty request."
        else:
            print(f"📩 [MarketMonitorServer] Received task: {text}")
            try:
                # 因为继承了 MarketMonitorAgent，所以可以直接调用 run 方法
                response_text = self.run(text)
                print("💬 [MarketMonitorServer] Core agent processing complete.")
            except Exception as e:
                response_text = f"Error processing request in MarketMonitorServer: {e}"
                print(f"❌ [MarketMonitorServer] Error: {e}")

        # 将最终结果打包成 A2A 响应
        task.artifacts = [{"parts": [{"type": "text", "text": str(response_text)}]}]
        task.status = TaskStatus(state=TaskState.COMPLETED)
        return task

def main():
    # 使用config.py中定义的端口，或者一个默认值
    port = getattr(config, 'MARKET_MONITOR_PORT', 5002)
    
    # 定义服务器的“名片”
    agent_card = AgentCard(
        name="Market Monitor A2A Agent",
        description="Provides comprehensive market analysis, including real-time prices, historical data, and the latest news.",
        url=f"http://localhost:{port}",
        skills=[
            AgentSkill(name="get_price", description="Fetches cryptocurrency price data."),
            AgentSkill(name="get_news", description="Fetches the latest cryptocurrency news."),
            AgentSkill(name="analyze_market", description="Provides a combined analysis of price and news for a given query.")
        ]
    )
    
    # 创建并启动服务器
    server = MarketMonitorServer(agent_card)
    
    print("\n" + "="*60)
    print("🚀 Starting Market Monitor A2A Server...")
    print(f"👂 Listening on http://localhost:{port}")
    print("   This server provides all market monitoring, routing, and analysis functionalities.")
    print("="*60)
    
    run_server(server, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()