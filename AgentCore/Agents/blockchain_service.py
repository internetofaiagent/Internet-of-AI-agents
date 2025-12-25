#!/usr/bin/env python3
"""
区块链服务 - 封装交易信息上链功能
"""

import os
import json
import logging
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from web3 import Web3
from eth_account import Account

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BlockchainService")


# ==============================================================================
#  上链数据结构定义
# ==============================================================================
@dataclass
class OnChainTransactionData:
    """上链交易数据模型"""
    order_id: str
    user_address: str  # 用户钱包地址
    merchant_address: str  # 商家钱包地址
    amount: float
    currency: str
    payment_tx_hash: str  # 支付交易哈希
    delivery_tx_hash: Optional[str] = None  # 交付交易哈希（可选）
    status: str = "paid"  # "paid", "delivered", "completed"
    timestamp: str = ""  # ISO格式时间戳
    product_info: Dict[str, Any] = None  # 商品信息
    delivery_info: Dict[str, Any] = None  # 交付信息
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if self.product_info is None:
            self.product_info = {}
        if self.delivery_info is None:
            self.delivery_info = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """序列化为JSON字符串"""
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
    
    def calculate_hash(self) -> str:
        """计算数据哈希"""
        json_str = self.to_json()
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()


# ==============================================================================
#  区块链服务类
# ==============================================================================
class BlockchainService:
    """
    区块链服务类 - 封装交易信息上链功能
    
    使用事件日志（Event Logs）方式：
    - 将交易数据序列化为JSON
    - 计算数据哈希
    - 将哈希存储在交易的 input data 中
    - 返回交易哈希用于后续查询
    """
    
    def __init__(
        self,
        rpc_url: Optional[str] = None,
        chain_id: Optional[int] = None,
        merchant_private_key: Optional[str] = None,
        merchant_address: Optional[str] = None
    ):
        """
        初始化区块链服务
        
        Args:
            rpc_url: IoTeX RPC URL，默认使用测试网
            chain_id: 链ID，默认使用IoTeX测试网 (4690)
            merchant_private_key: 商家私钥（用于签名交易）
            merchant_address: 商家钱包地址（如果提供私钥，会自动推导）
        """
        # 默认使用 IoTeX 测试网
        self.rpc_url = rpc_url or os.environ.get("IOTEX_RPC_URL", "https://babel-api.testnet.iotex.io")
        self.chain_id = chain_id or int(os.environ.get("IOTEX_CHAIN_ID", "4690"))
        
        # 初始化 Web3 连接
        self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        if not self.web3.is_connected():
            logger.warning(f"⚠️ [BlockchainService] 无法连接到 IoTeX 网络: {self.rpc_url}")
        else:
            logger.info(f"✅ [BlockchainService] 已连接到 IoTeX 网络: {self.rpc_url} (Chain ID: {self.chain_id})")
        
        # 商家账户信息
        self.merchant_private_key = merchant_private_key or os.environ.get("MERCHANT_PRIVATE_KEY")
        self.merchant_address = merchant_address
        
        if self.merchant_private_key:
            # 确保私钥格式正确
            if not self.merchant_private_key.startswith("0x"):
                self.merchant_private_key = "0x" + self.merchant_private_key
            
            # 从私钥推导地址
            try:
                account = Account.from_key(self.merchant_private_key)
                self.merchant_address = account.address
                logger.info(f"✅ [BlockchainService] 商家地址: {self.merchant_address}")
            except Exception as e:
                logger.error(f"❌ [BlockchainService] 无法从私钥推导地址: {e}")
                self.merchant_private_key = None
        else:
            logger.warning("⚠️ [BlockchainService] 未提供商家私钥，上链功能可能受限")
    
    def store_transaction_on_chain(
        self,
        transaction_data: OnChainTransactionData,
        to_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        将交易信息存储到链上
        
        实现步骤：
        1. 将订单数据序列化为 JSON
        2. 计算数据哈希（SHA256）
        3. 将哈希写入交易 input data（作为交易备注）
        4. 获取交易哈希并返回
        
        使用交易 input data 存储数据哈希，通过交易哈希可以查询和验证数据
        
        Args:
            transaction_data: 上链交易数据对象
            to_address: 接收地址（可选，如果提供则发送到该地址，否则发送到零地址）
            
        Returns:
            包含交易哈希和状态的字典
        """
        try:
            # 检查连接
            if not self.web3.is_connected():
                return {
                    "success": False,
                    "error": "无法连接到 IoTeX 网络"
                }
            
            # 检查是否有私钥
            if not self.merchant_private_key:
                return {
                    "success": False,
                    "error": "未提供商家私钥，无法签名交易"
                }
            
            # 步骤1: 将订单数据序列化为 JSON
            json_data = transaction_data.to_json()
            logger.info(f"📝 [BlockchainService] 步骤1: 数据序列化为JSON，长度: {len(json_data)} 字符")
            logger.debug(f"📝 [BlockchainService] JSON数据: {json_data[:200]}...")
            
            # 步骤2: 计算数据哈希（SHA256）
            data_hash = transaction_data.calculate_hash()
            logger.info(f"📊 [BlockchainService] 步骤2: 计算数据哈希 (SHA256): {data_hash}")
            
            # 步骤3: 将哈希写入交易 input data（作为交易备注）
            # SHA256 哈希是64个十六进制字符（32字节）
            # 将哈希编码为 bytes
            hash_bytes = bytes.fromhex(data_hash)
            
            # 验证哈希长度（SHA256 应该是32字节）
            if len(hash_bytes) != 32:
                logger.warning(f"⚠️ [BlockchainService] 哈希长度异常: {len(hash_bytes)} 字节，预期32字节")
                # 如果长度不对，进行调整
                if len(hash_bytes) < 32:
                    hash_bytes = hash_bytes + b'\x00' * (32 - len(hash_bytes))
                else:
                    hash_bytes = hash_bytes[:32]
            
            logger.info(f"📝 [BlockchainService] 步骤3: 准备将哈希写入交易 input data: {data_hash[:16]}...")
            
            # 目标地址：如果提供则使用，否则使用零地址（作为数据存储交易）
            if to_address:
                to_address = self.web3.to_checksum_address(to_address)
            else:
                # 使用零地址，表示这是一个数据存储交易
                to_address = "0x0000000000000000000000000000000000000000"
            
            # 获取账户信息
            account = Account.from_key(self.merchant_private_key)
            from_address = account.address
            
            # 检查余额（需要足够的 IOTX 支付 gas）
            balance = self.web3.eth.get_balance(from_address)
            balance_iotx = self.web3.from_wei(balance, 'ether')
            
            if balance_iotx < 0.001:  # 至少需要 0.001 IOTX
                logger.warning(f"⚠️ [BlockchainService] 账户余额不足: {balance_iotx} IOTX")
                return {
                    "success": False,
                    "error": f"账户余额不足，需要至少 0.001 IOTX，当前余额: {balance_iotx} IOTX"
                }
            
            # 获取 nonce
            nonce = self.web3.eth.get_transaction_count(from_address)
            
            # 估算 gas（数据存储交易通常需要更多 gas）
            gas_limit = 100000  # 设置一个合理的 gas limit
            gas_price = self.web3.eth.gas_price
            
            # 构建交易
            transaction = {
                'to': to_address,
                'value': 0,  # 不发送 IOTX，只存储数据
                'data': hash_bytes,  # 将数据哈希存储在 input data 中
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.chain_id
            }
            
            logger.info(f"📝 [BlockchainService] 构建交易: from={from_address}, to={to_address}, data_hash={data_hash[:16]}...")
            
            # 签名交易
            signed_txn = self.web3.eth.account.sign_transaction(transaction, self.merchant_private_key)
            
            # 步骤4: 发送交易并获取交易哈希
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            logger.info(f"✅ [BlockchainService] 步骤4: 交易已发送，交易哈希: {tx_hash_hex}")
            
            # 等待交易确认（可选，可以异步处理）
            try:
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                if receipt.status == 1:
                    logger.info(f"✅ [BlockchainService] 交易已确认: {tx_hash_hex}")
                    return {
                        "success": True,
                        "tx_hash": tx_hash_hex,
                        "block_number": receipt.blockNumber,
                        "block_hash": receipt.blockHash.hex(),
                        "data_hash": data_hash,
                        "json_data": json_data,  # 包含原始JSON数据（用于验证）
                        "transaction_data": transaction_data.to_dict(),
                        "gas_used": receipt.gasUsed,
                        "message": f"交易信息已成功上链，交易哈希: {tx_hash_hex}"
                    }
                else:
                    logger.error(f"❌ [BlockchainService] 交易失败: {tx_hash_hex}")
                    return {
                        "success": False,
                        "error": f"交易失败，交易哈希: {tx_hash_hex}",
                        "tx_hash": tx_hash_hex
                    }
            except Exception as e:
                logger.warning(f"⚠️ [BlockchainService] 等待交易确认超时: {e}")
                # 即使超时，交易可能已经发送，返回交易哈希
                return {
                    "success": True,
                    "tx_hash": tx_hash_hex,
                    "data_hash": data_hash,
                    "json_data": json_data,  # 包含原始JSON数据（用于验证）
                    "transaction_data": transaction_data.to_dict(),
                    "message": f"交易已发送，等待确认中，交易哈希: {tx_hash_hex}",
                    "warning": "交易确认超时，请稍后查询交易状态"
                }
            
        except Exception as e:
            logger.error(f"❌ [BlockchainService] 上链失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": f"上链失败: {str(e)}"
            }
    
    def verify_transaction_on_chain(
        self,
        tx_hash: str,
        expected_data: Optional[OnChainTransactionData] = None
    ) -> Dict[str, Any]:
        """
        验证链上交易
        
        实现步骤：
        1. 通过交易哈希查询链上数据
        2. 提取交易 input data 中的数据哈希
        3. 如果提供期望数据，验证数据完整性（比较哈希）
        
        Args:
            tx_hash: 交易哈希
            expected_data: 期望的交易数据（可选，如果提供则验证数据一致性）
            
        Returns:
            包含验证结果的字典
        """
        try:
            # 检查连接
            if not self.web3.is_connected():
                return {
                    "success": False,
                    "error": "无法连接到 IoTeX 网络"
                }
            
            logger.info(f"🔍 [BlockchainService] 开始验证交易: {tx_hash}")
            
            # 步骤1: 通过交易哈希查询链上数据
            try:
                receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                logger.info(f"✅ [BlockchainService] 步骤1: 获取交易收据成功，区块号: {receipt.blockNumber}")
            except Exception as e:
                logger.error(f"❌ [BlockchainService] 无法获取交易收据: {str(e)}")
                return {
                    "success": False,
                    "error": f"无法获取交易收据: {str(e)}"
                }
            
            # 获取交易详情
            try:
                tx = self.web3.eth.get_transaction(tx_hash)
                logger.info(f"✅ [BlockchainService] 获取交易详情成功")
            except Exception as e:
                logger.error(f"❌ [BlockchainService] 无法获取交易详情: {str(e)}")
                return {
                    "success": False,
                    "error": f"无法获取交易详情: {str(e)}"
                }
            
            # 步骤2: 提取交易 input data 中的数据哈希
            input_data = tx.input.hex() if tx.input else ""
            
            if not input_data:
                logger.warning(f"⚠️ [BlockchainService] 交易 input data 为空")
                return {
                    "success": True,
                    "verified": False,
                    "tx_hash": tx_hash,
                    "block_number": receipt.blockNumber,
                    "error": "交易 input data 为空，无法提取数据哈希"
                }
            
            logger.info(f"📊 [BlockchainService] 步骤2: 提取 input data，长度: {len(input_data)} 字符")
            
            # 从 input data 中提取数据哈希
            # input data 应该是32字节（64个十六进制字符）的哈希
            stored_hash = None
            if len(input_data) >= 64:
                # 如果是数据存储交易，input data 应该直接是数据哈希（64个字符）
                # 如果包含函数选择器，取后64个字符
                stored_hash = input_data[-64:] if len(input_data) > 64 else input_data
                logger.info(f"📊 [BlockchainService] 提取的数据哈希: {stored_hash}")
            else:
                logger.warning(f"⚠️ [BlockchainService] input data 长度不足: {len(input_data)} 字符，预期至少64字符")
            
            # 步骤3: 如果提供期望数据，验证数据完整性
            if expected_data:
                # 计算期望数据的哈希
                expected_hash = expected_data.calculate_hash()
                logger.info(f"📊 [BlockchainService] 步骤3: 计算期望数据哈希: {expected_hash}")
                
                if stored_hash:
                    # 比较哈希（不区分大小写）
                    if stored_hash.lower() == expected_hash.lower():
                        logger.info(f"✅ [BlockchainService] 数据验证成功，哈希匹配")
                        return {
                            "success": True,
                            "verified": True,
                            "tx_hash": tx_hash,
                            "block_number": receipt.blockNumber,
                            "stored_hash": stored_hash,
                            "expected_hash": expected_hash,
                            "data_integrity": "valid",
                            "message": "数据验证成功，链上数据与预期数据一致，数据完整性验证通过"
                        }
                    else:
                        logger.warning(f"⚠️ [BlockchainService] 数据验证失败，哈希不匹配")
                        logger.warning(f"   存储哈希: {stored_hash}")
                        logger.warning(f"   期望哈希: {expected_hash}")
                        return {
                            "success": True,
                            "verified": False,
                            "tx_hash": tx_hash,
                            "block_number": receipt.blockNumber,
                            "stored_hash": stored_hash,
                            "expected_hash": expected_hash,
                            "data_integrity": "invalid",
                            "error": "数据验证失败，链上数据与预期数据不一致，数据完整性验证失败"
                        }
                else:
                    return {
                        "success": True,
                        "verified": False,
                        "tx_hash": tx_hash,
                        "block_number": receipt.blockNumber,
                        "error": "无法从 input data 中提取数据哈希，无法进行验证"
                    }
            
            # 如果没有提供期望数据，只返回交易信息（不进行完整性验证）
            logger.info(f"ℹ️ [BlockchainService] 未提供期望数据，仅返回交易信息")
            return {
                "success": True,
                "verified": None,
                "tx_hash": tx_hash,
                "block_number": receipt.blockNumber,
                "block_hash": receipt.blockHash.hex(),
                "transaction_index": receipt.transactionIndex,
                "input_data": input_data,
                "stored_hash": stored_hash,
                "from_address": tx['from'],
                "to_address": tx['to'],
                "gas_used": receipt.gasUsed,
                "status": "success" if receipt.status == 1 else "failed",
                "message": "交易查询成功（未进行数据完整性验证）"
            }
            
        except Exception as e:
            logger.error(f"❌ [BlockchainService] 验证交易失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": f"验证交易失败: {str(e)}"
            }
    
    def create_transaction_data_from_order(
        self,
        order: Any,  # Order 对象
        payment_tx_hash: Optional[str] = None,
        delivery_tx_hash: Optional[str] = None,
        status: str = "paid"
    ) -> OnChainTransactionData:
        """
        从订单对象创建上链交易数据
        
        Args:
            order: Order 对象（来自 merchant_agent.py）
            payment_tx_hash: 支付交易哈希
            delivery_tx_hash: 交付交易哈希（可选）
            status: 订单状态 ("paid", "delivered", "completed")
            
        Returns:
            OnChainTransactionData 对象
        """
        # 从订单中提取信息
        user_address = getattr(order.user_info, 'user_wallet_address', '') or ''
        merchant_address = self.merchant_address or ''
        
        # 从支付信息中获取支付交易哈希
        if not payment_tx_hash and order.payment_info:
            payment_tx_hash = getattr(order.payment_info, 'payment_transaction_hash', None) or ''
        
        # 构建商品信息
        product_info = {}
        if order.product_info:
            product_info = {
                "product_id": getattr(order.product_info, 'product_id', ''),
                "product_name": getattr(order.product_info, 'product_name', ''),
                "quantity": getattr(order.product_info, 'quantity', 1),
                "unit_price": getattr(order.product_info, 'unit_price', 0.0)
            }
        
        # 构建交付信息
        delivery_info = {}
        if order.delivery_info:
            delivery_info = {
                "delivery_method": getattr(order.delivery_info, 'delivery_method', ''),
                "tracking_number": getattr(order.delivery_info, 'tracking_number', ''),
                "carrier": getattr(order.delivery_info, 'carrier', ''),
                "actual_delivery_date": getattr(order.delivery_info, 'actual_delivery_date', '')
            }
        
        # 确定时间戳
        timestamp = order.delivered_at if order.delivered_at else order.accepted_at
        if not timestamp:
            timestamp = order.created_at
        
        return OnChainTransactionData(
            order_id=order.order_id,
            user_address=user_address,
            merchant_address=merchant_address,
            amount=order.amount,
            currency=order.currency,
            payment_tx_hash=payment_tx_hash or '',
            delivery_tx_hash=delivery_tx_hash,
            status=status,
            timestamp=timestamp or datetime.now().isoformat(),
            product_info=product_info,
            delivery_info=delivery_info
        )


# ==============================================================================
#  便捷函数
# ==============================================================================
def create_blockchain_service(
    rpc_url: Optional[str] = None,
    chain_id: Optional[int] = None,
    merchant_private_key: Optional[str] = None
) -> BlockchainService:
    """
    创建区块链服务实例的便捷函数
    
    Args:
        rpc_url: IoTeX RPC URL
        chain_id: 链ID
        merchant_private_key: 商家私钥
        
    Returns:
        BlockchainService 实例
    """
    return BlockchainService(
        rpc_url=rpc_url,
        chain_id=chain_id,
        merchant_private_key=merchant_private_key
    )

