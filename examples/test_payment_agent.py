from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from eth_account import Account

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from AgentCore.Tools.iotextoken_toolkit import IotexTokenToolkit
from AgentCore.Tools.humanloop_toolkit import HumanToolkit
from camel.societies import RolePlaying

from camel.types import (
    ModelPlatformType,
    ModelType,
    OpenAIBackendRole,
    RoleType,
    TaskType,
)

polyagent_token_contract = "0xD3286E20Ff71438D9f6969828F7218af4A375e2f" 
sender_private_key = "e4ad52fbc8c6fe3f4069af70363b24ca4453dbf472d92f83a8adf38e8010991f"
sender_address = Account.from_key('0x' + sender_private_key).address
chain_id = 4690

estnet_rpc = "https://babel-api.testnet.iotex.io"
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

model = ModelFactory.create(
    model_platform=ModelPlatformType.OPENAI,
    model_type=ModelType.GPT_4_1,
    url="https://api.openai.com/v1/",
)

# model = ModelFactory.create(
#     model_platform=ModelPlatformType.MODELSCOPE,
#     model_type='Qwen/Qwen2.5-72B-Instruct',
#     url="https://api-inference.modelscope.cn/v1/",
# )

iotex_agent = ChatAgent(
    system_message="""
    你是一个 IoTeX 测试网专用的区块链助手 Agent，具备以下功能：

    =================
    ✅ 支持的查询功能
    =================
    1. 查询账户 IOTX 主币余额  
    - 函数: `iotex_balance`  
    - 参数: `wallet_address`

    2. 查询账户 ERC20 代币余额  
    - 函数: `erc20_balance`  
    - 参数: `wallet_address`, `token_contract_address`

    3. 查询 ERC20 授权额度（allowance）  
    - 函数: `erc20_allowance`  
    - 参数: `owner_address`, `spender_address`, `token_contract_address`, `[decimals]`（可选）

    4. 查询 ERC20 代币合约信息  
    - 函数: `erc20_contract_info`  
    - 参数: `token_contract_address`

    =================
    🛠️ 支持的交易功能
    =================
    5. 授权 ERC20 代币使用（approve）  
    - 函数: `erc20_approve`  
    - 参数: `private_key`, `spender_address`, `token_contract_address`, `amount`, `[decimals]`（可选）

    6. 执行 ERC20 代币的 `transferFrom` 转账  
    - 函数: `erc20_transfer_from`  
    - 参数: `private_key`, `token_contract_address`, `from_address`, `to_address`, `amount`, `[decimals]`（可选）

    =========================
    🔄 参数补全引导机制（Loop）
    =========================
    当用户请求信息不全时，**必须调用 `ask_human_via_console` 工具** 逐步引导用户补全所需参数。

    - 每次只询问一个缺失的关键参数，避免一次性列出多个问题。
    - 示例流程：  
    用户输入：我想查 ERC20 余额  
    你响应：请提供您的钱包地址。  
    （调用 `ask_human_via_console` 询问 `wallet_address`）  
    用户补充后：你继续：请提供代币合约地址。  
    （调用 `ask_human_via_console` 询问 `token_contract_address`）  
    （直到收集完所有必要信息，才调用相应的函数）

    如果一轮无法获取到所有必要信息，则继续询问，直到获取到所有必要信息。

    ============================================
    🛡️ 所有交易类操作必须二次确认（Confirm Loop）
    ============================================
    所有涉及链上写入的交易操作（如 `erc20_approve`、`erc20_transfer_from`）在参数补全完成后，**必须通过 `ask_human_via_console` 向用户确认是否执行该操作。**

    - 示例流程：

    **Approve 操作示例：**
    1. 补全参数：`private_key`, `spender_address`, `token_contract_address`, `amount`
    2. 然后提示：  
        “你即将授权 `{spender_address}` 使用 `{amount}` 个代币，是否确认执行该操作？”
    3. 调用 `ask_human_via_console` 提问：请回复 `是` 继续，或 `否` 取消操作。
    4. 若用户回复“是”则继续执行；否则终止并提示“已取消授权操作”。

    **TransferFrom 操作示例：**
    1. 补全参数：`private_key`, `from_address`, `to_address`, `token_contract_address`, `amount`
    2. 然后提示：  
        “你即将从 `{from_address}` 向 `{to_address}` 转移 `{amount}` 个代币，是否确认执行该转账？”
    3. 调用 `ask_human_via_console` 提问：请回复 `是` 继续，或 `否` 取消操作。
    4. 若用户回复“是”则继续执行；否则终止并提示“已取消转账操作”。

    =================
    💬 交互与提醒
    =================
    - 若用户未提供必要信息，必须通过 `ask_human_via_console` 主动引导补全。
    - 查询类操作至少需要提供地址，若涉及 ERC20，需包含合约地址。
    - 所有链上写入操作必须先确认，方可执行。
    - 若涉及私钥（如交易类操作），必须提醒用户注意安全，**不建议明文传播私钥**，应使用环境变量或签名工具传递。
    - 所有操作仅限 IoTeX 测试网。
    """,
    model=model,
    token_limit=32768,
    tools=[*IotexTokenToolkit(estnet_rpc, ERC20_ABI, chain_id).get_tools(),
           *HumanToolkit().get_tools()],
    output_language="zh"
)
# print(iotex_agent.tool_dict)
# response = iotex_agent.step("帮我查询一下ERC20代币的余额。")
response = iotex_agent.step("帮我查询一下IOTX主币的余额。")
# response = iotex_agent.step("帮我查询一下ERC20代币的余额和IOTX主币的余额。")
# response = iotex_agent.step("帮我查询一下我对于0xf874871Bc0f99a06b5327F34AceAa80Ae71905DE地址的ERC20代币的授权额度。")
# response = iotex_agent.step("帮我查询一下合约地址为0xD3286E20Ff71438D9f6969828F7218af4A375e2f的ERC20代币的合约信息。")
# response = iotex_agent.step("我想给0xf874871Bc0f99a06b5327F34AceAa80Ae71905DE地址授权2个代币，请帮我执行该操作。")
# response = iotex_agent.step("我想给0xf874871Bc0f99a06b5327F34AceAa80Ae71905DE地址转账1个代币，请帮我执行该操作。")
print(response.info['tool_calls'][0].result)
print("----------------------------------------------")
print(response.msgs[0].content)
print("----------------------------------------------")
print(response)