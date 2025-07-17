require("@nomicfoundation/hardhat-toolbox");
require("@openzeppelin/hardhat-upgrades");
require("dotenv").config();

// 自定义任务：查看账户余额
task("balance", "Prints an account's balance")
  .addParam("account", "The account's address")
  .setAction(async (taskArgs, hre) => {
    const balance = await hre.ethers.provider.getBalance(taskArgs.account);
    console.log(hre.ethers.formatEther(balance), "ETH");
  });

// 自定义任务：快速部署到测试网
task("deploy-testnet", "Deploy PolyAgentToken to testnet")
  .setAction(async (taskArgs, hre) => {
    await hre.run("run", { script: "scripts/deploy.js", network: "iotex_testnet" });
  });

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },
  networks: {
    hardhat: {
      chainId: 1337,
    },
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 1337,
    },
    iotex_testnet: {
      url: "https://babel-api.testnet.iotex.io",
      chainId: 4690,
      accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
      gasPrice: 1000000000000, // 1000 Gwei
      timeout: 60000,
    },
    iotex_mainnet: {
      url: "https://babel-api.mainnet.iotex.io",
      chainId: 4689,
      accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
      gasPrice: 1000000000000, // 1000 Gwei
      timeout: 60000,
    },
  },
  etherscan: {
    // IoTeX 暂不支持自动验证，可以手动在浏览器验证
    apiKey: {
      iotex_testnet: "dummy", // IoTeX 不需要 API key
      iotex_mainnet: "dummy",
    },
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
  mocha: {
    timeout: 40000,
  },
};
