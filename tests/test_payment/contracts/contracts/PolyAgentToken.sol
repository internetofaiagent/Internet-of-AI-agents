// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Pausable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";

/**
 * @title PolyAgentToken
 * @dev 基于OpenZeppelin的标准ERC20代币合约
 * 
 * 功能特性：
 * - 标准ERC20功能 (transfer, approve, transferFrom)
 * - 可燃烧代币 (burn, burnFrom)
 * - 可暂停功能 (pause/unpause)
 * - 所有权管理 (onlyOwner)
 * - EIP-2612 Permit功能 (无需预先approve的transferFrom)
 * - 铸造功能 (mint)
 * 
 * 安全特性：
 * - 基于OpenZeppelin经过审计的合约
 * - 所有权控制
 * - 暂停机制
 * - 重入攻击保护
 */
contract PolyAgentToken is ERC20, ERC20Burnable, ERC20Pausable, Ownable, ERC20Permit {
    
    // 最大供应量 (可选限制)
    uint256 public maxSupply;
    
    // 事件
    event MaxSupplyUpdated(uint256 newMaxSupply);
    event TokensMinted(address indexed to, uint256 amount);
    event EmergencyWithdraw(address indexed token, uint256 amount);
    
    /**
     * @dev 构造函数
     * @param _name 代币名称
     * @param _symbol 代币符号
     * @param _initialSupply 初始供应量 (不包含小数位)
     * @param _maxSupply 最大供应量 (不包含小数位，0表示无限制)
     * @param _initialOwner 初始所有者地址
     */
    constructor(
        string memory _name,
        string memory _symbol,
        uint256 _initialSupply,
        uint256 _maxSupply,
        address _initialOwner
    ) 
        ERC20(_name, _symbol) 
        Ownable(_initialOwner) 
        ERC20Permit(_name) 
    {
        require(_initialOwner != address(0), "PolyAgentToken: owner cannot be zero address");
        
        // 设置最大供应量
        maxSupply = _maxSupply * 10**decimals();
        
        // 铸造初始供应量给所有者
        if (_initialSupply > 0) {
            uint256 initialAmount = _initialSupply * 10**decimals();
            require(maxSupply == 0 || initialAmount <= maxSupply, "PolyAgentToken: initial supply exceeds max supply");
            _mint(_initialOwner, initialAmount);
            emit TokensMinted(_initialOwner, initialAmount);
        }
        
        emit MaxSupplyUpdated(maxSupply);
    }
    
    /**
     * @dev 铸造新代币 (仅所有者)
     * @param to 接收地址
     * @param amount 铸造数量 (包含小数位)
     */
    function mint(address to, uint256 amount) public onlyOwner {
        require(to != address(0), "PolyAgentToken: mint to zero address");
        require(amount > 0, "PolyAgentToken: mint amount must be greater than 0");
        
        // 检查最大供应量限制
        if (maxSupply > 0) {
            require(totalSupply() + amount <= maxSupply, "PolyAgentToken: mint would exceed max supply");
        }
        
        _mint(to, amount);
        emit TokensMinted(to, amount);
    }
    
    /**
     * @dev 批量铸造代币 (仅所有者)
     * @param recipients 接收地址数组
     * @param amounts 对应的铸造数量数组
     */
    function batchMint(address[] memory recipients, uint256[] memory amounts) public onlyOwner {
        require(recipients.length == amounts.length, "PolyAgentToken: arrays length mismatch");
        require(recipients.length > 0, "PolyAgentToken: empty arrays");
        
        uint256 totalAmount = 0;
        for (uint256 i = 0; i < amounts.length; i++) {
            totalAmount += amounts[i];
        }
        
        // 检查最大供应量限制
        if (maxSupply > 0) {
            require(totalSupply() + totalAmount <= maxSupply, "PolyAgentToken: batch mint would exceed max supply");
        }
        
        for (uint256 i = 0; i < recipients.length; i++) {
            require(recipients[i] != address(0), "PolyAgentToken: mint to zero address");
            require(amounts[i] > 0, "PolyAgentToken: mint amount must be greater than 0");
            _mint(recipients[i], amounts[i]);
            emit TokensMinted(recipients[i], amounts[i]);
        }
    }
    
    /**
     * @dev 暂停所有代币转移 (仅所有者)
     */
    function pause() public onlyOwner {
        _pause();
    }
    
    /**
     * @dev 恢复所有代币转移 (仅所有者)
     */
    function unpause() public onlyOwner {
        _unpause();
    }
    
    /**
     * @dev 更新最大供应量 (仅所有者)
     * @param _maxSupply 新的最大供应量 (包含小数位)
     */
    function updateMaxSupply(uint256 _maxSupply) public onlyOwner {
        require(_maxSupply == 0 || _maxSupply >= totalSupply(), "PolyAgentToken: max supply cannot be less than current supply");
        maxSupply = _maxSupply;
        emit MaxSupplyUpdated(_maxSupply);
    }
    
    /**
     * @dev 紧急提取意外发送到合约的ETH (仅所有者)
     */
    function emergencyWithdrawETH() public onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "PolyAgentToken: no ETH to withdraw");
        
        (bool success, ) = payable(owner()).call{value: balance}("");
        require(success, "PolyAgentToken: ETH withdrawal failed");
        
        emit EmergencyWithdraw(address(0), balance);
    }
    
    /**
     * @dev 紧急提取意外发送到合约的ERC20代币 (仅所有者)
     * @param token 代币合约地址
     */
    function emergencyWithdrawToken(address token) public onlyOwner {
        require(token != address(0), "PolyAgentToken: token address cannot be zero");
        require(token != address(this), "PolyAgentToken: cannot withdraw own tokens");
        
        IERC20 tokenContract = IERC20(token);
        uint256 balance = tokenContract.balanceOf(address(this));
        require(balance > 0, "PolyAgentToken: no tokens to withdraw");
        
        bool success = tokenContract.transfer(owner(), balance);
        require(success, "PolyAgentToken: token withdrawal failed");
        
        emit EmergencyWithdraw(token, balance);
    }
    
    /**
     * @dev 获取合约版本信息
     */
    function version() public pure returns (string memory) {
        return "1.0.0";
    }
    
    // 重写必要的函数以解决多重继承冲突
    function _update(address from, address to, uint256 value)
        internal
        override(ERC20, ERC20Pausable)
    {
        super._update(from, to, value);
    }
}
