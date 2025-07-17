# from flask import Flask, request, jsonify
# import nest_asyncio
# import asyncio
# from AgentCore.Society.user_agent_a2a import AmazonServiceManager
#
# # 允许嵌套事件循环（Jupyter/Flask下必需）
# nest_asyncio.apply()
#
# app = Flask(__name__)
# service = AmazonServiceManager()
#
# @app.route('/api/chat', methods=['POST'])
# def chat():
#     data = request.get_json()
#     user_input = data.get('message', '').strip()
#     if not user_input:
#         return jsonify({'success': False, 'error': '消息内容不能为空'}), 400
#
#     # 调用 autonomous_purchase 处理
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     result = loop.run_until_complete(service.autonomous_purchase(user_input))
#     return jsonify(result)
#
# if __name__ == '__main__':
#     print("\n=== Flask 服务启动成功 ===")
#     print("POST 测试: curl -X POST http://localhost:5011/api/chat -H 'Content-Type: application/json' -d '{\"message\":\"我想买iPhone 15\"}'\n")
#     print("前端 fetch 测试:")
#     print('''fetch('http://localhost:5011/api/chat', {\n  method: 'POST',\n  headers: { 'Content-Type': 'application/json' },\n  body: JSON.stringify({ message: '我想买iPhone 15' })\n})\n.then(res => res.json())\n.then(data => console.log(data));\n''')
#     app.run(host='0.0.0.0', port=5011, debug=True)
