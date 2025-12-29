import { useState } from 'react'
import './HomePage.css'

interface HomePageProps {
  onStartChat?: () => void
}

const HomePage = ({ onStartChat }: HomePageProps) => {
  const [inputValue, setInputValue] = useState('')

  const handleStart = () => {
    if (onStartChat) {
      onStartChat()
    }
  }

  return (
    <div className="homepage-container">
      {/* Header Navigation */}
      <header className="header">
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

      {/* Main AI Agent Section */}
      <main className="main-content">
        <div className="ai-agent-section">
          <h1 className="ai-title">Your AI agent is ready!</h1>
          <p className="ai-subtitle">Feel free to inform your demand and raise any request</p>
          <div className="ai-input-container">
            <div className="ai-input-icons">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="icon-mic">
                <path d="M12 1C10.34 1 9 2.34 9 4V12C9 13.66 10.34 15 12 15C13.66 15 15 13.66 15 12V4C15 2.34 13.66 1 12 1Z" stroke="#666" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M19 10V12C19 16.42 15.42 20 11 20M11 20V24M11 20H7" stroke="#666" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <input
              type="text"
              placeholder="What would you like to do?"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              className="ai-input"
            />
            <button onClick={handleStart} className="btn-start">Start</button>
          </div>
        </div>

        {/* Recommendation Section */}
        <section className="recommendation-section">
          <h2 className="section-title">Recommendation</h2>
          <div className="recommendation-cards">
            <div className="recommendation-card">
              <div className="card-icon">
                <img src="/fly.jpg" alt="Flight" width="40" height="40" style={{ objectFit: 'contain' }} />
              </div>
              <div className="card-content">
                <h3 className="card-title">Book return fare ticket</h3>
                <p className="card-description">based on the onward air ticket you ordered</p>
              </div>
            </div>

            <div className="recommendation-card">
              <div className="card-icon avatar-icon">
                <img src="/resume.jpg" alt="Podcast" width="40" height="40" style={{ borderRadius: '50%', objectFit: 'cover' }} />
              </div>
              <div className="card-content">
                <h3 className="card-title">Listen to podcast of Wu</h3>
                <p className="card-description">based on your podcast play history and frequency</p>
              </div>
            </div>

            <div className="recommendation-card">
              <div className="card-icon">
                <img src="/shoe.jpg" alt="Shoes" width="40" height="40" style={{ objectFit: 'contain' }} />
              </div>
              <div className="card-content">
                <h3 className="card-title">Order winter new shoes</h3>
                <p className="card-description">based on your purchase history and season change</p>
              </div>
            </div>
          </div>
        </section>

        {/* Previous Tasks and Agents Section */}
        <div className="bottom-sections">
          {/* Previous Tasks */}
          <section className="previous-section">
            <h2 className="section-title">Previous Tasks</h2>
            <div className="task-list">
              <div className="task-item">
                <div className="task-icon">
                  <img src="/1766985723001.jpg" alt="Movie" width="48" height="48" style={{ objectFit: 'contain' }} />
                </div>
                <div className="task-content">
                  <h3 className="task-title">Watch Online streaming media</h3>
                  <p className="task-details">Zootopia, Avatar, Nezha, Frozen...</p>
                </div>
              </div>

              <div className="task-item">
                <div className="task-icon">
                  <img src="/1766985745558.jpg" alt="Hamburger" width="48" height="48" style={{ objectFit: 'contain' }} />
                </div>
                <div className="task-content">
                  <h3 className="task-title">Order dinner</h3>
                  <p className="task-details">Spicy diced chicken, egg fried rice...</p>
                </div>
              </div>

              <div className="task-item">
                <div className="task-icon">
                  <img src="/1766985752566.jpg" alt="Mighty Patch" width="48" height="48" style={{ objectFit: 'contain' }} />
                </div>
                <div className="task-content">
                  <h3 className="task-title">Buy a gift for your mom</h3>
                  <p className="task-details">Mighty Patch™ Original patch from Hero Cosmetics</p>
                </div>
              </div>
            </div>
          </section>

          {/* Previous Agents */}
          <section className="previous-section">
            <h2 className="section-title">Previous Agents</h2>
            <div className="agent-list">
              <div className="agent-item">
                <div className="agent-avatar">
                  <img src="/1766985757167.jpg" alt="Li Nan" width="48" height="48" style={{ borderRadius: '50%', objectFit: 'cover' }} />
                </div>
                <div className="agent-content">
                  <h3 className="agent-title">Li Nan's music radio agent</h3>
                  <p className="agent-details">Love is Like a Tide, Toxic Perfume, Fairy Tale...</p>
                </div>
              </div>

              <div className="agent-item">
                <div className="agent-avatar">
                  <img src="/1766985752566.jpg" alt="Spring Airlines" width="48" height="48" style={{ borderRadius: '8px', objectFit: 'cover', backgroundColor: '#4caf50' }} />
                </div>
                <div className="agent-content">
                  <h3 className="agent-title">Spring Airlines</h3>
                  <p className="agent-details">20% discount flight from Shenzhen to Shanghai</p>
                </div>
              </div>

              <div className="agent-item">
                <div className="agent-avatar">
                  <img src="/1766985761436.jpg" alt="AIGC Avatar" width="48" height="48" style={{ borderRadius: '50%', objectFit: 'cover' }} />
                </div>
                <div className="agent-content">
                  <h3 className="agent-title">AIGC digital avatar agent</h3>
                  <p className="agent-details">Ads generation, Voice actor, Film stunt doubl...</p>
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}

export default HomePage

