import { useState, useEffect } from 'react'
import './App.css'
import SearchIcon from './assets/mag.png'
import { Emotion } from './types'
import Chat from './Chat'

function App(): JSX.Element {
  const [useLlm, setUseLlm] = useState<boolean | null>(null)
  const [searchValue, setSearchValue] = useState("")
  const [emotions, setEmotions] = useState<Emotion[]>([])

  useEffect(() => {
    fetch('/api/config').then(r => r.json()).then(data => setUseLlm(data.use_llm))
  }, [])

  const handleSearch = async (event: React.KeyboardEvent<HTMLInputElement>): Promise<void> => {
    if (event.key == "Enter") {
      const response = await fetch(`/api/movies?title=${encodeURIComponent(searchValue)}`)
      const data: Emotion[] = await response.json()
      data.sort(function(emotion1, emotion2){return emotion2.strength - emotion1.strength})
      setEmotions(data)
    }
  }

  if (useLlm === null) return <></>

  return (
    <div className={`full-body-container ${useLlm ? 'llm-mode' : ''}`}>
      {/* Search bar (always shown) */}
      <div className="top-text">
        <div className="google-colors">
          <h1 id="google-4">4</h1>
          <h1 id="google-3">3</h1>
          <h1 id="google-0-1">0</h1>
          <h1 id="google-0-2">0</h1>
        </div>
        <div className="input-box" onClick={() => document.getElementById('search-input')?.focus()}>
          <img src={SearchIcon} alt="search" />
          <input
            id="search-input"
            placeholder="Search for a Keeping up with the Kardashians episode"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            onKeyDown={handleSearch}
          />
        </div>
      </div>

      {/* Search results (always shown) */}
      <div id="answer-box">
        {emotions.map((emotion, index) => (
          <div key={index} className="episode-item">
            <h3 className="episode-title">{emotion.label}</h3>
            <p className="episode-desc">{emotion.strength}</p>
          </div>
        ))}
      </div>

      {/* Chat (only when USE_LLM = True in routes.py) */}
      {/*useLlm && <Chat onSearchTerm={handleSearch} />*/}
    </div>
  )
}

export default App
