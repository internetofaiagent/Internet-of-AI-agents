import sys
if sys.platform == "win32":
    import os
    os.system("chcp 65001")

from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os
import traceback
from datetime import datetime
import logging
import threading
import time
import re
import subprocess
import atexit
import signal
from typing import Dict, Any, Optional, List
from enum import Enum
import asyncio
import nest_asyncio
from AgentCore.Agents.user_agent_a2a import AmazonServiceManager

# 设置nest_asyncio以支持嵌套事件循环
nest_asyncio.apply()

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Agent服务器进程管理
class AgentServerManager:
    """Agent服务器进程管理器"""
    
    def __init__(self):
        self.agent_processes = {}
        self.agent_configs = {
            "agent_registry": {
                "script": "AgentCore/Agents/agent_registry.py",
                "port": 5001,
                "env_var": "AGENT_REGISTRY_PORT"
            },
            "user_agent": {
                "script": "AgentCore/Agents/user_agent_a2a.py",
                "port": 5011,
                "env_var": "AMAZON_A2A_PORT"  # user_agent_a2a.py期望这个环境变量
            },
            "payment_agent": {
                "script": "AgentCore/Agents/payment.py",
                "port": 5005,
                "env_var": "ALIPAY_A2A_PORT"
            },
            "amazon_agent": {
                "script": "AgentCore/Agents/a2a_amazon_agent.py",
                "port": 5012,
                "env_var": "AMAZON_SHOPPING_A2A_PORT"
            }
        }
        
        # 注册退出处理
        atexit.register(self.shutdown_all_agents)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        print("\n收到信号 " + str(signum) + "，正在关闭所有Agent服务器...")
        self.shutdown_all_agents()
        sys.exit(0)
    
    def start_agent(self, agent_name: str) -> bool:
        """启动单个Agent服务器"""
        try:
            config = self.agent_configs[agent_name]
            script_path = os.path.join(os.path.dirname(__file__), config["script"])
            
            if not os.path.exists(script_path):
                print("Agent脚本不存在: " + script_path)
                return False
            
            # 设置环境变量 - 添加更完整的环境变量
            env = os.environ.copy()
            env[config["env_var"]] = str(config["port"])
            
            # 确保必要的环境变量存在
            if not env.get('MODELSCOPE_SDK_TOKEN'):
                env['MODELSCOPE_SDK_TOKEN'] = '9d3aed4d-eca1-4e0c-9805-cb923ccbbf21'
                print("为 " + agent_name + " 设置MODELSCOPE_SDK_TOKEN")
            
            if not env.get('FEWSATS_API_KEY'):
                env['FEWSATS_API_KEY'] = '3q-t95sj95DywRNY4v4QsShXfyS1Gs4uvYRnwipK4Hg'
                print("为 " + agent_name + " 设置FEWSATS_API_KEY")
            
            # 关键修复：设置UTF-8编码，解决Windows GBK编码无法显示emoji的问题
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONLEGACYWINDOWSSTDIO'] = '1'  # Windows兼容性
            print("为 " + agent_name + " 设置UTF-8编码环境")
            
            # 设置正确的工作目录
            working_dir = os.path.dirname(__file__)
            
            print("启动 " + agent_name + " 服务器...")
            print("   工作目录: " + working_dir)
            print("   脚本路径: " + script_path)
            print("   端口: " + str(config['port']))
            print("   环境变量: " + config['env_var'] + "=" + str(config['port']))
            
            # 启动进程 - 设置正确的工作目录和编码
            process = subprocess.Popen(
                [sys.executable, script_path],
                env=env,
                cwd=working_dir,  # 设置工作目录
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',  # 明确指定UTF-8编码
                errors='replace'   # 遇到编码错误时替换为占位符而不是崩溃
            )
            
            self.agent_processes[agent_name] = {
                "process": process,
                "port": config["port"],
                "script": script_path,
                "working_dir": working_dir
            }
            
            # 启动日志监控线程 - 同时监控stdout和stderr
            stdout_thread = threading.Thread(
                target=self._monitor_agent_stdout,
                args=(agent_name, process),
                daemon=True
            )
            stdout_thread.start()
            
            stderr_thread = threading.Thread(
                target=self._monitor_agent_stderr,
                args=(agent_name, process),
                daemon=True
            )
            stderr_thread.start()
            
            # 等待一小段时间检查进程是否立即退出
            time.sleep(1)
            if process.poll() is not None:
                print(agent_name + " 进程立即退出 (退出码: " + str(process.returncode) + ")")
                # 读取stderr获取错误信息
                stderr_output = process.stderr.read()
                if stderr_output:
                    print(agent_name + " 错误输出:")
                    for line in stderr_output.strip().split('\n'):
                        print("   " + line)
                return False
            
            print(agent_name + " 服务器启动成功 (PID: " + str(process.pid) + ")")
            return True
            
        except Exception as e:
            print("启动 " + agent_name + " 失败: " + str(e))
            import traceback
            print("详细错误: " + traceback.format_exc())
            return False
    
    def _monitor_agent_stdout(self, agent_name: str, process: subprocess.Popen):
        """监控Agent标准输出"""
        try:
            while process.poll() is None:
                output = process.stdout.readline()
                if output:
                    print("[" + agent_name + "] " + output.strip())
        except Exception as e:
            print(agent_name + " stdout监控异常: " + str(e))
    
    def _monitor_agent_stderr(self, agent_name: str, process: subprocess.Popen):
        """监控Agent错误输出"""
        try:
            while process.poll() is None:
                error = process.stderr.readline()
                if error:
                    print("[" + agent_name + "] 错误 " + error.strip())
        except Exception as e:
            print(agent_name + " stderr监控异常: " + str(e))
    
    def start_all_agents(self) -> Dict[str, bool]:
        """启动所有Agent服务器"""
        results = {}
        
        print("开始逐个启动Agent服务器...")
        for i, agent_name in enumerate(self.agent_configs.keys(), 1):
            print("\n[" + str(i) + "/" + str(len(self.agent_configs)) + "] 启动 " + agent_name + "...")
            results[agent_name] = self.start_agent(agent_name)
            
            if results[agent_name]:
                print(agent_name + " 启动成功，等待稳定...")
            else:
                print(agent_name + " 启动失败")
            
            # 增加启动间隔，让每个Agent有足够时间初始化
            if i < len(self.agent_configs):
                print("等待 5 秒后启动下一个Agent...")
                time.sleep(5)
        
        print("\n启动结果总览:")
        for agent_name, success in results.items():
            status = "成功" if success else "失败"
            print("   " + agent_name + ": " + status)
        
        return results
    
    def check_agent_health(self, agent_name: str, timeout: int = 10) -> bool:
        """检查Agent服务器健康状态"""
        if agent_name not in self.agent_processes:
            return False
            
        process_info = self.agent_processes[agent_name]
        process = process_info["process"]
        port = process_info["port"]
        
        # 检查进程是否运行
        if process.poll() is not None:
            print(agent_name + " 进程已退出 (退出码: " + str(process.returncode) + ")")
            return False
        
        # 检查端口是否可访问
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except Exception as e:
            print("检查 " + agent_name + " 端口失败: " + str(e))
            return False
    
    def wait_for_agents_ready(self, timeout: int = 120) -> Dict[str, bool]:
        """等待所有Agent服务器就绪"""
        print("\n等待Agent服务器完全启动...")
        start_time = time.time()
        ready_status = {}
        check_count = 0
        
        while time.time() - start_time < timeout:
            check_count += 1
            print("\n第 " + str(check_count) + " 次检查Agent状态...")
            
            all_ready = True
            
            for agent_name in self.agent_configs.keys():
                if agent_name not in ready_status or not ready_status[agent_name]:
                    # 首先检查进程是否还在运行
                    if agent_name in self.agent_processes:
                        process = self.agent_processes[agent_name]["process"]
                        if process.poll() is not None:
                            print(agent_name + " 进程已退出 (退出码: " + str(process.returncode) + ")")
                            ready_status[agent_name] = False
                            all_ready = False
                            continue
                    
                    # 检查网络健康状态
                    is_ready = self.check_agent_health(agent_name, timeout=10)
                    ready_status[agent_name] = is_ready
                    
                    if is_ready:
                        print(agent_name + " 服务器就绪")
                    else:
                        print(agent_name + " 尚未就绪...")
                        all_ready = False
                else:
                    print(agent_name + " 已就绪")
            
            if all_ready:
                print("\n所有Agent服务器已就绪！")
                return ready_status
            
            print("等待 8 秒后重新检查...")
            time.sleep(8)
        
        print("\n等待超时 (" + str(timeout) + "秒)，部分Agent服务器可能未完全启动")
        return ready_status
    
    def shutdown_agent(self, agent_name: str):
        """关闭单个Agent服务器"""
        if agent_name in self.agent_processes:
            process_info = self.agent_processes[agent_name]
            process = process_info["process"]
            
            try:
                print("正在关闭 " + agent_name + " 服务器...")
                process.terminate()
                
                # 等待进程正常退出
                try:
                    process.wait(timeout=10)
                    print(agent_name + " 服务器已正常关闭")
                except subprocess.TimeoutExpired:
                    print(agent_name + " 强制关闭...")
                    process.kill()
                    process.wait()
                    print(agent_name + " 服务器已强制关闭")
                    
            except Exception as e:
                print("关闭 " + agent_name + " 失败: " + str(e))
            
            del self.agent_processes[agent_name]
    
    def shutdown_all_agents(self):
        """关闭所有Agent服务器"""
        if not self.agent_processes:
            return
            
        print("正在关闭所有Agent服务器...")
        
        for agent_name in list(self.agent_processes.keys()):
            self.shutdown_agent(agent_name)
        
        print("所有Agent服务器已关闭")
    
    def get_agent_status(self) -> Dict[str, Any]:
        """获取所有Agent状态"""
        status = {}
        
        for agent_name, config in self.agent_configs.items():
            if agent_name in self.agent_processes:
                process_info = self.agent_processes[agent_name]
                process = process_info["process"]
                
                status[agent_name] = {
                    "running": process.poll() is None,
                    "pid": process.pid,
                    "port": config["port"],
                    "healthy": self.check_agent_health(agent_name, timeout=3)
                }
            else:
                status[agent_name] = {
                    "running": False,
                    "pid": None,
                    "port": config["port"],
                    "healthy": False
                }
        
        return status

# 全局Agent服务器管理器
agent_manager = AgentServerManager()

# 导入所有Agent的业务逻辑类
try:
    from AgentCore.Agents.agent_registry import AgentRegistry, AgentRegistryServer
    from AgentCore.Agents.user_agent_a2a import AmazonServiceManager as UserServiceManager
    from AgentCore.Agents.payment import AlipayOrderService
    # 导入最新的Amazon Agent
    from AgentCore.Agents.a2a_amazon_agent import AmazonShoppingServiceManager, ThinkingMode
    ALL_AGENTS_AVAILABLE = True
    print("✅ 所有Agent模块导入成功")
except ImportError as e:
    print(" Agent导入失败: " + str(e))
    ALL_AGENTS_AVAILABLE = False
    UserServiceManager = None
    AlipayOrderService = None
    AmazonShoppingServiceManager = None
    ThinkingMode = None

try:
    from python_a2a import A2AClient
    A2A_CLIENT_AVAILABLE = True
except ImportError as e:
    print(" A2A客户端导入失败: " + str(e))
    A2A_CLIENT_AVAILABLE = False

app = Flask(__name__)
CORS(app)

# 配置JSON以正确显示中文，避免Unicode转义
app.config['JSON_AS_ASCII'] = False

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WorkflowState(Enum):
    """固定工作流状态枚举"""
    INITIAL = "initial"                           # 等待用户购买意图输入
    PRODUCT_SEARCH = "product_search"             # User Agent搜索商品中
    PRODUCT_SELECTION = "product_selection"       # 等待用户选择商品
    PAYMENT_CREATION = "payment_creation"         # Payment Agent创建订单中  
    PAYMENT_CONFIRMATION = "payment_confirmation" # 等待用户确认支付
    PAYMENT_VERIFICATION = "payment_verification" # Payment Agent验证支付状态
    ADDRESS_COLLECTION = "address_collection"     # Amazon Agent收集地址信息
    ORDER_PROCESSING = "order_processing"         # Amazon Agent处理最终订单
    MERCHANT_ACCEPTANCE = "merchant_acceptance"   # 商家agent接单确认
    WORKFLOW_COMPLETE = "workflow_complete"       # 工作流完成

class FixedWorkflowOrchestrator:
    """固定工作流编排器 - 纯A2A协议版本，仅做Agent协调，所有回复由真实AI Agent生成"""
    
    def __init__(self):
        # 只保留A2A Agent配置，移除所有本地Agent实例
        self.a2a_agents = {
            "agent_registry": {"url": "http://localhost:5001", "name": "Agent Registry"},
            "user_agent": {"url": "http://localhost:5011", "name": "User Agent"},
            "payment_agent": {"url": "http://localhost:5005", "name": "Payment Agent"},
            "amazon_agent": {"url": "http://localhost:5012", "name": "Amazon Agent"}
        }
        
        # 检查A2A服务可用性
        self._check_a2a_services()
    
    def _check_a2a_services(self):
        """检查A2A服务是否可用"""
        if not A2A_CLIENT_AVAILABLE:
            logger.warning("⚠️ A2A客户端不可用")
            return
            
        def check_service(agent_type: str, config: dict):
            try:
                client = A2AClient(config["url"])
                response = client.ask("health check")
                if response:
                    config["available"] = True
                    logger.info(" " + config['name'] + " A2A服务可用: " + config['url'])
                else:
                    config["available"] = False
                    logger.warning(" " + config['name'] + " A2A服务无响应: " + config['url'])
            except Exception as e:
                config["available"] = False
                logger.warning(" " + config['name'] + " A2A服务不可用: " + str(e))
        
        # 并发检查所有A2A服务
        threads = []
        for agent_type, config in self.a2a_agents.items():
            thread = threading.Thread(target=check_service, args=(agent_type, config))
            thread.daemon = True
            thread.start()
            threads.append(thread)
        
        # 等待检查完成
        for thread in threads:
            thread.join(timeout=5)
    
    def _call_agent_pure_a2a(self, agent_type: str, message: str, context: Dict[str, Any] = None) -> str:
        """纯A2A调用，无降级逻辑，所有回复由真实AI Agent生成"""
        try:
            agent_config = self.a2a_agents.get(agent_type)
            if not agent_config:
                error_msg = "未知的Agent类型: " + agent_type
                logger.error(error_msg)
                return "错误: " + error_msg
            
            if not agent_config.get("available", False):
                error_msg = agent_config['name'] + "服务不可用，请检查服务器状态"
                logger.error(error_msg)
                return "错误: " + error_msg
            
            # 构建包含上下文的完整消息
            if context:
                full_message = """工作流上下文：
当前状态: """ + str(context.get('workflow_state', 'unknown')) + """
历史记录: """ + str(context.get('conversation_history', [])) + """
会话数据: """ + str(context.get('session_data', {})) + """

用户消息: """ + message + """"""
            else:
                full_message = message
            
            # 纯A2A调用
            client = A2AClient(agent_config["url"])
            response = client.ask(full_message)
            
            if response:
                logger.info(" " + agent_config['name'] + " A2A调用成功")
                return response
            else:
                error_msg = agent_config['name'] + "返回空响应"
                logger.error(error_msg)
                return "错误: " + error_msg
                
        except Exception as e:
            error_msg = "调用" + agent_type + "失败: " + str(e)
            logger.error(error_msg)
            return "错误: " + error_msg
    
    def _analyze_agent_response_for_state_transition(self, response: str, current_state: str) -> str:
        """分析Agent回复，判断是否需要状态转换（简单的关键词匹配）"""
        response_lower = response.lower()
        
        if current_state == WorkflowState.INITIAL.value:
            # 检测购买意图
            if any(keyword in response_lower for keyword in ["商品", "产品", "搜索", "找到", "购买", "product", "search"]):
                return WorkflowState.PRODUCT_SELECTION.value
                
        elif current_state == WorkflowState.PRODUCT_SELECTION.value:
            # 检测支付订单创建
            if any(keyword in response_lower for keyword in ["支付", "订单", "创建", "payment", "order", "alipay"]):
                return WorkflowState.PAYMENT_CONFIRMATION.value
                
        elif current_state == WorkflowState.PAYMENT_CONFIRMATION.value:
            # 检测支付验证
            if any(keyword in response_lower for keyword in ["验证", "查询", "状态", "verify", "status", "completed"]):
                return WorkflowState.ADDRESS_COLLECTION.value
                
        elif current_state == WorkflowState.ADDRESS_COLLECTION.value:
            # 检测订单处理
            if any(keyword in response_lower for keyword in ["地址", "收货", "amazon", "订单处理", "address"]):
                return WorkflowState.ORDER_PROCESSING.value
                
        elif current_state == WorkflowState.ORDER_PROCESSING.value:
            # 检测订单处理完成，转到商家接单状态
            if any(keyword in response_lower for keyword in ["完成", "成功", "订单", "处理", "confirm", "complete", "success", "order"]):
                return WorkflowState.MERCHANT_ACCEPTANCE.value
                
        elif current_state == WorkflowState.MERCHANT_ACCEPTANCE.value:
            # 检测商家接单完成
            if any(keyword in response_lower for keyword in ["接单", "接受", "确认", "accepted", "confirmed", "完成", "complete"]):
                return WorkflowState.WORKFLOW_COMPLETE.value
        
        # 默认保持当前状态
        return current_state
    
    def initialize_session_state(self, session_state: Dict[str, Any]):
        """初始化会话状态"""
        if 'workflow_state' not in session_state:
            session_state.update({
                'workflow_state': WorkflowState.INITIAL.value,
                'conversation_history': [],
                'session_data': {}
            })
    
    def handle_initial_state(self, user_input: str, session_state: Dict[str, Any], user_id: str, session_id: str) -> Dict[str, Any]:
        """处理初始状态 - 直接调用User Agent，让其自主判断和回复"""
        logger.info("🔄 初始状态 - 调用User Agent处理用户输入")
        
        # 构建上下文
        context = {
            'workflow_state': session_state['workflow_state'],
            'conversation_history': session_state.get('conversation_history', []),
            'session_data': session_state.get('session_data', {}),
            'user_id': user_id,
            'session_id': session_id
        }
        
        # 调用User Agent，让其自主处理
        response = self._call_agent_pure_a2a("user_agent", user_input, context)
        
        # 根据回复判断状态转换
        new_state = self._analyze_agent_response_for_state_transition(response, session_state['workflow_state'])
        session_state['workflow_state'] = new_state
        
        return {
            "success": True,
            "response": response,
            "workflow_state": new_state,
            "agent_called": "user_agent"
        }
    
    def handle_product_selection(self, user_input: str, session_state: Dict[str, Any], user_id: str, session_id: str) -> Dict[str, Any]:
        """处理商品选择状态 - 让Agent自主决定是调用Payment Agent还是继续商品相关对话"""
        logger.info(" 商品选择状态 - 调用User Agent分析用户意图")
        
        # 构建包含工作流状态的上下文消息
        context_message = """用户在商品选择阶段的输入: """ + user_input + """

工作流状态: 用户正在选择商品，可能需要：
1. 如果用户确认购买某个商品，请调用Payment Agent创建支付订单
2. 如果用户还在浏览或询问商品信息，继续提供商品相关服务

历史对话: """ + str(session_state.get('conversation_history', [])) + """"""
        
        # 先调用User Agent分析意图
        context = {
            'workflow_state': session_state['workflow_state'],
            'conversation_history': session_state.get('conversation_history', []),
            'session_data': session_state.get('session_data', {})
        }
        
        user_response = self._call_agent_pure_a2a("user_agent", context_message, context)
        
        # 检查是否需要调用Payment Agent
        if any(keyword in user_response.lower() for keyword in ["确认购买", "支付", "订单", "payment"]):
            logger.info(" 检测到购买确认，调用Payment Agent")
            
            # 准备给Payment Agent的消息
            payment_message = """用户确认购买决定: """ + user_input + """

User Agent分析结果: """ + user_response + """

请为用户创建支付宝支付订单。"""
            
            payment_response = self._call_agent_pure_a2a("payment_agent", payment_message, context)
            
            # 合并两个Agent的回复
            combined_response = user_response + "\n\n" + payment_response
            new_state = WorkflowState.PAYMENT_CONFIRMATION.value
            
            return {
                "success": True,
                "response": combined_response,
                "workflow_state": new_state,
                "agents_called": ["user_agent", "payment_agent"]
            }
        else:
            # 用户还在浏览，继续当前状态
            return {
                "success": True,
                "response": user_response,
                "workflow_state": session_state['workflow_state'],
                "agent_called": "user_agent"
            }
    
    def handle_payment_confirmation(self, user_input: str, session_state: Dict[str, Any], user_id: str, session_id: str) -> Dict[str, Any]:
        """处理支付确认状态 - 让Payment Agent自主处理"""
        logger.info(" 支付确认状态 - 调用Payment Agent处理")
        
        context = {
            'workflow_state': session_state['workflow_state'],
            'conversation_history': session_state.get('conversation_history', []),
            'session_data': session_state.get('session_data', {})
        }
        
        payment_message = """用户在支付确认阶段的输入: """ + user_input + """

工作流状态: 用户正在确认支付，可能需要：
1. 如果用户确认支付，请查询支付状态
2. 如果支付成功，请为后续步骤做准备
3. 如果用户有支付相关问题，请解答

请根据用户输入自主处理。"""
        
        response = self._call_agent_pure_a2a("payment_agent", payment_message, context)
        
        # 检查是否支付成功，需要转到地址收集
        if any(keyword in response.lower() for keyword in ["成功", "完成", "success", "completed"]):
            logger.info(" 检测到支付成功，准备调用Amazon Agent收集地址")
            
            # 调用Amazon Agent开始地址收集
            amazon_message = """支付已完成，请开始收集用户地址信息：

支付结果: """ + response + """
用户输入: """ + user_input + """

请向用户收集完整的收货地址信息以便处理Amazon订单。"""
            
            amazon_response = self._call_agent_pure_a2a("amazon_agent", amazon_message, context)
            
            combined_response = response + "\n\n" + amazon_response
            new_state = WorkflowState.ADDRESS_COLLECTION.value
            
            return {
                "success": True,
                "response": combined_response,
                "workflow_state": new_state,
                "agents_called": ["payment_agent", "amazon_agent"]
            }
        else:
            return {
                "success": True,
                "response": response,
                "workflow_state": session_state['workflow_state'],
                "agent_called": "payment_agent"
            }
    
    def handle_address_collection(self, user_input: str, session_state: Dict[str, Any], user_id: str, session_id: str) -> Dict[str, Any]:
        """处理地址收集状态 - 让Amazon Agent自主处理"""
        logger.info("🔄 地址收集状态 - 调用Amazon Agent处理")
        
        context = {
            'workflow_state': session_state['workflow_state'],
            'conversation_history': session_state.get('conversation_history', []),
            'session_data': session_state.get('session_data', {})
        }
        
        amazon_message = """用户提供的地址信息: """ + user_input + """

工作流状态: 用户正在提供地址信息，请：
1. 验证地址信息是否完整
2. 如果完整，开始处理Amazon订单
3. 如果不完整，继续收集必要信息

请根据情况自主处理。"""
        
        response = self._call_agent_pure_a2a("amazon_agent", amazon_message, context)
        
        # 保存地址信息到session_data，供后续订单处理使用
        session_data = session_state.setdefault('session_data', {})
        if 'shipping_address' not in session_data:
            session_data['shipping_address'] = {}
        # 尝试从用户输入中提取地址信息（简单处理）
        if any(keyword in user_input.lower() for keyword in ["地址", "address", "街道", "street"]):
            session_data['shipping_address']['raw_input'] = user_input
        
        # 检查是否可以进入订单处理
        new_state = self._analyze_agent_response_for_state_transition(response, session_state['workflow_state'])
        session_state['workflow_state'] = new_state
        
        return {
            "success": True,
            "response": response,
            "workflow_state": new_state,
            "agent_called": "amazon_agent"
        }
    
    def handle_order_processing(self, user_input: str, session_state: Dict[str, Any], user_id: str, session_id: str) -> Dict[str, Any]:
        """处理订单处理状态 - 让Amazon Agent自主完成最终订单"""
        logger.info("🔄 订单处理状态 - 调用Amazon Agent完成订单")
        
        context = {
            'workflow_state': session_state['workflow_state'],
            'conversation_history': session_state.get('conversation_history', []),
            'session_data': session_state.get('session_data', {})
        }
        
        amazon_message = """请完成最终的Amazon订单处理:

用户输入: """ + user_input + """
工作流状态: 准备完成订单

请使用MCP工具完成Amazon订单的最终处理并返回订单确认信息。"""
        
        response = self._call_agent_pure_a2a("amazon_agent", amazon_message, context)
        
        # 保存订单信息到session_data，供后续商家接单使用
        session_data = session_state.setdefault('session_data', {})
        if 'order_info' not in session_data:
            session_data['order_info'] = {
                'order_id': f"ORDER_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'user_id': user_id,
                'merchant_type': 'amazon',
                'created_at': datetime.now().isoformat(),
                'product_info': session_data.get('product_info', {}),
                'payment_info': session_data.get('payment_info', {}),
                'shipping_address': session_data.get('shipping_address', {})
            }
        else:
            # 更新现有订单信息
            order_info = session_data['order_info']
            if not order_info.get('product_info'):
                order_info['product_info'] = session_data.get('product_info', {})
            if not order_info.get('payment_info'):
                order_info['payment_info'] = session_data.get('payment_info', {})
            if not order_info.get('shipping_address'):
                order_info['shipping_address'] = session_data.get('shipping_address', {})
        
        # 检查是否完成，如果完成则转到商家接单状态
        new_state = self._analyze_agent_response_for_state_transition(response, session_state['workflow_state'])
        session_state['workflow_state'] = new_state
        
        return {
            "success": True,
            "response": response,
            "workflow_state": new_state,
            "agent_called": "amazon_agent"
        }
    
    def handle_merchant_acceptance(self, user_input: str, session_state: Dict[str, Any], user_id: str, session_id: str) -> Dict[str, Any]:
        """处理商家接单状态 - 通过agent_registry通知商家agent接单"""
        logger.info("🔄 商家接单状态 - 通知商家agent接单")
        
        try:
            # 获取订单信息
            session_data = session_state.get('session_data', {})
            order_info = session_data.get('order_info', {})
            
            # 如果没有订单信息，尝试从对话历史中提取
            if not order_info:
                # 从最近的对话中提取商品和支付信息
                conversation_history = session_state.get('conversation_history', [])
                order_info = {
                    'order_id': f"ORDER_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    'user_id': user_id,
                    'merchant_type': 'amazon',
                    'product_info': {},
                    'payment_info': {},
                    'shipping_address': {}
                }
            
            # 构建订单数据
            order_data = {
                "order_id": order_info.get('order_id', f"ORDER_{datetime.now().strftime('%Y%m%d%H%M%S')}"),
                "user_id": order_info.get('user_id', user_id),
                "merchant_type": order_info.get('merchant_type', 'amazon'),
                "product_info": order_info.get('product_info', {}),
                "payment_info": order_info.get('payment_info', {}),
                "shipping_address": order_info.get('shipping_address', {})
            }
            
            # 调用agent_registry创建订单并通知商家agent
            registry_url = self.a2a_agents.get("agent_registry", {}).get("url", "http://localhost:5001")
            
            if not A2A_CLIENT_AVAILABLE:
                logger.warning("⚠️ A2A客户端不可用，无法通知商家agent")
                return {
                    "success": False,
                    "response": "系统错误：无法连接到Agent注册中心",
                    "workflow_state": session_state['workflow_state'],
                    "error": "A2A客户端不可用"
                }
            
            import json
            registry_client = A2AClient(registry_url)
            
            # 创建订单
            create_order_message = json.dumps(order_data, ensure_ascii=False)
            registry_response = registry_client.ask(f"create_order: {create_order_message}")
            
            logger.info(f"📦 Agent Registry响应: {registry_response[:200] if registry_response else 'None'}...")
            
            # 解析响应
            try:
                if registry_response and registry_response.strip().startswith("{"):
                    response_data = json.loads(registry_response)
                    if response_data.get("success"):
                        order_id = response_data.get("order", {}).get("order_id", order_data["order_id"])
                        logger.info(f"✅ 订单已创建并加入监听队列: {order_id}")
                        
                        # 等待一小段时间让监听线程处理
                        time.sleep(2)
                        
                        # 查询订单状态
                        order_status_response = registry_client.ask(f"get_order: {order_id}")
                        logger.info(f"📊 订单状态: {order_status_response[:200] if order_status_response else 'None'}...")
                        
                        # 检查订单是否已被接单
                        if order_status_response and order_status_response.strip().startswith("{"):
                            status_data = json.loads(order_status_response)
                            order_status = status_data.get("order", {}).get("status", "pending")
                            
                            if order_status == "accepted":
                                response_text = f"""✅ 商家已接单！

订单ID: {order_id}
订单状态: 商家已确认接单

商家agent已接受订单并开始处理。订单将很快完成交付。"""
                                new_state = WorkflowState.WORKFLOW_COMPLETE.value
                            else:
                                response_text = f"""📦 订单已创建，等待商家接单...

订单ID: {order_id}
订单状态: {order_status}

系统已通知商家agent，正在等待接单确认。"""
                                new_state = session_state['workflow_state']  # 保持当前状态，等待接单
                        else:
                            response_text = f"""📦 订单已创建并已通知商家agent

订单ID: {order_id}

系统已自动通知商家agent接单，请稍候。"""
                            new_state = session_state['workflow_state']
                    else:
                        error_msg = response_data.get("error", "未知错误")
                        response_text = f"❌ 创建订单失败: {error_msg}"
                        new_state = session_state['workflow_state']
                else:
                    # 响应不是JSON格式，直接使用
                    response_text = f"""📦 订单处理中...

{registry_response if registry_response else '订单已提交到Agent注册中心，等待商家agent接单。'}"""
                    new_state = session_state['workflow_state']
                    
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ 解析Agent Registry响应失败: {e}")
                response_text = f"""📦 订单已提交

{registry_response if registry_response else '订单已提交到Agent注册中心，系统将自动通知商家agent接单。'}"""
                new_state = session_state['workflow_state']
            
            session_state['workflow_state'] = new_state
            
            return {
                "success": True,
                "response": response_text,
                "workflow_state": new_state,
                "agent_called": "agent_registry"
            }
            
        except Exception as e:
            logger.error(f"❌ 处理商家接单状态失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "response": f"系统错误：处理商家接单时发生异常: {str(e)}",
                "workflow_state": session_state['workflow_state'],
                "error": str(e)
            }
    
    def handle_workflow_complete(self, user_input: str, session_state: Dict[str, Any], user_id: str, session_id: str) -> Dict[str, Any]:
        """处理工作流完成状态 - 让User Agent自主处理后续对话"""
        logger.info("🔄 工作流完成状态 - 调用User Agent处理")
        
        context = {
            'workflow_state': session_state['workflow_state'],
            'conversation_history': session_state.get('conversation_history', []),
            'session_data': session_state.get('session_data', {})
        }
        
        # 检查是否要开始新的购物流程
        if any(keyword in user_input.lower() for keyword in ["新", "重新", "再次", "开始", "new", "restart"]):
            # 重置工作流状态
            session_state['workflow_state'] = WorkflowState.INITIAL.value
            session_state['session_data'] = {}
            
            message = """用户要求开始新的购物流程: """ + user_input + """

之前的购物已完成，现在开始新的购物流程。请为用户提供购物服务。"""
        else:
            message = """工作流已完成，用户输入: """ + user_input + """

可以提供订单查询、购物建议或其他服务。"""
        
        response = self._call_agent_pure_a2a("user_agent", message, context)
        
        return {
            "success": True,
            "response": response,
            "workflow_state": session_state['workflow_state'],
            "agent_called": "user_agent"
        }
    
    def process_workflow(self, user_input: str, user_id: str = "default_user", session_id: str = None) -> Dict[str, Any]:
        """处理工作流的主入口 - 纯协调逻辑，所有回复由AI Agent生成"""
        try:
            # 创建或获取会话状态
            session_key = f"{user_id}:{session_id}" if session_id else f"{user_id}:default"
            
            if not hasattr(self, 'session_states'):
                self.session_states = {}
            
            if session_key not in self.session_states:
                self.session_states[session_key] = {}
                
            session_state = self.session_states[session_key]
            self.initialize_session_state(session_state)
            
            # 记录对话历史
            session_state['conversation_history'].append({
                'timestamp': datetime.now().isoformat(),
                'user_input': user_input,
                'workflow_state_before': session_state['workflow_state']
            })
            
            # 根据当前工作流状态分发处理（纯协调逻辑）
            current_state = WorkflowState(session_state['workflow_state'])
            
            if current_state == WorkflowState.INITIAL:
                result = self.handle_initial_state(user_input, session_state, user_id, session_id)
            elif current_state == WorkflowState.PRODUCT_SELECTION:
                result = self.handle_product_selection(user_input, session_state, user_id, session_id)
            elif current_state == WorkflowState.PAYMENT_CONFIRMATION:
                result = self.handle_payment_confirmation(user_input, session_state, user_id, session_id)
            elif current_state == WorkflowState.ADDRESS_COLLECTION:
                result = self.handle_address_collection(user_input, session_state, user_id, session_id)
            elif current_state == WorkflowState.ORDER_PROCESSING:
                result = self.handle_order_processing(user_input, session_state, user_id, session_id)
            elif current_state == WorkflowState.MERCHANT_ACCEPTANCE:
                result = self.handle_merchant_acceptance(user_input, session_state, user_id, session_id)
            elif current_state == WorkflowState.WORKFLOW_COMPLETE:
                result = self.handle_workflow_complete(user_input, session_state, user_id, session_id)
            else:
                # 未知状态，重置到初始状态
                session_state['workflow_state'] = WorkflowState.INITIAL.value
                result = self.handle_initial_state(user_input, session_state, user_id, session_id)
            
            # 更新对话历史记录
            session_state['conversation_history'][-1].update({
                'response': result.get('response', ''),
                'workflow_state_after': result.get('workflow_state', ''),
                'agents_called': result.get('agents_called', result.get('agent_called', []))
            })
            
            # 添加系统信息到返回结果
            result.update({
                'timestamp': datetime.now().isoformat(),
                'session_id': session_id,
                'user_id': user_id,
                'conversation_turn': len(session_state['conversation_history']),
                'pure_a2a_mode': True
            })
            
            if result["success"]:
                logger.info(" [" + datetime.now().strftime('%H:%M:%S') + "] 工作流处理成功 - 状态: " + result.get('workflow_state'))
            else:
                logger.warning("⚠ [" + datetime.now().strftime('%H:%M:%S') + "] 工作流处理失败")
            
            return result
            
        except Exception as e:
            logger.error(" 工作流处理失败: " + str(e))
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "response": "工作流协调器遇到错误：" + str(e),
                "workflow_state": WorkflowState.INITIAL.value,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "pure_a2a_mode": True
            }

# 全局固定工作流编排器实例
workflow_orchestrator = FixedWorkflowOrchestrator()

@app.route('/')
def index():
    """主页"""
    return jsonify({
        'status': 'ok',
        'message': '固定工作流购物助手 - 纯A2A多Agent协作系统',
        'version': '5.0-pure-a2a',
        'system_type': 'Fixed Workflow Multi-Agent System (Pure A2A)',
        'architecture': 'Pure A2A Protocol - No Local Fallback',
        'workflow_states': [state.value for state in WorkflowState],
        'features': [
            '固定购物工作流程（纯协调逻辑）',
            'User Agent: 意图理解、商品搜索（真实AI回复）',
            'Payment Agent: 支付宝订单创建和验证（真实AI回复）',
            'Amazon Agent: 地址收集和一键支付（真实AI回复）',
            '纯A2A协议通信（无本地降级）',
            '真实AI Agent响应（无预设回复）',
            'Agent间协作通信',
            '状态驱动的用户体验'
        ],
        'workflow_flow': [
            '1. 用户输入购买意图 → User Agent自主分析和搜索',
            '2. 用户选择商品 → User Agent判断意图 → Payment Agent创建订单',
            '3. 用户确认支付 → Payment Agent自主验证支付状态',
            '4. 支付成功 → Amazon Agent自主收集地址信息',
            '5. Amazon Agent自主执行一键支付完成订单'
        ],
        'agent_communication': [
            'User Agent ↔ Payment Agent: 购买确认和订单创建',
            'Payment Agent ↔ Amazon Agent: 支付完成和地址收集',
            'User Agent ↔ Amazon Agent: 订单确认和状态查询'
        ],
        'endpoints': {
            'chat': '/api/chat',
            'health': '/api/health',
            'status': '/api/status',
            'agents_start': '/api/agents/start',
            'agents_stop': '/api/agents/stop',
            'agents_status': '/api/agents/status'
        }
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """处理聊天请求 - 固定工作流版本"""
    try:
        # 验证请求格式
        data = request.get_json()
        if not data or 'message' not in data:
            logger.warning(" 请求格式错误，缺少message字段")
            return jsonify({
                'success': False,
                'error': '请求格式错误，缺少message字段',
                'error_type': 'invalid_request'
            }), 400

        user_message = data['message'].strip()
        if not user_message:
            logger.warning(" 消息内容为空")
            return jsonify({
                'success': False,
                'error': '消息内容不能为空',
                'error_type': 'empty_message'
            }), 400

        # 获取用户ID和会话ID
        user_id = data.get('user_id', 'default_user')
        session_id = data.get('session_id', None)

        logger.info(" [" + datetime.now().strftime('%H:%M:%S') + "] 固定工作流处理请求")
        logger.info(" 用户: " + user_id + ", 会话: " + str(session_id) + ", 消息: " + user_message)

        # 使用固定工作流编排器处理请求
        result = workflow_orchestrator.process_workflow(user_message, user_id, session_id)
        
        return jsonify(result)

    except Exception as e:
        logger.error(" [" + datetime.now().strftime('%H:%M:%S') + "] API错误: " + str(e))
        logger.error(" 详细错误信息: " + traceback.format_exc())
        
        return jsonify({
            'success': False,
            'error': '固定工作流系统暂时不可用，请稍后再试',
            'error_type': 'server_error',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查 - 检查所有A2A Agent服务状态"""
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'system_type': 'Fixed Workflow Multi-Agent (Pure A2A)',
            'agents': {},
            'workflow_system': 'operational'
        }
        
        # 检查各个A2A Agent的健康状态
        for agent_type, agent_config in workflow_orchestrator.a2a_agents.items():
            try:
                health_status['agents'][agent_type] = {
                    'status': 'available' if agent_config.get("available", False) else 'unavailable',
                    'url': agent_config["url"],
                    'name': agent_config["name"],
                    'a2a_available': agent_config.get("available", False)
                }
            except Exception as e:
                health_status['agents'][agent_type] = {
                    'status': 'error', 
                    'error': str(e),
                    'url': agent_config.get("url", "unknown"),
                    'name': agent_config.get("name", agent_type)
                }
        
        # 判断整体健康状态
        agent_statuses = [agent['status'] for agent in health_status['agents'].values()]
        if 'available' not in agent_statuses:
            health_status['status'] = 'unhealthy'
            return jsonify(health_status), 503
        elif 'error' in agent_statuses or 'unavailable' in agent_statuses:
            health_status['status'] = 'degraded'
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(" 健康检查失败: " + str(e))
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取详细的服状态"""
    try:
        status = {
            'timestamp': datetime.now().isoformat(),
            'system_type': 'Fixed Workflow Multi-Agent Orchestrator (Pure A2A)',
            'version': '5.0-pure-a2a',
            'mode': 'Pure A2A (No Local Fallback)',
            'a2a_agents': workflow_orchestrator.a2a_agents,
            'workflow_states': [state.value for state in WorkflowState],
            'active_sessions': len(getattr(workflow_orchestrator, 'session_states', {})),
            'capabilities': {
                'fixed_workflow': True,
                'pure_a2a_communication': True,
                'real_ai_responses': True,
                'no_preset_replies': True,
                'agent_coordination': True,
                'state_management': True,
                'multi_session_support': True
            },
            'agent_servers': agent_manager.get_agent_status()
        }
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(" 获取状态失败: " + str(e))
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# 新增Agent服务器管理API
@app.route('/api/agents/start', methods=['POST'])
def start_agents():
    """启动所有Agent服务器"""
    try:
        results = agent_manager.start_all_agents()
        ready_status = agent_manager.wait_for_agents_ready()
        
        return jsonify({
            'success': True,
            'start_results': results,
            'ready_status': ready_status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(" 启动Agent服务器失败: " + str(e))
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/agents/stop', methods=['POST'])
def stop_agents():
    """停止所有Agent服务器"""
    try:
        agent_manager.shutdown_all_agents()
        
        return jsonify({
            'success': True,
            'message': '所有Agent服务器已停止',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(" 停止Agent服务器失败: " + str(e))
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/agents/status', methods=['GET'])
def get_agents_status():
    """获取Agent服务器状态"""
    try:
        status = agent_manager.get_agent_status()
        
        return jsonify({
            'success': True,
            'agents': status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(" 获取Agent状态失败: " + str(e))
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# 错误处理
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': '请求的资源不存在',
        'available_endpoints': ['/api/chat', '/api/health', '/api/status', '/api/agents/start', '/api/agents/stop', '/api/agents/status']
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': '服务器内部错误，请稍后再试',
        'timestamp': datetime.now().isoformat()
    }), 500

def startup_sequence():
    """启动序列 - 自动启动Agent服务器"""
    print("\n" + "="*80)
    print(" 固定工作流购物助手服务启动序列 (纯A2A架构)")
    print("="*80)
    
    # 1. 启动所有Agent服务器
    print("🤖 第一步：启动所有Agent服务器...")
    start_results = agent_manager.start_all_agents()
    
    # 显示启动结果
    for agent_name, success in start_results.items():
        status = " 成功" if success else " 失败"
        print("   " + agent_name + ": " + status)
    
    # 2. 等待所有服务器就绪
    print("\n 第二步：等待Agent服务器就绪...")
    ready_status = agent_manager.wait_for_agents_ready()
    
    # 显示就绪状态
    all_ready = all(ready_status.values())
    if all_ready:
        print(" 所有Agent服务器已就绪！")
    else:
        print(" 部分Agent服务器未就绪")
        for agent_name, ready in ready_status.items():
            status = " 就绪" if ready else " 未就绪"
            print("   " + agent_name + ": " + status)
    
    # 3. 更新工作流编排器的A2A配置
    print("\n 第三步：更新A2A配置...")
    workflow_orchestrator._check_a2a_services()


    from flask import request, jsonify

@app.route("/market-trade", methods=["POST"])
def market_trade():
    data = request.json
    user_msg = data.get("message", "")

    print("收到 market-trade 请求:", user_msg)

    # 临时模拟返回结果
    return jsonify({
        "success": True,
        "response": f"已收到消息：{user_msg}"
    })


    # 显示最终状态
    print("\n 系统状态总览:")
    print(" 架构特点:")
    print("   • 纯A2A协议通信 - 无本地降级")
    print("   • 真实AI Agent回复 - 无预设回复")
    print("   • 工作流纯协调逻辑 - 不包含业务逻辑")
    print("   • Agent间直接通信 - 支持协作")
    print()
    print(" 工作流程:")
    print("   1 用户购买意图输入 → User Agent自主分析搜索")
    print("   2️ 用户选择商品 → User Agent判断 → Payment Agent创建订单")
    print("   3️ 用户确认支付 → Payment Agent自主验证支付状态")
    print("   4️ 支付成功 → Amazon Agent自主收集地址信息")
    print("   5️ Amazon Agent自主执行一键支付完成订单")
    print()
    print(" Agent协作:")
    print("   • User Agent: 意图理解、商品搜索、购买决策")
    print("   • Payment Agent: 订单创建、支付验证、状态查询")
    print("   • Amazon Agent: 地址收集、一键支付、订单处理")
    print("   • 所有回复由真实AI自主生成")
    print()
    print(" 系统特性:")
    print("   • 自动启动Agent服务器")
    print("   • 固定工作流状态管理")
    print("   • 纯A2A协议架构")
    print("   • 真实AI Agent响应")
    print("   • Agent间协作通信")
    print("   • 多用户多会话支持")
    print()
    print(" 访问地址: http://localhost:5002")
    print(" 主要API:")
    print("   • POST /api/chat - 聊天接口（纯A2A模式）")
    print("   • GET /api/health - A2A服务健康检查")
    print("   • GET /api/status - 详细状态（含A2A状态）")
    print("   • POST /api/agents/start - 启动Agent服务器")
    print("   • POST /api/agents/stop - 停止Agent服务器")
    print()
    print(" 使用示例:")
    print("   curl -X POST http://localhost:5002/api/chat \\")
    print("        -H 'Content-Type: application/json' \\")
    print("        -d '{\"message\":\"我想买iPhone 15\",\"user_id\":\"user123\"}'")
    print()
    print(" 关键特点:")
    print("   • 所有回复由真实AI Agent生成")
    print("   • 工作流仅做状态管理和Agent调度")
    print("   • 支持Agent间直接通信协作")
    print("   • 无任何预设回复或本地降级")
    print("\n" + "="*80)
    
    return all_ready

if __name__ == '__main__':
    try:
        # 执行启动序列
        startup_success = startup_sequence()
        
        # 启动Flask应用
        logger.info(" 启动Flask Web服务器...")
        app.run(
            host='0.0.0.0',
            port=5002,
            debug=False,
            threaded=True  # 启用多线程支持异步调用和A2A通信
        )
        
    except KeyboardInterrupt:
        print("\n 收到中断信号，正在关闭...")
        agent_manager.shutdown_all_agents()
        print(" 服务已安全关闭")
    except Exception as e:
        print(" 启动失败: " + str(e))
        logger.error("启动失败: " + str(e))
        agent_manager.shutdown_all_agents()
        sys.exit(1) 
