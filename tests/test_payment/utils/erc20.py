from typing import List
import requests
import json
from eth_account import Account
from web3 import Web3
import time

 # IoTeX 测试网 RPC 端点
testnet_rpc = "https://babel-api.testnet.iotex.io"
web3 = Web3(Web3.HTTPProvider(testnet_rpc))
chain_id = 4690
polyagent_token_contract = "0xD3286E20Ff71438D9f6969828F7218af4A375e2f"  # 示例代币合约地址

def iotex_transfer(private_key: str, to_address: str, amount_iotx: float) -> str:
    """
    在 IoTeX 测试网进行转账操作
    
    参数:
    - private_key: 转出账户的私钥（不包含0x前缀）
    - to_address: 转入账户地址
    - amount_iotx: 转移的 IOTX 数量（以 IOTX 为单位）
    
    返回:
    - 交易哈希或错误信息
    """
    try:
        # 确保私钥格式正确
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        
        # 创建账户对象
        account = Account.from_key(private_key)
        from_address = account.address
        
        print(f"发送方地址: {from_address}")
        print(f"接收方地址: {to_address}")
        print(f"转账金额: {amount_iotx} IOTX")
        
        # 检查连接
        if not web3.is_connected():
            return "错误: 无法连接到 IoTeX 测试网"
        
        # 获取账户余额
        balance_wei = web3.eth.get_balance(from_address)
        balance_iotx = web3.from_wei(balance_wei, 'ether')
        print(f"当前账户余额: {balance_iotx} IOTX")
        
        # 检查余额是否足够
        if balance_iotx < amount_iotx:
            return f"错误: 余额不足。当前余额: {balance_iotx} IOTX，需要: {amount_iotx} IOTX"
        
        # 将 IOTX 转换为 wei
        amount_wei = web3.to_wei(amount_iotx, 'ether')
        
        # 获取当前 nonce
        nonce = web3.eth.get_transaction_count(from_address)
        
        # 估算 gas 费用
        gas_price = web3.eth.gas_price
        gas_limit = 21000  # 标准转账的 gas limit
        
        print(f"Gas Price: {gas_price} wei")
        print(f"Gas Limit: {gas_limit}")
        
        # 构建交易
        transaction = {
            'to': to_address,
            'value': amount_wei,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': chain_id
        }
        
        # 签名交易
        signed_txn = web3.eth.account.sign_transaction(transaction, private_key)
        
        # 发送交易 - 兼容新旧版本的web3.py
        raw_transaction = getattr(signed_txn, 'rawTransaction', getattr(signed_txn, 'raw_transaction', None))
        if raw_transaction is None:
            return "错误: 无法获取签名交易数据"
        tx_hash = web3.eth.send_raw_transaction(raw_transaction)
        tx_hash_hex = tx_hash.hex()
        
        print(f"交易已发送! 交易哈希: {tx_hash_hex}")
        
        # 等待交易确认
        print("等待交易确认...")
        try:
            # 等待交易收据，最多等待5分钟
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt.status == 1:
                result = f"✅ 转账成功!\n"
                result += f"交易哈希: {tx_hash_hex}\n"
                result += f"区块号: {receipt.blockNumber}\n"
                result += f"Gas 使用量: {receipt.gasUsed}\n"
                result += f"从: {from_address}\n"
                result += f"到: {to_address}\n"
                result += f"金额: {amount_iotx} IOTX\n"
                result += f"IoTeX 测试网浏览器链接: https://testnet.iotexscan.io/tx/{tx_hash_hex}"
                return result
            else:
                return f"❌ 交易失败! 交易哈希: {tx_hash_hex}"
                
        except Exception as wait_error:
            return f"⚠️ 交易已发送但等待确认时出错: {str(wait_error)}\n交易哈希: {tx_hash_hex}\n请手动检查交易状态"
        
    except ValueError as ve:
        return f"参数错误: {str(ve)}"
    except Exception as e:
        return f"转账失败: {str(e)}"


# ERC20 合约 ABI（简化版，包含approve和transferFrom方法）
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_from", "type": "address"},
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transferFrom",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

def erc20_approve(
    private_key: str,
    token_contract_address: str,
    spender_address: str,
    amount: float,
    decimals: int = 18
) -> str:
    """
    执行 ERC20 代币的 approve 操作
    
    参数:
    - private_key: 代币拥有者的私钥（不包含0x前缀）
    - token_contract_address: ERC20代币合约地址
    - spender_address: 被授权的地址（可以花费代币的地址）
    - amount: 授权的代币数量（以代币为单位，非wei）
    - decimals: 代币精度（默认18位）
    
    返回:
    - 交易哈希或错误信息
    """
    try:
        # 确保私钥格式正确
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        
        # 创建账户对象
        account = Account.from_key(private_key)
        owner_address = account.address
        
        print(f"代币拥有者地址: {owner_address}")
        print(f"被授权地址: {spender_address}")
        print(f"授权数量: {amount}")
        print(f"代币合约地址: {token_contract_address}")
        
        # 检查连接
        if not web3.is_connected():
            return "错误: 无法连接到 IoTeX 测试网"
        
        # 创建合约实例
        contract = web3.eth.contract(
            address=Web3.to_checksum_address(token_contract_address),
            abi=ERC20_ABI
        )
        
        # 将代币数量转换为对应精度的整数
        amount_wei = int(amount * (10 ** decimals))
        
        # 获取当前 nonce
        nonce = web3.eth.get_transaction_count(owner_address)
        
        # 构建 approve 交易
        approve_txn = contract.functions.approve(
            Web3.to_checksum_address(spender_address),
            amount_wei
        ).build_transaction({
            'chainId': chain_id,
            'gas': 100000,  # approve 操作的 gas limit
            'gasPrice': web3.eth.gas_price,
            'nonce': nonce,
        })
        
        print(f"Gas Price: {approve_txn['gasPrice']} wei")
        print(f"Gas Limit: {approve_txn['gas']}")
        
        # 签名交易
        signed_txn = web3.eth.account.sign_transaction(approve_txn, private_key)
        
        # 发送交易 - 兼容新旧版本的web3.py
        raw_transaction = getattr(signed_txn, 'rawTransaction', getattr(signed_txn, 'raw_transaction', None))
        if raw_transaction is None:
            return "错误: 无法获取签名交易数据"
        tx_hash = web3.eth.send_raw_transaction(raw_transaction)
        tx_hash_hex = tx_hash.hex()
        
        print(f"Approve 交易已发送! 交易哈希: {tx_hash_hex}")
        
        # 等待交易确认
        print("等待交易确认...")
        try:
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt.status == 1:
                result = f"✅ Approve 操作成功!\n"
                result += f"交易哈希: {tx_hash_hex}\n"
                result += f"区块号: {receipt.blockNumber}\n"
                result += f"Gas 使用量: {receipt.gasUsed}\n"
                result += f"代币拥有者: {owner_address}\n"
                result += f"被授权地址: {spender_address}\n"
                result += f"授权数量: {amount} 代币\n"
                result += f"IoTeX 测试网浏览器链接: https://testnet.iotexscan.io/tx/{tx_hash_hex}"
                return result
            else:
                return f"❌ Approve 操作失败! 交易哈希: {tx_hash_hex}"
                
        except Exception as wait_error:
            return f"⚠️ 交易已发送但等待确认时出错: {str(wait_error)}\n交易哈希: {tx_hash_hex}\n请手动检查交易状态"
        
    except ValueError as ve:
        return f"参数错误: {str(ve)}"
    except Exception as e:
        return f"Approve 操作失败: {str(e)}"

def erc20_transfer_from(
    private_key: str,
    token_contract_address: str,
    from_address: str,
    to_address: str,
    amount: float,
    decimals: int = 18
) -> str:
    """
    执行 ERC20 代币的 transferFrom 操作
    
    参数:
    - private_key: 被授权地址的私钥（有权限转移代币的地址）
    - token_contract_address: ERC20代币合约地址
    - from_address: 代币转出地址（代币拥有者地址）
    - to_address: 代币转入地址
    - amount: 转移的代币数量（以代币为单位，非wei）
    - decimals: 代币精度（默认18位）
    
    返回:
    - 交易哈希或错误信息
    """
    try:
        # 确保私钥格式正确
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        
        # 创建账户对象（这是被授权的地址）
        account = Account.from_key(private_key)
        spender_address = account.address
        
        print(f"执行者地址（被授权地址）: {spender_address}")
        print(f"代币转出地址: {from_address}")
        print(f"代币转入地址: {to_address}")
        print(f"转移数量: {amount}")
        print(f"代币合约地址: {token_contract_address}")
        
        # 检查连接
        if not web3.is_connected():
            return "错误: 无法连接到 IoTeX 测试网"
        
        # 创建合约实例
        contract = web3.eth.contract(
            address=Web3.to_checksum_address(token_contract_address),
            abi=ERC20_ABI
        )
        
        # 将代币数量转换为对应精度的整数
        amount_wei = int(amount * (10 ** decimals))
        
        # 检查授权额度
        try:
            allowance = contract.functions.allowance(
                Web3.to_checksum_address(from_address),
                Web3.to_checksum_address(spender_address)
            ).call()
            allowance_tokens = allowance / (10 ** decimals)
            print(f"当前授权额度: {allowance_tokens} 代币")
            
            if allowance < amount_wei:
                return f"错误: 授权额度不足。当前授权: {allowance_tokens} 代币，需要: {amount} 代币"
        except Exception as e:
            print(f"警告: 无法检查授权额度 - {str(e)}")
        
        # 获取当前 nonce
        nonce = web3.eth.get_transaction_count(spender_address)
        
        # 构建 transferFrom 交易
        transfer_txn = contract.functions.transferFrom(
            Web3.to_checksum_address(from_address),
            Web3.to_checksum_address(to_address),
            amount_wei
        ).build_transaction({
            'chainId': chain_id,
            'gas': 100000,  # transferFrom 操作的 gas limit
            'gasPrice': web3.eth.gas_price,
            'nonce': nonce,
        })
        
        print(f"Gas Price: {transfer_txn['gasPrice']} wei")
        print(f"Gas Limit: {transfer_txn['gas']}")
        
        # 签名交易
        signed_txn = web3.eth.account.sign_transaction(transfer_txn, private_key)
        
        # 发送交易 - 兼容新旧版本的web3.py
        raw_transaction = getattr(signed_txn, 'rawTransaction', getattr(signed_txn, 'raw_transaction', None))
        if raw_transaction is None:
            return "错误: 无法获取签名交易数据"
        tx_hash = web3.eth.send_raw_transaction(raw_transaction)
        tx_hash_hex = tx_hash.hex()
        
        print(f"TransferFrom 交易已发送! 交易哈希: {tx_hash_hex}")
        
        # 等待交易确认
        print("等待交易确认...")
        try:
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt.status == 1:
                result = f"✅ TransferFrom 操作成功!\n"
                result += f"交易哈希: {tx_hash_hex}\n"
                result += f"区块号: {receipt.blockNumber}\n"
                result += f"Gas 使用量: {receipt.gasUsed}\n"
                result += f"执行者: {spender_address}\n"
                result += f"从: {from_address}\n"
                result += f"到: {to_address}\n"
                result += f"数量: {amount} 代币\n"
                result += f"IoTeX 测试网浏览器链接: https://testnet.iotexscan.io/tx/{tx_hash_hex}"
                return result
            else:
                return f"❌ TransferFrom 操作失败! 交易哈希: {tx_hash_hex}"
                
        except Exception as wait_error:
            return f"⚠️ 交易已发送但等待确认时出错: {str(wait_error)}\n交易哈希: {tx_hash_hex}\n请手动检查交易状态"
        
    except ValueError as ve:
        return f"参数错误: {str(ve)}"
    except Exception as e:
        return f"TransferFrom 操作失败: {str(e)}"


def erc20_balance(
    token_contract_address: str,
    wallet_address: str,
    decimals: int = 18
) -> dict:
    """
    查询指定地址的 ERC20 代币余额
    
    参数:
    - token_contract_address: ERC20代币合约地址
    - wallet_address: 要查询余额的钱包地址
    - decimals: 代币精度（默认18位）
    
    返回:
    - 包含余额信息的字典，格式为:
      {
          'success': bool,
          'balance_wei': int,
          'balance_tokens': float,
          'wallet_address': str,
          'contract_address': str,
          'decimals': int,
          'error': str (仅在失败时存在)
      }
    """
    try:
        print(f"查询地址: {wallet_address}")
        print(f"代币合约地址: {token_contract_address}")
        
        # 检查连接
        if not web3.is_connected():
            return {
                'success': False,
                'error': '无法连接到 IoTeX 测试网'
            }
        
        # 创建合约实例
        contract = web3.eth.contract(
            address=Web3.to_checksum_address(token_contract_address),
            abi=ERC20_ABI
        )
        
        # 查询余额（返回 wei 单位）
        balance_wei = contract.functions.balanceOf(
            Web3.to_checksum_address(wallet_address)
        ).call()
        
        # 转换为代币单位
        balance_tokens = balance_wei / (10 ** decimals)
        
        print(f"余额: {balance_tokens} 代币 ({balance_wei} wei)")
        
        return {
            'success': True,
            'balance_wei': balance_wei,
            'balance_tokens': balance_tokens,
            'wallet_address': wallet_address,
            'contract_address': token_contract_address,
            'decimals': decimals
        }
        
    except Exception as e:
        error_msg = f"查询余额失败: {str(e)}"
        print(error_msg)
        return {
            'success': False,
            'wallet_address': wallet_address,
            'contract_address': token_contract_address,
            'error': error_msg
        }


def erc20_contract_info(token_contract_address: str) -> dict:
    """
    查询 ERC20 代币合约的基本信息
    
    参数:
    - token_contract_address: ERC20代币合约地址
    
    返回:
    - 包含合约信息的字典，格式为:
      {
          'success': bool,
          'contract_address': str,
          'name': str,
          'symbol': str,
          'decimals': int,
          'total_supply_wei': int,
          'total_supply_tokens': float,
          'error': str (仅在失败时存在)
      }
    """
    try:
        print(f"查询合约信息: {token_contract_address}")
        
        # 检查连接
        if not web3.is_connected():
            return {
                'success': False,
                'error': '无法连接到 IoTeX 测试网'
            }
        
        # 扩展的 ABI，包含更多信息查询方法
        extended_abi = ERC20_ABI + [
            {
                "constant": True,
                "inputs": [],
                "name": "name",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            }
        ]
        
        # 创建合约实例
        contract = web3.eth.contract(
            address=Web3.to_checksum_address(token_contract_address),
            abi=extended_abi
        )
        
        # 查询基本信息
        name = "N/A"
        symbol = "N/A"
        decimals = 18
        total_supply_wei = 0
        
        try:
            name = contract.functions.name().call()
        except:
            print("警告: 无法获取代币名称")
        
        try:
            symbol = contract.functions.symbol().call()
        except:
            print("警告: 无法获取代币符号")
        
        try:
            decimals = contract.functions.decimals().call()
        except:
            print("警告: 无法获取代币精度，使用默认值18")
        
        try:
            total_supply_wei = contract.functions.totalSupply().call()
        except:
            print("警告: 无法获取总供应量")
        
        total_supply_tokens = total_supply_wei / (10 ** decimals)
        
        print(f"代币名称: {name}")
        print(f"代币符号: {symbol}")
        print(f"代币精度: {decimals}")
        print(f"总供应量: {total_supply_tokens} 代币")
        
        return {
            'success': True,
            'contract_address': token_contract_address,
            'name': name,
            'symbol': symbol,
            'decimals': decimals,
            'total_supply_wei': total_supply_wei,
            'total_supply_tokens': total_supply_tokens
        }
        
    except Exception as e:
        error_msg = f"查询合约信息失败: {str(e)}"
        print(error_msg)
        return {
            'success': False,
            'contract_address': token_contract_address,
            'error': error_msg
        }


def erc20_allowance(
    token_contract_address: str,
    owner_address: str,
    spender_address: str,
    decimals: int = 18
) -> dict:
    """
    查询 ERC20 代币的授权额度
    
    参数:
    - token_contract_address: ERC20代币合约地址
    - owner_address: 代币拥有者地址
    - spender_address: 被授权地址
    - decimals: 代币精度（默认18位）
    
    返回:
    - 包含授权信息的字典，格式为:
      {
          'success': bool,
          'allowance_wei': int,
          'allowance_tokens': float,
          'owner_address': str,
          'spender_address': str,
          'contract_address': str,
          'decimals': int,
          'error': str (仅在失败时存在)
      }
    """
    try:
        print(f"查询授权额度:")
        print(f"代币拥有者: {owner_address}")
        print(f"被授权地址: {spender_address}")
        print(f"代币合约: {token_contract_address}")
        
        # 检查连接
        if not web3.is_connected():
            return {
                'success': False,
                'error': '无法连接到 IoTeX 测试网'
            }
        
        # 创建合约实例
        contract = web3.eth.contract(
            address=Web3.to_checksum_address(token_contract_address),
            abi=ERC20_ABI
        )
        
        # 查询授权额度
        allowance_wei = contract.functions.allowance(
            Web3.to_checksum_address(owner_address),
            Web3.to_checksum_address(spender_address)
        ).call()
        
        # 转换为代币单位
        allowance_tokens = allowance_wei / (10 ** decimals)
        
        print(f"授权额度: {allowance_tokens} 代币 ({allowance_wei} wei)")
        
        return {
            'success': True,
            'allowance_wei': allowance_wei,
            'allowance_tokens': allowance_tokens,
            'owner_address': owner_address,
            'spender_address': spender_address,
            'contract_address': token_contract_address,
            'decimals': decimals
        }
        
    except Exception as e:
        error_msg = f"查询授权额度失败: {str(e)}"
        print(error_msg)
        return {
            'success': False,
            'owner_address': owner_address,
            'spender_address': spender_address,
            'contract_address': token_contract_address,
            'error': error_msg
        }


def example():
    sender_private_key = "YOUR_PRIVATEKEY"  # 替换为发送地址的私钥（不包含0x前缀）
    spender_private_key = "YOUR_PRIVATEKEY"  # 替换为被授权地址的私钥（不包含0x前缀）

    sender_address = Account.from_key('0x' + sender_private_key).address
    spender_address = Account.from_key('0x' + spender_private_key).address

    # 测试查询代币余额
    balance_info = erc20_balance(
        token_contract_address=polyagent_token_contract,
        wallet_address=sender_address,
        decimals=18
    )
    print(json.dumps(balance_info, indent=4))
    
    # 测试 approve 操作
    approve_result = erc20_approve(
        private_key=sender_private_key,
        token_contract_address=polyagent_token_contract,
        spender_address=spender_address,
        amount=100.0,  # 授权100代币
        decimals=18
    )
    print(approve_result)
    # 测试查询 allowance
    allowance_info = erc20_allowance(
        token_contract_address=polyagent_token_contract,
        owner_address=sender_address,
        spender_address=spender_address,
        decimals=18
    )
    print(json.dumps(allowance_info, indent=4))
    # 测试 transferFrom 操作
    transfer_result = erc20_transfer_from(
        private_key=spender_private_key,
        token_contract_address=polyagent_token_contract,
        from_address=sender_address,
        to_address=spender_address,
        amount=50.0,  # 转移50代币
        decimals=18
    )
    print(transfer_result)

# 示例用法
if __name__ == "__main__":
    example()