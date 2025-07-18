#!/usr/bin/env python3
"""
配置管理系统 - 支持模拟模式和真实模式切换
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class OperationMode(Enum):
    """操作模式枚举"""
    MOCK = "mock"
    REAL = "real"
    HYBRID = "hybrid"  # 混合模式：部分真实，部分模拟

@dataclass
class PaymentConfig:
    """支付配置"""
    mode: OperationMode
    alipay_app_id: str = ""
    alipay_private_key_path: str = ""
    alipay_public_key_path: str = ""
    alipay_gateway: str = "https://openapi.alipay.com/gateway.do"
    alipay_sandbox: bool = True
    
    # 其他支付方式配置
    wechat_pay_enabled: bool = False
    stripe_enabled: bool = False

@dataclass
class AmazonConfig:
    """Amazon配置"""
    mode: OperationMode
    
    # SP-API配置
    sp_api_refresh_token: str = ""
    sp_api_client_id: str = ""
    sp_api_client_secret: str = ""
    marketplace_id: str = "ATVPDKIKX0DER"
    region: str = "us-east-1"
    
    # AWS配置
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_role_arn: str = ""
    
    # RapidAPI配置（用于商品搜索）
    rapidapi_key: str = ""
    rapidapi_host: str = "real-time-amazon-data.p.rapidapi.com"
    
    # 其他配置
    sandbox: bool = True
    max_retry_attempts: int = 3
    request_timeout: int = 30

@dataclass
class SystemConfig:
    """系统配置"""
    environment: str = "development"  # development, staging, production
    log_level: str = "INFO"
    enable_metrics: bool = False
    enable_tracing: bool = False
    
    # 服务端口配置
    user_agent_port: int = 5011
    payment_agent_port: int = 5005
    amazon_agent_port: int = 5012
    registry_port: int = 5001

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or os.getenv('CONFIG_FILE', '.env')
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        # 从环境变量加载
        self.payment_config = PaymentConfig(
            mode=OperationMode(os.getenv('PAYMENT_MODE', 'mock')),
            alipay_app_id=os.getenv('ALIPAY_APP_ID', ''),
            alipay_private_key_path=os.getenv('ALIPAY_PRIVATE_KEY_PATH', ''),
            alipay_public_key_path=os.getenv('ALIPAY_PUBLIC_KEY_PATH', ''),
            alipay_gateway=os.getenv('ALIPAY_GATEWAY', 'https://openapi.alipay.com/gateway.do'),
            alipay_sandbox=os.getenv('ALIPAY_SANDBOX', 'true').lower() == 'true'
        )
        
        self.amazon_config = AmazonConfig(
            mode=OperationMode(os.getenv('AMAZON_MODE', 'mock')),
            sp_api_refresh_token=os.getenv('AMAZON_SP_API_REFRESH_TOKEN', ''),
            sp_api_client_id=os.getenv('AMAZON_SP_API_CLIENT_ID', ''),
            sp_api_client_secret=os.getenv('AMAZON_SP_API_CLIENT_SECRET', ''),
            marketplace_id=os.getenv('AMAZON_MARKETPLACE_ID', 'ATVPDKIKX0DER'),
            region=os.getenv('AMAZON_REGION', 'us-east-1'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', ''),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', ''),
            aws_role_arn=os.getenv('AWS_ROLE_ARN', ''),
            rapidapi_key=os.getenv('RAPIDAPI_KEY', ''),
            rapidapi_host=os.getenv('RAPIDAPI_HOST', 'real-time-amazon-data.p.rapidapi.com'),
            sandbox=os.getenv('AMAZON_SANDBOX', 'true').lower() == 'true'
        )
        
        self.system_config = SystemConfig(
            environment=os.getenv('ENVIRONMENT', 'development'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            enable_metrics=os.getenv('ENABLE_METRICS', 'false').lower() == 'true',
            enable_tracing=os.getenv('ENABLE_TRACING', 'false').lower() == 'true',
            user_agent_port=int(os.getenv('USER_AGENT_PORT', '5011')),
            payment_agent_port=int(os.getenv('PAYMENT_AGENT_PORT', '5005')),
            amazon_agent_port=int(os.getenv('AMAZON_AGENT_PORT', '5012')),
            registry_port=int(os.getenv('REGISTRY_PORT', '5001'))
        )
    
    def is_payment_real(self) -> bool:
        """检查支付是否为真实模式"""
        return self.payment_config.mode == OperationMode.REAL
    
    def is_amazon_real(self) -> bool:
        """检查Amazon是否为真实模式"""
        return self.amazon_config.mode == OperationMode.REAL
    
    def is_production(self) -> bool:
        """检查是否为生产环境"""
        return self.system_config.environment == "production"
    
    def validate_config(self) -> Dict[str, Any]:
        """验证配置完整性"""
        issues = []
        
        # 验证支付配置
        if self.is_payment_real():
            if not self.payment_config.alipay_app_id:
                issues.append("支付宝APP_ID未配置")
            if not self.payment_config.alipay_private_key_path:
                issues.append("支付宝私钥路径未配置")
            if not os.path.exists(self.payment_config.alipay_private_key_path):
                issues.append("支付宝私钥文件不存在")
        
        # 验证Amazon配置
        if self.is_amazon_real():
            if not self.amazon_config.sp_api_refresh_token:
                issues.append("Amazon SP-API refresh token未配置")
            if not self.amazon_config.sp_api_client_id:
                issues.append("Amazon SP-API client ID未配置")
            if not self.amazon_config.aws_access_key_id:
                issues.append("AWS access key未配置")
        
        # 验证生产环境配置
        if self.is_production():
            if self.payment_config.alipay_sandbox:
                issues.append("生产环境不应使用支付宝沙箱")
            if self.amazon_config.sandbox:
                issues.append("生产环境不应使用Amazon沙箱")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    def get_service_urls(self) -> Dict[str, str]:
        """获取服务URL配置"""
        return {
            "user_agent": f"http://localhost:{self.system_config.user_agent_port}",
            "payment_agent": f"http://localhost:{self.system_config.payment_agent_port}",
            "amazon_agent": f"http://localhost:{self.system_config.amazon_agent_port}",
            "registry": f"http://localhost:{self.system_config.registry_port}"
        }
    
    def export_config_template(self, file_path: str = ".env.template"):
        """导出配置模板"""
        template = """# 系统配置
ENVIRONMENT=development
LOG_LEVEL=INFO
ENABLE_METRICS=false
ENABLE_TRACING=false

# 服务端口配置
USER_AGENT_PORT=5011
PAYMENT_AGENT_PORT=5005
AMAZON_AGENT_PORT=5012
REGISTRY_PORT=5001

# 支付配置
PAYMENT_MODE=mock  # mock, real, hybrid
ALIPAY_APP_ID=your_app_id_here
ALIPAY_PRIVATE_KEY_PATH=./keys/app_private_key.pem
ALIPAY_PUBLIC_KEY_PATH=./keys/alipay_public_key.pem
ALIPAY_GATEWAY=https://openapi.alipay.com/gateway.do
ALIPAY_SANDBOX=true

# Amazon配置
AMAZON_MODE=mock  # mock, real, hybrid
AMAZON_SP_API_REFRESH_TOKEN=your_refresh_token
AMAZON_SP_API_CLIENT_ID=your_client_id
AMAZON_SP_API_CLIENT_SECRET=your_client_secret
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
AMAZON_REGION=us-east-1
AMAZON_SANDBOX=true

# AWS配置（Amazon SP-API需要）
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_ROLE_ARN=your_aws_role_arn

# RapidAPI配置（商品搜索）
RAPIDAPI_KEY=your_rapidapi_key
RAPIDAPI_HOST=real-time-amazon-data.p.rapidapi.com
"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(template)
        
        print(f"✅ 配置模板已导出到: {file_path}")

# 全局配置实例
config = ConfigManager()

def get_config() -> ConfigManager:
    """获取全局配置实例"""
    return config

# 配置验证装饰器
def require_real_payment(func):
    """装饰器：要求真实支付模式"""
    def wrapper(*args, **kwargs):
        if not config.is_payment_real():
            raise ValueError("此功能需要真实支付模式")
        return func(*args, **kwargs)
    return wrapper

def require_real_amazon(func):
    """装饰器：要求真实Amazon模式"""
    def wrapper(*args, **kwargs):
        if not config.is_amazon_real():
            raise ValueError("此功能需要真实Amazon模式")
        return func(*args, **kwargs)
    return wrapper

if __name__ == "__main__":
    # 测试配置管理器
    config_mgr = ConfigManager()
    
    print("📋 当前配置:")
    print(f"支付模式: {config_mgr.payment_config.mode.value}")
    print(f"Amazon模式: {config_mgr.amazon_config.mode.value}")
    print(f"环境: {config_mgr.system_config.environment}")
    
    print("\n🔍 配置验证:")
    validation = config_mgr.validate_config()
    if validation["valid"]:
        print("✅ 配置验证通过")
    else:
        print("❌ 配置验证失败:")
        for issue in validation["issues"]:
            print(f"  - {issue}")
    
    print("\n🌐 服务URL:")
    urls = config_mgr.get_service_urls()
    for service, url in urls.items():
        print(f"  {service}: {url}")
    
    # 导出配置模板
    config_mgr.export_config_template()
