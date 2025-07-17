const { ethers, network } = require("hardhat");

async function main() {
  // 获取网络信息
  const chainId = network.config.chainId;
  const networkName = network.name;
  
  console.log(`🚀 Deploying PolyAgentToken to ${networkName} (chainId: ${chainId})`);

  // 获取部署者账户（从 hardhat.config.js 配置中自动获取）
  const [deployer] = await ethers.getSigners();
  const balance = await ethers.provider.getBalance(deployer.address);
  
  console.log("Deployer:", deployer.address);
  console.log("Balance:", ethers.formatEther(balance), "ETH");

  // 代币配置（从环境变量或默认值）
  const name = process.env.TOKEN_NAME || "PolyAgent Token";
  const symbol = process.env.TOKEN_SYMBOL || "PAT";
  const initialSupply = process.env.TOKEN_INITIAL_SUPPLY || "1000000";
  const maxSupply = process.env.TOKEN_MAX_SUPPLY || "10000000";

  // 部署合约
  console.log("\nDeploying contract...");
  const PolyAgentToken = await ethers.getContractFactory("PolyAgentToken");
  const token = await PolyAgentToken.deploy(
    name,
    symbol,
    initialSupply,
    maxSupply,
    deployer.address
  );

  await token.waitForDeployment();
  const address = await token.getAddress();

  console.log("✅ PolyAgentToken deployed to:", address);
  
  // 获取浏览器链接
  const explorerUrl = getExplorerUrl(chainId, address);
  if (explorerUrl) {
    console.log("🔗 Explorer:", explorerUrl);
  }

  // 验证合约信息
  const totalSupply = await token.totalSupply();
  const decimals = await token.decimals();
  
  console.log("\nContract Info:");
  console.log("- Name:", await token.name());
  console.log("- Symbol:", await token.symbol());
  console.log("- Total Supply:", ethers.formatUnits(totalSupply, decimals));
  console.log("- Owner:", await token.owner());

  // 保存部署信息
  const deploymentInfo = {
    network: networkName,
    chainId,
    address,
    deployer: deployer.address,
    timestamp: new Date().toISOString(),
    txHash: token.deploymentTransaction()?.hash
  };

  require("fs").writeFileSync(
    `deployments/${networkName}.json`,
    JSON.stringify(deploymentInfo, null, 2)
  );

  console.log(`\n💾 Deployment info saved to deployments/${networkName}.json`);
  return token;
}

function getExplorerUrl(chainId, address) {
  const explorers = {
    4690: `https://testnet.iotexscan.io/address/${address}`, // IoTeX Testnet
    4689: `https://iotexscan.io/address/${address}`,         // IoTeX Mainnet
    1: `https://etherscan.io/address/${address}`,            // Ethereum Mainnet
    11155111: `https://sepolia.etherscan.io/address/${address}` // Sepolia Testnet
  };
  return explorers[chainId];
}

// 如果直接运行此脚本
if (require.main === module) {
  main()
    .then(() => process.exit(0))
    .catch((error) => {
      console.error("❌ 部署失败:", error);
      process.exit(1);
    });
}

module.exports = main;
