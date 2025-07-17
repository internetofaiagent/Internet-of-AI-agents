from camel.toolkits.base import BaseToolkit
from camel.toolkits.function_tool import FunctionTool

from typing import List, Dict
import requests
import json
from eth_account import Account
from web3 import Web3
import time

class IotexTokenToolkit(BaseToolkit):
    def __init__(self, rpc_url: str, erc20_abi: list, chain_id: int):
        """
        Initializes the toolkit with a given RPC URL and ERC20 ABI.

        Args:
            rpc_url (str): The RPC URL for the IoTeX testnet
            erc20_abi (list): The ABI definition for the ERC20 contract
        """
        self.rpc_url = rpc_url
        self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.erc20_abi = erc20_abi
        self.chain_id = chain_id

    def erc20_balance(self, token_contract_address: str, wallet_address: str, decimals: int = 18) -> dict:
        """
        Queries the ERC20 token balance of a specified wallet address.

        Args:
            token_contract_address (str): The ERC20 token contract address
            wallet_address (str): The wallet address to query
            decimals (int, optional): Token decimals (default is 18)

        Returns:
            dict: A dictionary containing balance information.
        """
        try:
            if not self.web3.is_connected():
                return {
                    'success': False,
                    'error': 'Unable to connect to IoTeX testnet'
                }

            contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(token_contract_address),
                abi=self.erc20_abi
            )

            balance_wei = contract.functions.balanceOf(
                self.web3.to_checksum_address(wallet_address)
            ).call()

            balance_tokens = balance_wei / (10 ** decimals)

            return {
                'success': True,
                'balance_wei': balance_wei,
                'balance_tokens': balance_tokens,
                'wallet_address': wallet_address,
                'contract_address': token_contract_address,
                'decimals': decimals
            }

        except Exception as e:
            return {
                'success': False,
                'wallet_address': wallet_address,
                'contract_address': token_contract_address,
                'error': f"Failed to query balance: {str(e)}"
            }

    def iotex_balance(self, wallet_address: str) -> dict:
        """
        Queries the IOTX (native coin) balance of a specified wallet address.

        Args:
            wallet_address (str): The wallet address to query

        Returns:
            dict: A dictionary containing balance information.
        """
        try:
            if not self.web3.is_connected():
                return {
                    'success': False,
                    'error': 'Unable to connect to IoTeX testnet'
                }

            balance_wei = self.web3.eth.get_balance(
                self.web3.to_checksum_address(wallet_address)
            )

            balance_iotx = self.web3.from_wei(balance_wei, 'ether')

            return {
                'success': True,
                'balance_wei': balance_wei,
                'balance_iotx': float(balance_iotx),
                'wallet_address': wallet_address
            }

        except Exception as e:
            return {
                'success': False,
                'wallet_address': wallet_address,
                'error': f"Failed to query native balance: {str(e)}"
            }

    def erc20_allowance(
        self,
        token_contract_address: str,
        owner_address: str,
        spender_address: str,
        decimals: int = 18
    ) -> dict:
        """
        Queries the allowance of an ERC20 token for a given owner and spender.

        Args:
            token_contract_address (str): The address of the ERC20 token contract.
            owner_address (str): The address of the token owner.
            spender_address (str): The address authorized to spend tokens.
            decimals (int, optional): The number of decimals the token uses. Defaults to 18.

        Returns:
            dict: A dictionary containing allowance information.
        """
        try:
            if not self.web3.is_connected():
                return {
                    'success': False,
                    'error': 'Unable to connect to IoTeX testnet'
                }

            contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(token_contract_address),
                abi=self.erc20_abi
            )

            allowance_wei = contract.functions.allowance(
                self.web3.to_checksum_address(owner_address),
                self.web3.to_checksum_address(spender_address)
            ).call()

            allowance_tokens = allowance_wei / (10 ** decimals)

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
            return {
                'success': False,
                'owner_address': owner_address,
                'spender_address': spender_address,
                'contract_address': token_contract_address,
                'error': f"Failed to query token allowance: {str(e)}"
            }

    def erc20_contract_info(self, token_contract_address: str) -> dict:
        """
        Queries the basic information of an ERC20 token contract.

        Args:
            token_contract_address (str): The ERC20 token contract address

        Returns:
            dict: A dictionary containing contract information.
        """
        try:
            if not self.web3.is_connected():
                return {
                    'success': False,
                    'error': 'Unable to connect to IoTeX testnet'
                }

            # Extended ABI to ensure required methods exist
            extended_abi = self.erc20_abi +[
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
            contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(token_contract_address),
                abi=extended_abi
            )
  
            name = "N/A"
            symbol = "N/A"
            decimals = 18
            total_supply_wei = 0

            try:
                name = contract.functions.name().call()
            except:
                name = "N/A"

            try:
                symbol = contract.functions.symbol().call()
            except:
                symbol = "N/A"

            try:
                decimals = contract.functions.decimals().call()
            except:
                decimals = 18

            try:
                total_supply_wei = contract.functions.totalSupply().call()
            except:
                total_supply_wei = 0

            total_supply_tokens = total_supply_wei / (10 ** decimals)

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
            return {
                'success': False,
                'contract_address': token_contract_address,
                'error': f"Failed to query contract info: {str(e)}"
            }

    def erc20_approve(
        self,
        private_key: str,
        token_contract_address: str,
        spender_address: str,
        amount: float,
        decimals: int = 18
    ) -> dict:
        """
        Executes an ERC20 `approve` operation to authorize a spender to use tokens.

        Args:
            private_key (str): Owner's private key (with or without '0x' prefix).
            token_contract_address (str): ERC20 token contract address.
            spender_address (str): Address to be approved for spending tokens.
            amount (float): Token amount to approve (in human-readable format).
            decimals (int): Number of decimal places the token uses (default is 18).

        Returns:
            dict: Result of the approval transaction, including transaction hash,
                block number, gas used, and a success or error message.
        """
        try:
            # Ensure private key starts with '0x'
            if not private_key.startswith("0x"):
                private_key = "0x" + private_key

            # Derive the account object from the private key
            account = Account.from_key(private_key)
            owner_address = account.address

            # Check if web3 is connected to the network
            if not self.web3.is_connected():
                return {"success": False, "error": "Unable to connect to IoTeX testnet"}

            # Load ERC20 contract instance
            contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(token_contract_address),
                abi=self.erc20_abi
            )

            # Convert human-readable amount to smallest unit (wei)
            amount_wei = int(amount * (10 ** decimals))

            # Get the current nonce for the transaction
            nonce = self.web3.eth.get_transaction_count(owner_address)

            # Build the approve transaction
            approve_txn = contract.functions.approve(
                self.web3.to_checksum_address(spender_address),
                amount_wei
            ).build_transaction({
                "chainId": self.chain_id,
                "gas": 100000,
                "gasPrice": self.web3.eth.gas_price,
                "nonce": nonce,
            })

            # Sign the transaction
            signed_txn = self.web3.eth.account.sign_transaction(approve_txn, private_key)

            # Broadcast the transaction to the network - Compatible with both old and new web3.py versions
            raw_transaction = getattr(signed_txn, 'rawTransaction', getattr(signed_txn, 'raw_transaction', None))
            if raw_transaction is None:
                return {"success": False, "error": "Failed to get raw transaction data"}
            tx_hash = self.web3.eth.send_raw_transaction(raw_transaction)
            tx_hash_hex = tx_hash.hex()

            # Wait for the transaction to be mined
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

            # Check transaction status
            if receipt.status == 1:
                return {
                    "success": True,
                    "message": "✅ Approve transaction succeeded.",
                    "transaction_hash": tx_hash_hex,
                    "block_number": receipt.blockNumber,
                    "gas_used": receipt.gasUsed,
                    "owner_address": owner_address,
                    "spender_address": spender_address,
                    "amount_tokens": amount,
                    "explorer_url": f"https://testnet.iotexscan.io/tx/{tx_hash_hex}"
                }
            else:
                return {
                    "success": False,
                    "message": "❌ Approve transaction failed.",
                    "transaction_hash": tx_hash_hex
                }

        except ValueError as ve:
            return {"success": False, "error": f"Invalid input: {str(ve)}"}
        except Exception as e:
            return {"success": False, "error": f"Approve operation failed: {str(e)}"}

    def erc20_transfer_from(
        self,
        private_key: str,
        token_contract_address: str,
        from_address: str,
        to_address: str,
        amount: float,
        decimals: int = 18
    ) -> Dict:
        """
        Executes ERC20 transferFrom operation.

        Args:
            private_key (str): Private key of the spender (who has approval to transfer tokens)
            token_contract_address (str): ERC20 token contract address
            from_address (str): Source token owner address
            to_address (str): Destination address
            amount (float): Amount of tokens to transfer (human-readable)
            decimals (int): Token decimal precision (default 18)

        Returns:
            dict: Result including transaction hash or error message
        """
        try:
            if not private_key.startswith("0x"):
                private_key = "0x" + private_key

            account = Account.from_key(private_key)
            spender_address = account.address

            print(f"Spender address (caller): {spender_address}")
            print(f"Transfer from: {from_address}")
            print(f"Transfer to: {to_address}")
            print(f"Amount: {amount}")
            print(f"Token contract address: {token_contract_address}")

            if not self.web3.is_connected():
                return {"success": False, "error": "Unable to connect to IoTeX testnet"}

            contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(token_contract_address),
                abi=self.erc20_abi
            )

            amount_wei = int(amount * (10 ** decimals))

            try:
                allowance = contract.functions.allowance(
                    self.web3.to_checksum_address(from_address),
                    self.web3.to_checksum_address(spender_address)
                ).call()
                allowance_tokens = allowance / (10 ** decimals)

                print(f"Current allowance: {allowance_tokens} tokens")

                if allowance < amount_wei:
                    return {
                        "success": False,
                        "error": f"Insufficient allowance. Current: {allowance_tokens}, Required: {amount}"
                    }
            except Exception as e:
                print(f"Warning: Failed to check allowance - {str(e)}")

            nonce = self.web3.eth.get_transaction_count(spender_address)

            transfer_txn = contract.functions.transferFrom(
                self.web3.to_checksum_address(from_address),
                self.web3.to_checksum_address(to_address),
                amount_wei
            ).build_transaction({
                'chainId': self.chain_id,
                'gas': 100000,
                'gasPrice': self.web3.eth.gas_price,
                'nonce': nonce,
            })

            print(f"Gas Price: {transfer_txn['gasPrice']} wei")
            print(f"Gas Limit: {transfer_txn['gas']}")

            signed_txn = self.web3.eth.account.sign_transaction(transfer_txn, private_key)
            # Compatible with both old and new web3.py versions
            raw_transaction = getattr(signed_txn, 'rawTransaction', getattr(signed_txn, 'raw_transaction', None))
            if raw_transaction is None:
                return {"success": False, "error": "Failed to get raw transaction data for transfer"}
            tx_hash = self.web3.eth.send_raw_transaction(raw_transaction)
            tx_hash_hex = tx_hash.hex()

            print(f"TransferFrom transaction sent. Hash: {tx_hash_hex}")
            print("Waiting for transaction confirmation...")

            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

            if receipt.status == 1:
                return {
                    "success": True,
                    "message": "✅ TransferFrom succeeded!",
                    "transaction_hash": tx_hash_hex,
                    "block_number": receipt.blockNumber,
                    "gas_used": receipt.gasUsed,
                    "spender_address": spender_address,
                    "from_address": from_address,
                    "to_address": to_address,
                    "amount_tokens": amount,
                    "explorer_url": f"https://testnet.iotexscan.io/tx/{tx_hash_hex}"
                }
            else:
                return {
                    "success": False,
                    "message": "❌ TransferFrom transaction failed.",
                    "transaction_hash": tx_hash_hex
                }

        except ValueError as ve:
            return {"success": False, "error": f"Invalid parameter: {str(ve)}"}
        except Exception as e:
            return {"success": False, "error": f"TransferFrom failed: {str(e)}"}
        
    def get_tools(self) -> List[FunctionTool]:
        """
        Returns a list of FunctionTool objects representing the
        functions in the toolkit.
        """
        return [
            FunctionTool(self.erc20_balance),
            FunctionTool(self.iotex_balance),
            FunctionTool(self.erc20_allowance),
            FunctionTool(self.erc20_contract_info),
            FunctionTool(self.erc20_approve),
            FunctionTool(self.erc20_transfer_from)
        ]