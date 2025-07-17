from typing import List
import requests
import json
from eth_account import Account
from web3 import Web3
import time

from utils.erc20 import erc20_balance, erc20_allowance, erc20_contract_info, erc20_approve, ERC20_ABI

from web3 import Web3
from typing import Dict

def get_token_info(web3: Web3, token_contract_address: str, erc20_abi: list) -> Dict:
    """
    获取指定 ERC20/XRC20 代币的基本信息（名称、符号、小数位数）。

    Args:
        web3 (Web3): 已连接网络的 Web3 实例（如 IoTeX 测试网）
        token_contract_address (str): ERC20/XRC20 代币合约地址
        erc20_abi (list): ERC20 ABI 列表

    Returns:
        Dict: 包含 name, symbol, decimals 或错误信息
    """
    try:
        contract = web3.eth.contract(
            address=web3.to_checksum_address(token_contract_address),
            abi=erc20_abi
        )

        name = contract.functions.name().call()
        symbol = contract.functions.symbol().call()
        decimals = contract.functions.decimals().call()

        return {
            "success": True,
            "name": name,
            "symbol": symbol,
            "decimals": decimals
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"无法读取代币信息: {str(e)}"
        }

# IoTeX 测试网 RPC 端点
testnet_rpc = "https://babel-api.testnet.iotex.io"
web3 = Web3(Web3.HTTPProvider(testnet_rpc))
chain_id = 4690
polyagent_token_contract = "0xD3286E20Ff71438D9f6969828F7218af4A375e2f" 

sender_private_key = "e4ad52fbc8c6fe3f4069af70363b24ca4453dbf472d92f83a8adf38e8010991f"
sender_address = Account.from_key('0x' + sender_private_key).address

spender_private_key = "3efe78303dcf8ea3355ef363f04eb442e000081fe66ebcebf5d9cf19f3ace8b8"
spender_address = Account.from_key('0x' + spender_private_key).address

# info = get_token_info(web3, polyagent_token_contract, ERC20_ABI)
# print(info)


# print(sender_address)
# print(spender_address)
# print("----------------------------------------------")

# allowance_info = erc20_allowance(
#     token_contract_address=polyagent_token_contract,
#     owner_address=sender_address,
#     spender_address=spender_address,
# )

# contract_info = erc20_contract_info(token_contract_address=polyagent_token_contract)

# approve_info = erc20_approve(
#     private_key=sender_private_key,
#     token_contract_address=polyagent_token_contract,
#     spender_address=spender_address,
#     amount=2,
#     decimals=18
# )

balance_info = erc20_balance(
    token_contract_address=polyagent_token_contract,
    wallet_address=sender_address,
    decimals=18
)

# allowance_info = erc20_allowance(
#     token_contract_address=polyagent_token_contract,
#     owner_address=sender_address,
#     spender_address=spender_address,
#     decimals=18
# )

print(json.dumps(balance_info, indent=4))
print("----------------------------------------------")
# print(json.dumps(allowance_info,indent=4))
# print("----------------------------------------------")
# print(json.dumps(contract_info,indent=4))
# print("----------------------------------------------")
# print(json.dumps(approve_info,indent=4))
# print("----------------------------------------------")
# print(json.dumps(balance_info, indent=4))
# print("----------------------------------------------")
# print(json.dumps(allowance_info,indent=4))

