# PolyAgent-Web3-AI-Agent-Interoperability-Protocol Windows 部署文档

## 系统要求

在开始部署之前，请确保您的 Windows 系统已安装以下依赖：

- **Python**: 3.8+ & <3.12
- **Node.js**: 16.0+
- **npm**: 8.0+
- **Git**: 最新版本

### 依赖安装检查

可以通过以下命令检查当前版本（在命令提示符或 PowerShell 中执行）：

```cmd
python --version
node --version
npm --version
git --version
```

如果缺少任何依赖，请先安装：

- **Python**: 通过 [Python官网](https://www.python.org/) 下载并安装
- **Node.js**: 通过 [Node.js官网](https://nodejs.org/) 下载并安装
- **Git**: 通过 [Git官网](https://git-scm.com/) 下载并安装

## 部署步骤

### 后端部署

#### 第一步：设置 Python 虚拟环境

1. 打开命令提示符（cmd）或 PowerShell
2. 导航到项目根目录（请替换为你的实际路径）：
   ```cmd
   cd D:\github_repository\PolyAgent-Web3-AI-Agent-Interoperability-Protocol
   ```

3. 创建 Python 虚拟环境：
   ```cmd
   python -m venv venv
   ```

4. 激活虚拟环境：
   - 如果使用命令提示符（cmd）：
     ```cmd
     venv\Scripts\activate
     ```
   - 如果使用 PowerShell：
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```

   激活成功后，命令行前会显示 `(venv)`

5. 安装 Python 依赖：
   ```cmd
   pip install -r requirements.txt
   ```

#### 第二步：启动后端服务
1. 确保虚拟环境已激活，激活agent
   cd AgentCore/Society
   python market_trade.py
   python market_monitor.py (不同终端窗口)

2.确保虚拟环境已激活，在同一个窗口输入：

```cmd
python app.py
```

如果启动成功，终端会显示类似以下的提示信息：
```
🧠 正在初始化AI模型...
✅ ModelScope Qwen 模型初始化成功。
🤖 正在加载AI Agents...
✅ AI Agents 已加载。
 * Running on http://127.0.0.1:5000
```

**注意**: warning 警告可以忽略，如果出现 error 错误说明有问题需要解决。

### 前端部署

#### 第一步：进入前端目录

后端成功启动后，打开新的命令提示符或 PowerShell 窗口，并进入前端目录：

```cmd
cd D:\github_repository\PolyAgent-Web3-AI-Agent-Interoperability-Protocol\frontEnd
```

#### 第二步：安装前端依赖

1. 如果您还没有安装 pnpm，请先全局安装：
   ```cmd
   npm install -g pnpm
   ```

2. 如果已经安装过 pnpm，在 frontEnd 目录下安装项目依赖：
   ```cmd
   pnpm install
   ```

#### 第三步：启动前端开发服务器

在 frontEnd 目录下运行：

```cmd
pnpm run dev
```

如果启动成功，终端会显示类似以下信息：
```
  VITE v6.3.5  ready in 1234 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

然后您可以：
- 按 `o + Enter` 自动在浏览器中打开应用
- 或手动访问显示的本地地址（通常是 http://localhost:5173/）

## 常见问题

### 1. Python 虚拟环境激活问题

如果 `venv\Scripts\activate` 或 `.\venv\Scripts\Activate.ps1` 命令失败，请确保：
- 虚拟环境目录创建成功
- 您在项目根目录下运行命令
- PowerShell 可能需要设置执行策略，管理员身份运行 PowerShell 并执行：
  ```powershell
  Set-ExecutionPolicy RemoteSigned
  ```

### 2. 权限问题

如果遇到权限问题，建议以管理员身份运行命令提示符或 PowerShell。

### 3. 端口冲突

- 后端默认使用端口 5000
- 前端默认使用端口 5173

如果端口被占用，您可以：
- 关闭占用端口的其他程序
- 或在启动时指定其他端口

### 4. 依赖安装失败

如果 Python 依赖安装失败，尝试：
```cmd
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果前端依赖安装失败，尝试：
```cmd
pnpm cache clean
pnpm install
```

## 停止服务

- **停止后端**: 在后端窗口中按 `Ctrl + C`
- **停止前端**: 在前端窗口中按 `Ctrl + C`
- **退出虚拟环境**: 输入 `deactivate`

## 下次启动

下次启动项目时：

1. 激活虚拟环境：
   ```cmd
   cd D:\github_repository\PolyAgent-Web3-AI-Agent-Interoperability-Protocol
   venv\Scripts\activate
   ```
2. 激活agent
   cd AgentCore/Society
   python market_trade.py
   python market_monitor.py (不同终端窗口)
3. 启动后端：
   ```cmd
   python app.py
   ```

4. 启动前端（新窗口）：
   ```cmd
   cd frontEnd
   pnpm run dev
   ```

---

**注意**: 请确保在开发过程中保持两个命令行窗口打开，一个运行后端服务，一个运行前端服务。