from eth_account import Account

# 创建 sender 钱包
sender_acct = Account.create()
sender_private_key = sender_acct.key.hex()
sender_address = sender_acct.address

# 创建 spender 钱包
spender_acct = Account.create()
spender_private_key = spender_acct.key.hex()
spender_address = spender_acct.address

print("Sender Address:", sender_address)
print("Sender Private Key:", sender_private_key)
print("Spender Address:", spender_address)
print("Spender Private Key:", spender_private_key)