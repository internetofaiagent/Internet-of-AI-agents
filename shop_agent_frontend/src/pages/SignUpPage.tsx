import { useState } from 'react'
import './SignUpPage.css'

interface SignUpPageProps {
  onBack: () => void
}

const SignUpPage = ({ onBack }: SignUpPageProps) => {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [verificationCode, setVerificationCode] = useState('')

  const handleSignUp = (e: React.FormEvent) => {
    e.preventDefault()
    // Sign up logic here
  }

  const handleGetVerificationCode = () => {
    // Get verification code logic here
  }

  return (
    <div className="signup-container">
      <div className="logo-container">
        <div className="logo">
          <img src="/logo.png" alt="AI Logo" width="60" height="60" />
        </div>
      </div>

      <div className="signup-card">
        <div className="card-header">
          <button onClick={onBack} className="back-button">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 15L7 10L12 5" stroke="black" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
        <h1 className="title">Sign Up</h1>

        <p className="description">
          Start to have your autonomous AI agent and direct agent connection in our P2P user agent network
        </p>

        <form onSubmit={handleSignUp} className="signup-form">
          <div className="input-section">
            <label className="section-label">Text Field(s)</label>
            <div className="input-group-container">
              <div className="input-group">
                <input
                  type="text"
                  placeholder="Username:"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="input-field"
                />
              </div>

              <div className="input-group">
                <input
                  type="email"
                  placeholder="Email Address:"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-field"
                />
              </div>

              <div className="input-group">
                <input
                  type="tel"
                  placeholder="Phone Number:"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  className="input-field"
                />
              </div>

              <div className="input-group verification-group">
                <input
                  type="text"
                  placeholder="Verification Code:"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value)}
                  className="input-field verification-input"
                />
                <button
                  type="button"
                  onClick={handleGetVerificationCode}
                  className="btn-get-code"
                >
                  Get
                </button>
              </div>
            </div>
          </div>

          <button type="submit" className="btn-signup-primary">
            Sign Up
          </button>

          <button type="button" className="btn-signup-secondary">
            Sign up
          </button>
        </form>
      </div>
    </div>
  )
}

export default SignUpPage

