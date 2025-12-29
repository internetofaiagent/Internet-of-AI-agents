import { useState, useEffect } from 'react'
import './ChatPage.css'

interface ChatPageProps {
  onBack: () => void
}

const ChatPage = ({ onBack }: ChatPageProps) => {
  const [inputValue, setInputValue] = useState('')
  const [showProductRecommendation, setShowProductRecommendation] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => {
      setShowProductRecommendation(true)
    }, 5000)

    return () => clearTimeout(timer)
  }, [])

  const handleStop = () => {
    // Stop logic here
  }

  const handleNewChat = () => {
    // New chat logic here
  }

  const handleOtherChoices = () => {
    // Other choices logic here
  }

  const handleViewDetail = () => {
    // View detail logic here
  }

  const handleOrder = () => {
    // Order logic here
  }

  return (
    <div className="chatpage-container">
      {/* Header Navigation */}
      <header className="header">
        <button onClick={onBack} className="back-button-header">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 15L7 10L12 5" stroke="#000" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
        <nav className="nav">
          <a href="#" className="nav-link active">Home</a>
          <a href="#" className="nav-link">Agents</a>
          <a href="#" className="nav-link">Order</a>
          <a href="#" className="nav-link">OPC</a>
        </nav>
        <div className="user-profile">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="16" cy="12" r="6" stroke="#666" strokeWidth="2" fill="none"/>
            <path d="M4 28c0-6.627 5.373-12 12-12s12 5.373 12 12" stroke="#666" strokeWidth="2" strokeLinecap="round"/>
          </svg>
        </div>
      </header>

      {/* Chat Content */}
      <main className="chat-content">
        <div className="chat-messages">
          <div className="message user-message">
            <div className="message-bubble user-bubble">
              What can I give to my friend John as Christmas gift?
            </div>
          </div>

          <div className="message assistant-message">
            {!showProductRecommendation ? (
              <div className="message-bubble assistant-bubble">
                Yes as Christmas is coming, and John is your good friend, giving him a Christmas gift is a good idea! Based on your budget and relationship with John, I think a <strong>Christmas tree</strong> could be a good choice! Let me search for the most suitable Christmas tree for you to buy. Feel free to stop me if you have any other ideas.
                
                <div className="search-status">
                  <div className="status-row">
                    <span className="status-text">find 38 agents...</span>
                    <span className="status-icon">*</span>
                    <span className="status-text">search for 249 items...</span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill"></div>
                  </div>
                  <div className="status-text">find and search for Holiday Essence seller agent...</div>
                </div>
              </div>
            ) : (
              <div className="product-recommendation">
                <div className="recommendation-text">
                  Yes as Christmas is coming, and John is your good friend, giving him a Christmas gift is a good idea! Based on your budget and relationship with John, I think a <strong>Christmas tree</strong> could be a good choice! We find and think this is maybe the most suitable for you to buy. Feel free to have a look and consider:
                </div>
                <div className="product-card">
                  <div className="product-image">
                    <img src="/1767011307409.jpg" alt="Christmas Tree" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '8px' }} />
                  </div>
                  <div className="product-details">
                    <h3 className="product-title">Christmas Tree, 4.5ft Premium Unlit Realistic Spruce Holiday Décor w/Dense Branches, Easy Assembly, Metal Base</h3>
                    <div className="product-header-row">
                      <div className="product-header-left">
                        <div className="product-price">$79.99</div>
                        <div className="product-rating">
                          <div className="stars-container">
                            <span className="star star-filled">★</span>
                            <span className="star star-filled">★</span>
                            <span className="star star-filled">★</span>
                            <span className="star star-filled">★</span>
                            <span className="star star-half">
                              <span className="star-outline">★</span>
                              <span className="star-fill">★</span>
                            </span>
                          </div>
                          <span className="rating-value">4.5</span>
                        </div>
                      </div>
                      <div className="seller-info">
                        <div className="seller-text">Directly bought from</div>
                        <div className="seller-logo-circle">
                          <img src="/1767011321984.jpg" alt="Holiday Essence" width="32" height="32" style={{ borderRadius: '50%', objectFit: 'cover' }} />
                        </div>
                        <div className="seller-text">Holiday Essence seller agent</div>
                      </div>
                    </div>
                    <div className="product-info-row">
                      <div className="shipping-info">
                        <div>Free delivery</div>
                        <div>3 days shipping time</div>
                        <div>7-day free return</div>
                      </div>
                      <div className="product-specs">
                        <div>Size: 6"D x 29"W x 48"H</div>
                        <div>Material: Polyvinyl Chloride</div>
                        <div>Weight: 1.59 Kilograms</div>
                      </div>
                    </div>
                    <div className="product-actions">
                      <button onClick={handleOtherChoices} className="btn-other">Other Choices</button>
                      <button onClick={handleViewDetail} className="btn-view">View Detail</button>
                      <button onClick={handleOrder} className="btn-order">Order &gt;</button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Footer Input Bar */}
      <footer className="chat-footer">
        <div className="footer-left">History</div>
        <div className="footer-center">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="footer-mic">
            <path d="M12 1C10.34 1 9 2.34 9 4V12C9 13.66 10.34 15 12 15C13.66 15 15 13.66 15 12V4C15 2.34 13.66 1 12 1Z" stroke="#666" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M19 10V12C19 16.42 15.42 20 11 20M11 20V24M11 20H7" stroke="#666" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <input
            type="text"
            placeholder=""
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            className="footer-input"
          />
        </div>
        <div className="footer-right">
          <button onClick={handleStop} className="btn-stop">Stop</button>
          <button onClick={handleNewChat} className="btn-new">+ New</button>
        </div>
      </footer>
    </div>
  )
}

export default ChatPage

