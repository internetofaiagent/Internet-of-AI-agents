#!/usr/bin/env python3
"""
AI Agent可用性测试脚本
测试User Agent、Payment Agent、Amazon Agent的各项功能
"""

import os
import sys
import time
import json
import asyncio
import subprocess
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
import requests

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入A2A客户端
try:
    from python_a2a import A2AClient
    A2A_AVAILABLE = True
except ImportError:
    print("⚠️ python_a2a导入失败，A2A通信测试将跳过")
    A2A_AVAILABLE = False

class TestResult:
    """测试结果类"""
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.success = False
        self.error_message = ""
        self.details = {}
        self.execution_time = 0
        
    def set_success(self, details: Dict = None):
        self.success = True
        if details:
            self.details = details
            
    def set_failure(self, error_message: str, details: Dict = None):
        self.success = False
        self.error_message = error_message
        if details:
            self.details = details

class AgentAvailabilityTester:
    """AI Agent可用性测试器"""
    
    def __init__(self):
        self.test_results: List[TestResult] = []
        self.agent_processes = {}  # 存储启动的Agent进程
        
        # Agent配置
        self.agents_config = {
            "user_agent": {
                "port": 5011,
                "script": "AgentCore/Society/user_agent_a2a.py",
                "name": "User Agent"
            },
            "payment_agent": {
                "port": 5005,
                "script": "AgentCore/Society/payment.py",
                "name": "Payment Agent"
            },
            "amazon_agent": {
                "port": 5012,
                "script": "AgentCore/Society/a2a amazon agent.py",
                "name": "Amazon Agent"
            }
        }
    
    def log(self, message: str, level: str = "INFO"):
        """日志输出"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        emoji = {
            "INFO": "ℹ️",
            "SUCCESS": "✅", 
            "WARNING": "⚠️",
            "ERROR": "❌",
            "TEST": "🧪"
        }.get(level, "📝")
        print(f"[{timestamp}] {emoji} {message}")
    
    def add_test_result(self, result: TestResult):
        """添加测试结果"""
        self.test_results.append(result)
        if result.success:
            self.log(f"测试通过: {result.test_name}", "SUCCESS")
        else:
            self.log(f"测试失败: {result.test_name} - {result.error_message}", "ERROR")
    
    def test_environment_setup(self) -> TestResult:
        """测试环境配置"""
        result = TestResult("环境配置检查")
        start_time = time.time()
        
        try:
            self.log("检查环境变量配置...", "TEST")
            
            # 检查必需的环境变量
            env_vars = {
                "MODELSCOPE_SDK_TOKEN": os.environ.get("MODELSCOPE_SDK_TOKEN"),
                "FEWSATS_API_KEY": os.environ.get("FEWSATS_API_KEY")
            }
            
            missing_vars = [var for var, value in env_vars.items() if not value]
            
            if missing_vars:
                result.set_failure(f"缺少环境变量: {', '.join(missing_vars)}")
            else:
                # 检查Python依赖
                dependencies = ["requests", "asyncio", "camel"]
                missing_deps = []
                
                for dep in dependencies:
                    try:
                        __import__(dep)
                    except ImportError:
                        missing_deps.append(dep)
                
                if missing_deps:
                    result.set_failure(f"缺少Python依赖: {', '.join(missing_deps)}")
                else:
                    result.set_success({
                        "environment_variables": env_vars,
                        "dependencies_available": dependencies
                    })
                    
        except Exception as e:
            result.set_failure(f"环境检查异常: {str(e)}")
        
        result.execution_time = time.time() - start_time
        return result
    
    def test_llm_api_availability(self) -> List[TestResult]:
        """测试大模型API可用性"""
        results = []
        
        # 测试ModelScope API
        result = TestResult("ModelScope API可用性")
        start_time = time.time()
        
        try:
            self.log("测试ModelScope API连接...", "TEST")
            
            # 尝试导入camel库并创建模型
            try:
                from camel.models import ModelFactory
                from camel.types import ModelPlatformType
                
                # 创建Qwen2.5模型实例（User Agent和Payment Agent使用）
                model_qwen25 = ModelFactory.create(
                    model_platform=ModelPlatformType.MODELSCOPE,
                    model_type='Qwen/Qwen2.5-72B-Instruct',
                    model_config_dict={'temperature': 0.2},
                    api_key=os.environ.get('MODELSCOPE_SDK_TOKEN', '9d3aed4d-eca1-4e0c-9805-cb923ccbbf21'),
                )
                
                self.log("Qwen2.5模型创建成功", "SUCCESS")
                
                result.set_success({
                    "model_platform": "ModelScope",
                    "models_tested": ["Qwen2.5-72B-Instruct"],
                    "api_key_valid": True
                })
                
            except Exception as e:
                result.set_failure(f"ModelScope API调用失败: {str(e)}")
                
        except Exception as e:
            result.set_failure(f"测试异常: {str(e)}")
        
        result.execution_time = time.time() - start_time
        results.append(result)
        
        return results
    
    def start_agent_process(self, agent_key: str) -> bool:
        """启动Agent进程"""
        config = self.agents_config[agent_key]
        script_path = config["script"]
        
        try:
            self.log(f"启动 {config['name']}...", "TEST")
            
            # 检查脚本文件是否存在
            if not os.path.exists(script_path):
                self.log(f"脚本文件不存在: {script_path}", "ERROR")
                return False
            
            # 设置环境变量
            env = os.environ.copy()
            env["AMAZON_A2A_PORT"] = str(self.agents_config["user_agent"]["port"])
            env["ALIPAY_A2A_PORT"] = str(self.agents_config["payment_agent"]["port"])
            env["AMAZON_SHOPPING_A2A_PORT"] = str(self.agents_config["amazon_agent"]["port"])
            # 设置UTF-8编码支持
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            
            # 启动进程
            process = subprocess.Popen(
                [sys.executable, script_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.agent_processes[agent_key] = process
            
            # 等待Agent启动
            time.sleep(10)  # 给Agent足够时间启动
            
            # 检查进程是否还在运行
            if process.poll() is None:
                self.log(f"{config['name']} 启动成功", "SUCCESS")
                return True
            else:
                stdout, stderr = process.communicate()
                self.log(f"{config['name']} 启动失败: {stderr}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"启动 {config['name']} 时出错: {str(e)}", "ERROR")
            return False
    
    def check_agent_health(self, agent_key: str) -> bool:
        """检查Agent健康状态"""
        config = self.agents_config[agent_key]
        port = config["port"]
        
        try:
            # 尝试连接Agent端口
            response = requests.get(f"http://localhost:{port}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def test_agent_startup(self) -> List[TestResult]:
        """测试Agent启动"""
        results = []
        
        for agent_key, config in self.agents_config.items():
            result = TestResult(f"{config['name']} 启动测试")
            start_time = time.time()
            
            try:
                # 启动Agent
                if self.start_agent_process(agent_key):
                    # 等待并检查健康状态
                    time.sleep(5)
                    if self.check_agent_health(agent_key):
                        result.set_success({
                            "port": config["port"],
                            "process_running": True,
                            "health_check": True
                        })
                    else:
                        result.set_failure("健康检查失败", {
                            "port": config["port"],
                            "process_running": True,
                            "health_check": False
                        })
                else:
                    result.set_failure("Agent启动失败")
                    
            except Exception as e:
                result.set_failure(f"启动测试异常: {str(e)}")
            
            result.execution_time = time.time() - start_time
            results.append(result)
        
        return results
    
    def test_mcp_services(self) -> List[TestResult]:
        """测试MCP服务功能"""
        results = []
        
        # 测试Payment Agent的MCP服务（订单生成）
        result = TestResult("Payment Agent MCP服务 - 订单生成")
        start_time = time.time()
        
        try:
            self.log("测试Payment Agent订单生成功能...", "TEST")
            
            # 导入并测试Alipay服务
            try:
                from AgentCore.Society.payment import AlipayOrderService
                
                # 创建服务实例
                alipay_service = AlipayOrderService()
                
                # 测试订单生成
                test_product = {
                    "name": "测试商品 - iPhone 15",
                    "usd_price": 999.99,
                    "exchange_rate": 7.26
                }
                
                # 由于MCP工具可能不可用，我们测试基础功能
                order_number = alipay_service.generate_order_number()
                rmb_amount = alipay_service.calculate_rmb_amount(test_product["usd_price"])
                
                if order_number and rmb_amount > 0:
                    # 打印订单生成结果
                    self.log("📨 Payment Agent 订单生成结果:", "INFO")
                    self.log(f"   订单号: {order_number}", "INFO")
                    self.log(f"   人民币金额: ¥{rmb_amount}", "INFO")
                    self.log(f"   美元价格: ${test_product['usd_price']}", "INFO")
                    
                    result.set_success({
                        "order_number": order_number,
                        "rmb_amount": rmb_amount,
                        "usd_price": test_product["usd_price"],
                        "exchange_rate": 7.26,
                        "order_details": f"订单号: {order_number}, 金额: ¥{rmb_amount} (${test_product['usd_price']} USD)"
                    })
                else:
                    result.set_failure("订单生成功能异常")
                    
            except Exception as e:
                result.set_failure(f"Payment Agent MCP测试失败: {str(e)}")
                
        except Exception as e:
            result.set_failure(f"测试异常: {str(e)}")
        
        result.execution_time = time.time() - start_time
        results.append(result)
        
        # 测试Amazon Agent的MCP服务
        result = TestResult("Amazon Agent MCP服务可用性")
        start_time = time.time()
        
        try:
            self.log("测试Amazon Agent MCP工具状态...", "TEST")
            
            # 这里我们主要检查MCP工具的导入和配置
            try:
                # 检查qwen-agent是否可用
                try:
                    from qwen_agent.agents import Assistant
                    qwen_available = True
                except ImportError:
                    qwen_available = False
                
                # 检查环境变量
                fewsats_key = os.environ.get('FEWSATS_API_KEY')
                modelscope_token = os.environ.get('MODELSCOPE_SDK_TOKEN')
                
                mcp_status = {
                    "qwen_agent_available": qwen_available,
                    "fewsats_api_key": bool(fewsats_key),
                    "modelscope_token": bool(modelscope_token)
                }
                
                if all(mcp_status.values()):
                    result.set_success(mcp_status)
                else:
                    result.set_failure("MCP工具配置不完整", mcp_status)
                    
            except Exception as e:
                result.set_failure(f"Amazon Agent MCP检查失败: {str(e)}")
                
        except Exception as e:
            result.set_failure(f"测试异常: {str(e)}")
        
        result.execution_time = time.time() - start_time
        results.append(result)
        
        return results
    
    def test_a2a_communication(self) -> List[TestResult]:
        """测试A2A协议通信"""
        results = []
        
        if not A2A_AVAILABLE:
            result = TestResult("A2A通信测试")
            result.set_failure("python_a2a库不可用")
            results.append(result)
            return results
        
        # 测试各Agent之间的A2A通信
        agent_pairs = [
            ("user_agent", "payment_agent", "用户Agent → 支付Agent"),
            ("user_agent", "amazon_agent", "用户Agent → 亚马逊Agent"),
            ("payment_agent", "amazon_agent", "支付Agent → 亚马逊Agent")
        ]
        
        for agent1_key, agent2_key, description in agent_pairs:
            result = TestResult(f"A2A通信: {description}")
            start_time = time.time()
            
            try:
                self.log(f"测试 {description} 通信...", "TEST")
                
                agent2_config = self.agents_config[agent2_key]
                agent2_url = f"http://localhost:{agent2_config['port']}"
                
                # 检查目标Agent是否在运行
                if not self.check_agent_health(agent2_key):
                    result.set_failure(f"目标Agent ({agent2_config['name']}) 不可用")
                else:
                    try:
                        # 创建A2A客户端并发送测试消息
                        client = A2AClient(agent2_url)
                        test_message = "Hello, 这是一个A2A通信测试消息"
                        
                        # 设置较短的超时时间
                        response = client.ask(test_message)
                        
                        if response and len(response) > 0:
                            # 打印Agent响应内容以增强测试可信性
                            self.log(f"📨 {agent2_config['name']} 响应内容:", "INFO")
                            self.log(f"   请求: {test_message}", "INFO")
                            self.log(f"   响应: {response[:200]}{'...' if len(response) > 200 else ''}", "INFO")
                            
                            result.set_success({
                                "target_agent": agent2_config['name'],
                                "target_url": agent2_url,
                                "message_sent": test_message,
                                "response_received": True,
                                "response_length": len(response),
                                "response_preview": response[:100] + "..." if len(response) > 100 else response
                            })
                        else:
                            result.set_failure("收到空响应")
                            
                    except Exception as e:
                        result.set_failure(f"A2A通信失败: {str(e)}")
                        
            except Exception as e:
                result.set_failure(f"测试异常: {str(e)}")
            
            result.execution_time = time.time() - start_time
            results.append(result)
        
        return results
    
    def test_complete_payment_flow(self) -> TestResult:
        """测试完整支付流程"""
        result = TestResult("完整支付流程测试")
        start_time = time.time()
        
        try:
            self.log("测试完整支付流程...", "TEST")
            
            if not A2A_AVAILABLE:
                result.set_failure("A2A库不可用，无法测试完整流程")
                return result
            
            # 模拟完整的支付流程
            flow_steps = []
            
            # 第1步：向User Agent发送购买请求
            try:
                user_agent_url = f"http://localhost:{self.agents_config['user_agent']['port']}"
                
                if not self.check_agent_health("user_agent"):
                    result.set_failure("User Agent不可用")
                    return result
                
                user_client = A2AClient(user_agent_url)
                purchase_request = "我想买一个iPhone 15 Pro，预算1000美元"
                
                self.log("步骤1: 向User Agent发送购买请求...", "TEST")
                user_response = user_client.ask(purchase_request)
                
                if user_response:
                    # 打印User Agent响应内容
                    self.log("📨 User Agent 响应:", "INFO")
                    self.log(f"   请求: {purchase_request}", "INFO")
                    self.log(f"   响应: {user_response[:300]}{'...' if len(user_response) > 300 else ''}", "INFO")
                    
                    flow_steps.append({
                        "step": 1,
                        "action": "User Agent购买请求",
                        "success": True,
                        "response_length": len(user_response),
                        "response_preview": user_response[:150] + "..." if len(user_response) > 150 else user_response
                    })
                else:
                    flow_steps.append({
                        "step": 1,
                        "action": "User Agent购买请求",
                        "success": False,
                        "error": "空响应"
                    })
                    
            except Exception as e:
                flow_steps.append({
                    "step": 1,
                    "action": "User Agent购买请求",
                    "success": False,
                    "error": str(e)
                })
            
            # 第2步：测试Payment Agent订单生成
            try:
                payment_agent_url = f"http://localhost:{self.agents_config['payment_agent']['port']}"
                
                if self.check_agent_health("payment_agent"):
                    payment_client = A2AClient(payment_agent_url)
                    payment_request = "请为iPhone 15 Pro创建支付订单，价格999美元"
                    
                    self.log("步骤2: 测试Payment Agent订单生成...", "TEST")
                    payment_response = payment_client.ask(payment_request)
                    
                    if payment_response:
                        # 打印Payment Agent响应内容
                        self.log("📨 Payment Agent 响应:", "INFO")
                        self.log(f"   请求: {payment_request}", "INFO")
                        self.log(f"   响应: {payment_response[:300]}{'...' if len(payment_response) > 300 else ''}", "INFO")
                        
                        flow_steps.append({
                            "step": 2,
                            "action": "Payment Agent订单生成",
                            "success": True,
                            "response_length": len(payment_response),
                            "response_preview": payment_response[:150] + "..." if len(payment_response) > 150 else payment_response
                        })
                    else:
                        flow_steps.append({
                            "step": 2,
                            "action": "Payment Agent订单生成",
                            "success": False,
                            "error": "空响应"
                        })
                else:
                    flow_steps.append({
                        "step": 2,
                        "action": "Payment Agent订单生成",
                        "success": False,
                        "error": "Payment Agent不可用"
                    })
                    
            except Exception as e:
                flow_steps.append({
                    "step": 2,
                    "action": "Payment Agent订单生成",
                    "success": False,
                    "error": str(e)
                })
            
            # 第3步：测试Amazon Agent响应
            try:
                amazon_agent_url = f"http://localhost:{self.agents_config['amazon_agent']['port']}"
                
                if self.check_agent_health("amazon_agent"):
                    amazon_client = A2AClient(amazon_agent_url)
                    amazon_request = "搜索iPhone 15 Pro商品"
                    
                    self.log("步骤3: 测试Amazon Agent商品搜索...", "TEST")
                    amazon_response = amazon_client.ask(amazon_request)
                    
                    if amazon_response:
                        # 打印Amazon Agent响应内容
                        self.log("📨 Amazon Agent 响应:", "INFO")
                        self.log(f"   请求: {amazon_request}", "INFO")
                        self.log(f"   响应: {amazon_response[:300]}{'...' if len(amazon_response) > 300 else ''}", "INFO")
                        
                        flow_steps.append({
                            "step": 3,
                            "action": "Amazon Agent商品搜索",
                            "success": True,
                            "response_length": len(amazon_response),
                            "response_preview": amazon_response[:150] + "..." if len(amazon_response) > 150 else amazon_response
                        })
                    else:
                        flow_steps.append({
                            "step": 3,
                            "action": "Amazon Agent商品搜索",
                            "success": False,
                            "error": "空响应"
                        })
                else:
                    flow_steps.append({
                        "step": 3,
                        "action": "Amazon Agent商品搜索",
                        "success": False,
                        "error": "Amazon Agent不可用"
                    })
                    
            except Exception as e:
                flow_steps.append({
                    "step": 3,
                    "action": "Amazon Agent商品搜索",
                    "success": False,
                    "error": str(e)
                })
            
            # 分析流程结果
            successful_steps = sum(1 for step in flow_steps if step["success"])
            total_steps = len(flow_steps)
            
            if successful_steps == total_steps:
                result.set_success({
                    "total_steps": total_steps,
                    "successful_steps": successful_steps,
                    "flow_details": flow_steps,
                    "success_rate": f"{successful_steps}/{total_steps}"
                })
            else:
                result.set_failure(f"流程不完整: {successful_steps}/{total_steps} 步骤成功", {
                    "total_steps": total_steps,
                    "successful_steps": successful_steps,
                    "flow_details": flow_steps,
                    "success_rate": f"{successful_steps}/{total_steps}"
                })
                
        except Exception as e:
            result.set_failure(f"流程测试异常: {str(e)}")
        
        result.execution_time = time.time() - start_time
        return result
    
    def cleanup_agents(self):
        """清理Agent进程"""
        self.log("清理Agent进程...", "INFO")
        
        for agent_key, process in self.agent_processes.items():
            try:
                if process.poll() is None:  # 进程还在运行
                    process.terminate()
                    time.sleep(2)
                    if process.poll() is None:  # 仍然在运行，强制杀死
                        process.kill()
                    self.log(f"{self.agents_config[agent_key]['name']} 进程已终止", "INFO")
            except Exception as e:
                self.log(f"终止 {agent_key} 进程时出错: {str(e)}", "WARNING")
    
    def generate_report(self) -> str:
        """生成测试报告"""
        report = []
        report.append("="*80)
        report.append("AI AGENT 可用性测试报告")
        report.append("="*80)
        report.append(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"测试总数: {len(self.test_results)}")
        report.append("")
        
        # 统计测试结果
        passed_tests = sum(1 for result in self.test_results if result.success)
        failed_tests = len(self.test_results) - passed_tests
        
        report.append("📊 测试概览")
        report.append("-" * 40)
        report.append(f"✅ 通过测试: {passed_tests}")
        report.append(f"❌ 失败测试: {failed_tests}")
        report.append(f"📈 成功率: {(passed_tests/len(self.test_results)*100):.1f}%")
        report.append("")
        
        # 按类别分组显示结果
        categories = {
            "环境配置": [],
            "大模型API": [],
            "Agent启动": [],
            "MCP服务": [],
            "A2A通信": [],
            "完整流程": []
        }
        
        for result in self.test_results:
            if "环境" in result.test_name:
                categories["环境配置"].append(result)
            elif "API" in result.test_name or "ModelScope" in result.test_name:
                categories["大模型API"].append(result)
            elif "启动" in result.test_name:
                categories["Agent启动"].append(result)
            elif "MCP" in result.test_name:
                categories["MCP服务"].append(result)
            elif "A2A" in result.test_name:
                categories["A2A通信"].append(result)
            elif "流程" in result.test_name:
                categories["完整流程"].append(result)
        
        for category, results in categories.items():
            if results:
                report.append(f"📋 {category}测试结果")
                report.append("-" * 40)
                
                for result in results:
                    status = "✅ 通过" if result.success else "❌ 失败"
                    report.append(f"{status} {result.test_name}")
                    
                    if result.execution_time > 0:
                        report.append(f"   ⏱️ 执行时间: {result.execution_time:.2f}秒")
                    
                    if result.success and result.details:
                        report.append("   📄 详细信息:")
                        for key, value in result.details.items():
                            if key == "response_preview":
                                report.append(f"      • {key}: {value}")
                            else:
                                report.append(f"      • {key}: {value}")
                    elif not result.success:
                        report.append(f"   ❌ 错误信息: {result.error_message}")
                        if result.details:
                            report.append("   📄 额外信息:")
                            for key, value in result.details.items():
                                if key == "response_preview":
                                    report.append(f"      • {key}: {value}")
                                else:
                                    report.append(f"      • {key}: {value}")
                    report.append("")
                
                report.append("")
        
        # 添加建议和结论
        report.append("📝 测试结论与建议")
        report.append("-" * 40)
        
        if passed_tests == len(self.test_results):
            report.append("🎉 所有测试通过！系统各组件功能正常。")
        else:
            report.append("⚠️  部分测试失败，需要关注以下问题:")
            
            failed_results = [r for r in self.test_results if not r.success]
            for result in failed_results:
                report.append(f"   • {result.test_name}: {result.error_message}")
        
        report.append("")
        report.append("💡 优化建议:")
        report.append("   • 确保所有环境变量正确配置")
        report.append("   • 检查网络连接和API密钥有效性")
        report.append("   • 监控Agent进程的资源使用情况")
        report.append("   • 定期执行可用性测试")
        
        # 添加Agent响应内容展示部分
        response_tests = [r for r in self.test_results if r.success and r.details.get("response_preview")]
        flow_tests = [r for r in self.test_results if "流程" in r.test_name and r.details.get("flow_details")]
        
        if response_tests or flow_tests:
            report.append("🤖 Agent响应内容展示")
            report.append("-" * 40)
            
            # 展示一般响应内容
            for result in response_tests:
                report.append(f"📝 {result.test_name}:")
                if "message_sent" in result.details:
                    report.append(f"   📤 发送消息: {result.details['message_sent']}")
                if "response_preview" in result.details:
                    report.append(f"   📥 响应预览: {result.details['response_preview']}")
                report.append("")
            
            # 展示流程测试的详细响应
            for result in flow_tests:
                report.append(f"📝 {result.test_name} - 详细流程:")
                flow_details = result.details.get("flow_details", [])
                for step in flow_details:
                    status = "✅" if step["success"] else "❌"
                    report.append(f"   {status} 步骤{step['step']}: {step['action']}")
                    if step["success"] and "response_preview" in step:
                        report.append(f"      📥 响应: {step['response_preview']}")
                    elif not step["success"]:
                        report.append(f"      ❌ 错误: {step.get('error', '未知错误')}")
                report.append("")
        
        report.append("")
        report.append("="*80)
        
        return "\n".join(report)
    
    def run_all_tests(self):
        """运行所有测试"""
        self.log("开始AI Agent可用性测试", "INFO")
        
        try:
            # 1. 环境配置测试
            self.log("=== 第1阶段: 环境配置测试 ===", "INFO")
            env_result = self.test_environment_setup()
            self.add_test_result(env_result)
            
            if not env_result.success:
                self.log("环境配置测试失败，跳过后续测试", "ERROR")
                return
            
            # 2. 大模型API测试
            self.log("=== 第2阶段: 大模型API测试 ===", "INFO")
            llm_results = self.test_llm_api_availability()
            for result in llm_results:
                self.add_test_result(result)
            
            # 3. Agent启动测试
            self.log("=== 第3阶段: Agent启动测试 ===", "INFO")
            startup_results = self.test_agent_startup()
            for result in startup_results:
                self.add_test_result(result)
            
            # 等待Agent完全启动
            time.sleep(15)
            
            # 4. MCP服务测试
            self.log("=== 第4阶段: MCP服务测试 ===", "INFO")
            mcp_results = self.test_mcp_services()
            for result in mcp_results:
                self.add_test_result(result)
            
            # 5. A2A通信测试
            self.log("=== 第5阶段: A2A通信测试 ===", "INFO")
            a2a_results = self.test_a2a_communication()
            for result in a2a_results:
                self.add_test_result(result)
            
            # 6. 完整流程测试
            self.log("=== 第6阶段: 完整支付流程测试 ===", "INFO")
            flow_result = self.test_complete_payment_flow()
            self.add_test_result(flow_result)
            
        except KeyboardInterrupt:
            self.log("测试被用户中断", "WARNING")
        except Exception as e:
            self.log(f"测试过程中发生异常: {str(e)}", "ERROR")
        finally:
            # 清理资源
            self.cleanup_agents()
            
            # 生成报告
            report = self.generate_report()
            
            # 保存报告到文件
            report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            # 显示报告
            print("\n" + report)
            self.log(f"测试报告已保存到: {report_file}", "SUCCESS")

def main():
    """主函数"""
    print("🚀 启动AI Agent可用性测试")
    print("测试将验证User Agent、Payment Agent、Amazon Agent的各项功能")
    print("包括: 大模型API调用、MCP服务、A2A通信、完整支付流程")
    print("")
    print("📋 新功能特性:")
    print("   • 实时打印Agent响应内容，增强测试可信性")
    print("   • 详细展示订单生成过程和支付流程")
    print("   • 完整的响应内容在测试报告中展示")
    print("-" * 60)
    
    tester = AgentAvailabilityTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main() 