import importlib.util
import os
import sys

# 动态加载带空格的模块
module_path = os.path.join(os.path.dirname(__file__), 'AgentCore', 'Society', 'a2a amazon agent.py')
spec = importlib.util.spec_from_file_location('a2a_amazon_agent', module_path)
if spec is None or spec.loader is None:
    print("无法加载模块: a2a amazon agent.py")
    sys.exit(1)
agent_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_module)

if __name__ == "__main__":
    agent_module.notify_frontend_via_websocket("订单已发货: 测试订单123456")
    print("消息已通过WebSocket发送，请在前端页面查看推送效果。") 