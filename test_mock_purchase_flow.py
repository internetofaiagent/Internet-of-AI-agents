#!/usr/bin/env python3
"""
测试模拟购买流程
1. 用户提出购买需求 → User Agent搜索商品 → 推荐给用户
2. 用户确认选择 → User Agent调用Mock Payment Agent → Mock Payment Agent调用Amazon Agent
3. 所有步骤都返回模拟成功消息
"""

import time
import sys
import os

sys.path.append('AgentCore/Society')

try:
    from python_a2a import A2AClient
    A2A_AVAILABLE = True
except ImportError:
    print("❌ python_a2a导入失败")
    A2A_AVAILABLE = False

def test_services_health():
    """测试所有服务健康状态"""
    print("🔍 检查所有服务健康状态")
    print("="*60)
    
    services = [
        ("Agent Registry", "http://localhost:5001"),
        ("Mock Payment Agent", "http://localhost:5005"),
        ("Amazon Agent", "http://localhost:5012"),
        ("User Agent", "http://localhost:5011")
    ]
    
    healthy_count = 0
    for name, url in services:
        try:
            client = A2AClient(url)
            response = client.ask("health check")
            if response and ("healthy" in response.lower() or "运行正常" in response or "operational" in response.lower()):
                print(f"   ✅ {name}: 运行正常")
                healthy_count += 1
            else:
                print(f"   ⚠️ {name}: 响应异常 - {response[:50] if response else 'None'}")
        except Exception as e:
            print(f"   ❌ {name}: 连接失败 - {e}")
    
    print(f"\n📊 服务状态: {healthy_count}/{len(services)} 服务正常")
    return healthy_count == len(services)

def test_step1_product_search():
    """步骤1: 测试商品搜索和推荐"""
    print("\n🔍 步骤1: 测试商品搜索和推荐")
    print("="*60)
    
    if not A2A_AVAILABLE:
        print("❌ A2A客户端不可用")
        return False
    
    try:
        client = A2AClient("http://localhost:5011")
        request = "我想买一个iPhone 15 Pro，预算1200美元"
        
        print(f"📝 发送搜索请求: {request}")
        
        start_time = time.time()
        response = client.ask(request)
        end_time = time.time()
        
        print(f"⏱️ 响应时间: {end_time - start_time:.2f}秒")
        print("📥 User Agent响应:")
        print("="*60)
        print(response if response else "无响应")
        print("="*60)
        
        # 检查是否是商品推荐
        if response:
            has_recommendation = "为您找到以下商品推荐" in response
            has_price = "$" in response and "USD" in response
            has_products = "**1." in response
            
            print(f"\n🔍 响应分析:")
            print(f"   {'✅' if has_recommendation else '❌'} 包含商品推荐: {'是' if has_recommendation else '否'}")
            print(f"   {'✅' if has_price else '❌'} 包含价格信息: {'是' if has_price else '否'}")
            print(f"   {'✅' if has_products else '❌'} 包含商品列表: {'是' if has_products else '否'}")
            
            if has_recommendation and has_price and has_products:
                print("🎉 步骤1测试成功！User Agent正确返回商品推荐")
                return True
            else:
                print("❌ 步骤1测试失败：响应格式不完整")
                return False
        else:
            print("❌ 步骤1测试失败：无响应")
            return False
            
    except Exception as e:
        print(f"❌ 步骤1测试异常: {e}")
        return False

def test_step2_mock_purchase():
    """步骤2: 测试模拟购买确认流程"""
    print("\n🛒 步骤2: 测试模拟购买确认流程")
    print("="*60)
    
    if not A2A_AVAILABLE:
        print("❌ A2A客户端不可用")
        return False
    
    try:
        client = A2AClient("http://localhost:5011")
        request = "确认购买 iPhone 15 Pro"
        
        print(f"📝 发送确认请求: {request}")
        
        start_time = time.time()
        response = client.ask(request)
        end_time = time.time()
        
        print(f"⏱️ 响应时间: {end_time - start_time:.2f}秒")
        print("📥 User Agent响应:")
        print("="*60)
        print(response if response else "无响应")
        print("="*60)
        
        # 检查模拟购买流程
        if response:
            has_payment_success = "支付宝支付成功" in response
            has_amazon_order = "Amazon订单确认成功" in response
            has_order_number = "订单号:" in response
            has_no_errors = "错误" not in response and "失败" not in response and "Error" not in response
            has_real_price = "$0.00" not in response  # 确保不是$0价格
            
            print(f"\n🔍 响应分析:")
            print(f"   {'✅' if has_payment_success else '❌'} 支付成功: {'检测到' if has_payment_success else '未检测到'}")
            print(f"   {'✅' if has_amazon_order else '❌'} Amazon订单确认: {'检测到' if has_amazon_order else '未检测到'}")
            print(f"   {'✅' if has_order_number else '❌'} 订单号生成: {'检测到' if has_order_number else '未检测到'}")
            print(f"   {'✅' if has_no_errors else '❌'} 无错误信息: {'是' if has_no_errors else '否'}")
            print(f"   {'✅' if has_real_price else '❌'} 真实价格: {'是' if has_real_price else '否（$0.00）'}")
            
            success_count = sum([has_payment_success, has_amazon_order, has_order_number, has_no_errors, has_real_price])
            
            if success_count >= 4:
                print("🎉 步骤2测试成功！模拟购买流程正常工作")
                return True
            else:
                print(f"⚠️ 步骤2测试部分成功 ({success_count}/5)，需要进一步检查")
                return False
        else:
            print("❌ 步骤2测试失败：无响应")
            return False
            
    except Exception as e:
        print(f"❌ 步骤2测试异常: {e}")
        return False

def test_direct_mock_payment():
    """直接测试Mock Payment Agent"""
    print("\n💳 直接测试Mock Payment Agent")
    print("="*60)
    
    try:
        client = A2AClient("http://localhost:5005")
        request = """用户确认购买商品，请创建支付订单：

商品信息：
- 名称: iPhone 15 Pro
- 单价: $999.00 USD
- 数量: 1
- 总价: $999.00 USD

请为此商品创建支付订单并通知Amazon Agent。"""
        
        print(f"📝 发送支付请求: {request[:100]}...")
        
        start_time = time.time()
        response = client.ask(request)
        end_time = time.time()
        
        print(f"⏱️ 响应时间: {end_time - start_time:.2f}秒")
        print("📥 Mock Payment Agent响应:")
        print("="*60)
        print(response if response else "无响应")
        print("="*60)
        
        if response:
            has_payment = "支付宝支付成功" in response
            has_amazon = "Amazon订单确认" in response
            has_order = "订单号:" in response
            
            print(f"\n🔍 响应分析:")
            print(f"   {'✅' if has_payment else '❌'} 模拟支付: {'成功' if has_payment else '失败'}")
            print(f"   {'✅' if has_amazon else '❌'} Amazon调用: {'成功' if has_amazon else '失败'}")
            print(f"   {'✅' if has_order else '❌'} 订单生成: {'成功' if has_order else '失败'}")
            
            return has_payment and has_amazon and has_order
        else:
            print("❌ 直接测试失败：无响应")
            return False
            
    except Exception as e:
        print(f"❌ 直接测试异常: {e}")
        return False

def main():
    """主测试函数"""
    print("🧪 测试模拟购买流程")
    print("="*80)
    print("新的模拟流程:")
    print("1. User Agent搜索商品 → 推荐给用户")
    print("2. User Agent调用Mock Payment Agent → 返回模拟支付成功")
    print("3. Mock Payment Agent调用Amazon Agent → 返回模拟下单成功")
    print("4. Amazon Agent发送发货通知给User Agent")
    print("="*80)
    
    # 检查服务状态
    if not test_services_health():
        print("\n❌ 部分服务未启动，请先启动所有必需的服务")
        print("\n💡 启动顺序:")
        print("1. python AgentCore/Society/agent_registry.py")
        print("2. python payment_mock.py  # 使用新的模拟支付服务")
        print("3. python \"AgentCore/Society/a2a amazon agent.py\"")
        print("4. python AgentCore/Society/user_agent_a2a.py")
        return
    
    # 执行测试
    step1_success = test_step1_product_search()
    step2_success = test_step2_mock_purchase()
    direct_payment_success = test_direct_mock_payment()
    
    # 总结结果
    print("\n" + "="*80)
    print("📊 测试结果总结")
    print("="*80)
    
    print(f"{'✅' if step1_success else '❌'} 步骤1 - 商品搜索和推荐: {'通过' if step1_success else '失败'}")
    print(f"{'✅' if step2_success else '❌'} 步骤2 - 模拟购买流程: {'通过' if step2_success else '失败'}")
    print(f"{'✅' if direct_payment_success else '❌'} 直接支付测试: {'通过' if direct_payment_success else '失败'}")
    
    total_success = sum([step1_success, step2_success, direct_payment_success])
    
    if total_success == 3:
        print("\n🎉 所有测试通过！模拟购买流程完全正常")
        print("✅ 系统已实现完整的模拟购买流程")
    elif total_success >= 2:
        print("\n⚠️ 大部分测试通过，系统基本正常")
    else:
        print("\n❌ 多个测试失败，需要检查系统配置")
    
    print(f"\n📊 成功率: {total_success}/3 ({total_success/3*100:.1f}%)")

if __name__ == "__main__":
    main()
