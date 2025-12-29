import { useState } from 'react'
import './LoginPage.css'

interface LoginPageProps {
  onSignUp: () => void
  onLoginSuccess?: () => void
}

const LoginPage = ({ onSignUp, onLoginSuccess }: LoginPageProps) => {
  const [emailOrPhone, setEmailOrPhone] = useState('')
  const [password, setPassword] = useState('')

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault()
    // Login logic here
    if (onLoginSuccess) {
      onLoginSuccess()
    }
  }

  return (
    <div className="login-container">
      <div className="logo-container">
        <div className="logo">
          <img src="/logo.png" alt="AI Logo" width="60" height="60" />
        </div>
      </div>

      <div className="login-card">
        <h1 className="title">
          Decentralized P2P<br />
          User Agent Network
        </h1>
        <p className="description">
          Your autonomous AI agent directly connecting and interacting with other user agents without centralized online platforms
        </p>

        <form onSubmit={handleLogin} className="login-form">
          <div className="input-group">
            <input
              type="text"
              placeholder="Email or Phone Number"
              value={emailOrPhone}
              onChange={(e) => setEmailOrPhone(e.target.value)}
              className="input-field"
            />
          </div>

          <div className="input-group">
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field"
            />
          </div>

          <button type="submit" className="btn-login">
            Login
          </button>

          <button type="button" onClick={onSignUp} className="btn-signup">
            Sign up
          </button>
        </form>
      </div>
    </div>
  )
}

export default LoginPage

