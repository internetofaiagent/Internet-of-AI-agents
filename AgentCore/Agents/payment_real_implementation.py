#!/usr/bin/env python3
"""
真实支付宝API集成实现方案
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

class RealAlipayService:
    """真实支付宝服务实现"""
    
    def __init__(self):
        # 从环境变量或配置文件读取API配置
        self.app_id = os.getenv('ALIPAY_APP_ID', '')
        self.private_key_path = os.getenv('ALIPAY_PRIVATE_KEY_PATH', '')
        self.alipay_public_key_path = os.getenv('ALIPAY_PUBLIC_KEY_PATH', '')
        self.gateway = os.getenv('ALIPAY_GATEWAY', 'https://openapi.alipay.com/gateway.do')
        self.is_sandbox = os.getenv('ALIPAY_SANDBOX', 'false').lower() == 'true'
        
        # 初始化支付宝SDK
        self._init_alipay_client()
    
    def _init_alipay_client(self):
        """初始化支付宝客户端"""
        try:
            from alipay import AliPay
            
            # 读取私钥
            with open(self.private_key_path, 'r') as f:
                app_private_key = f.read()
            
            # 读取支付宝公钥
            with open(self.alipay_public_key_path, 'r') as f:
                alipay_public_key = f.read()
            
            self.alipay_client = AliPay(
                appid=self.app_id,
                app_notify_url=None,  # 默认回调url
                app_private_key_string=app_private_key,
                alipay_public_key_string=alipay_public_key,
                sign_type="RSA2",
                debug=self.is_sandbox  # 沙箱模式
            )
            
            print("✅ 支付宝客户端初始化成功")
            
        except Exception as e:
            print(f"❌ 支付宝客户端初始化失败: {e}")
            self.alipay_client = None
    
    async def create_payment_order(self, product_info: Dict[str, Any]) -> Dict[str, Any]:
        """创建真实支付订单"""
        if not self.alipay_client:
            return {
                "success": False,
                "error": "支付宝客户端未初始化"
            }
        
        try:
            # 生成订单号
            order_number = f"ORDER_{datetime.now().strftime('%Y%m%d%H%M%S')}{os.getpid()}"
            
            # 计算金额（美元转人民币）
            usd_amount = product_info.get('usd_price', 999.00)
            exchange_rate = await self._get_exchange_rate()
            rmb_amount = round(usd_amount * exchange_rate, 2)
            
            # 构建支付订单参数
            order_data = {
                "out_trade_no": order_number,
                "total_amount": str(rmb_amount),
                "subject": product_info.get('name', 'Amazon商品购买'),
                "body": f"购买商品: {product_info.get('name', 'Unknown')}",
                "product_code": "FAST_INSTANT_TRADE_PAY",
                "timeout_express": "30m"  # 30分钟超时
            }
            
            # 创建支付链接
            if self.is_sandbox:
                # 沙箱环境：创建网页支付
                pay_url = self.alipay_client.api_alipay_trade_page_pay(
                    **order_data,
                    return_url="http://localhost:5005/alipay/return",
                    notify_url="http://localhost:5005/alipay/notify"
                )
                payment_url = f"{self.gateway}?{pay_url}"
            else:
                # 生产环境：创建APP支付或网页支付
                pay_url = self.alipay_client.api_alipay_trade_page_pay(**order_data)
                payment_url = f"{self.gateway}?{pay_url}"
            
            return {
                "success": True,
                "order_number": order_number,
                "payment_url": payment_url,
                "amount_usd": usd_amount,
                "amount_rmb": rmb_amount,
                "exchange_rate": exchange_rate,
                "expires_at": datetime.now().timestamp() + 1800  # 30分钟后过期
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"创建支付订单失败: {str(e)}"
            }
    
    async def query_payment_status(self, order_number: str) -> Dict[str, Any]:
        """查询支付状态"""
        if not self.alipay_client:
            return {
                "success": False,
                "error": "支付宝客户端未初始化"
            }
        
        try:
            # 查询订单状态
            result = self.alipay_client.api_alipay_trade_query(out_trade_no=order_number)
            
            if result.get("code") == "10000":
                trade_status = result.get("trade_status")
                
                return {
                    "success": True,
                    "order_number": order_number,
                    "trade_status": trade_status,
                    "trade_no": result.get("trade_no"),
                    "total_amount": result.get("total_amount"),
                    "paid_amount": result.get("receipt_amount"),
                    "payment_time": result.get("send_pay_date"),
                    "is_paid": trade_status in ["TRADE_SUCCESS", "TRADE_FINISHED"]
                }
            else:
                return {
                    "success": False,
                    "error": f"查询失败: {result.get('msg', '未知错误')}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"查询支付状态失败: {str(e)}"
            }
    
    async def _get_exchange_rate(self) -> float:
        """获取美元到人民币汇率"""
        try:
            # 这里可以调用真实的汇率API
            # 例如：https://api.exchangerate-api.com/v4/latest/USD
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.exchangerate-api.com/v4/latest/USD') as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['rates'].get('CNY', 7.26)
                    else:
                        return 7.26  # 默认汇率
                        
        except Exception as e:
            print(f"⚠️ 获取汇率失败，使用默认汇率: {e}")
            return 7.26  # 默认汇率

class PaymentModeManager:
    """支付模式管理器"""
    
    def __init__(self):
        self.mode = os.getenv('PAYMENT_MODE', 'mock').lower()  # mock 或 real
        
        if self.mode == 'real':
            self.service = RealAlipayService()
        else:
            from payment import AlipayOrderService  # 导入模拟服务
            self.service = AlipayOrderService()
    
    async def create_payment(self, product_info: Dict[str, Any]) -> Dict[str, Any]:
        """创建支付订单（根据模式选择实现）"""
        if self.mode == 'real':
            return await self.service.create_payment_order(product_info)
        else:
            # 使用模拟服务
            return await self.service.run_alipay_query("模拟支付请求", product_info)
    
    async def query_payment(self, order_number: str) -> Dict[str, Any]:
        """查询支付状态（根据模式选择实现）"""
        if self.mode == 'real':
            return await self.service.query_payment_status(order_number)
        else:
            # 模拟查询结果
            return {
                "success": True,
                "order_number": order_number,
                "trade_status": "TRADE_SUCCESS",
                "is_paid": True
            }

# 配置文件示例
PAYMENT_CONFIG_TEMPLATE = """
# 支付配置文件 (.env)

# 支付模式：mock（模拟）或 real（真实）
PAYMENT_MODE=mock

# 支付宝配置（仅在 PAYMENT_MODE=real 时需要）
ALIPAY_APP_ID=your_app_id_here
ALIPAY_PRIVATE_KEY_PATH=./keys/app_private_key.pem
ALIPAY_PUBLIC_KEY_PATH=./keys/alipay_public_key.pem
ALIPAY_GATEWAY=https://openapi.alipay.com/gateway.do
ALIPAY_SANDBOX=true

# Amazon配置
AMAZON_MODE=mock
AMAZON_SP_API_REFRESH_TOKEN=your_refresh_token
AMAZON_SP_API_CLIENT_ID=your_client_id
AMAZON_SP_API_CLIENT_SECRET=your_client_secret
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
"""

if __name__ == "__main__":
    # 示例用法
    async def test_payment():
        manager = PaymentModeManager()
        
        product_info = {
            "name": "iPhone 15 Pro",
            "usd_price": 999.00,
            "quantity": 1
        }
        
        # 创建支付
        result = await manager.create_payment(product_info)
        print(f"支付创建结果: {result}")
        
        if result.get("success"):
            order_number = result.get("order_number")
            
            # 查询支付状态
            status = await manager.query_payment(order_number)
            print(f"支付状态: {status}")
    
    asyncio.run(test_payment())
