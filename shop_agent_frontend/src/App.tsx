import { useState } from 'react'
import LoginPage from './pages/LoginPage'
import SignUpPage from './pages/SignUpPage'
import HomePage from './pages/HomePage'
import ChatPage from './pages/ChatPage'

function App() {
  const [currentPage, setCurrentPage] = useState<'login' | 'signup' | 'home' | 'chat'>('login')

  const handleNavigateToSignUp = () => {
    setCurrentPage('signup')
  }

  const handleNavigateToLogin = () => {
    setCurrentPage('login')
  }

  const handleLoginSuccess = () => {
    setCurrentPage('home')
  }

  const handleStartChat = () => {
    setCurrentPage('chat')
  }

  const handleBackToHome = () => {
    setCurrentPage('home')
  }

  return (
    <>
      {currentPage === 'login' && <LoginPage onSignUp={handleNavigateToSignUp} onLoginSuccess={handleLoginSuccess} />}
      {currentPage === 'signup' && <SignUpPage onBack={handleNavigateToLogin} />}
      {currentPage === 'home' && <HomePage onStartChat={handleStartChat} />}
      {currentPage === 'chat' && <ChatPage onBack={handleBackToHome} />}
    </>
  )
}

export default App

