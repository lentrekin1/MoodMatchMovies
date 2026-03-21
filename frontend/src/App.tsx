import { useState, useEffect } from 'react'
import './App.css'
import SearchIcon from './assets/mag.png'
import { Movie } from './types'
import Chat from './Chat'

function App(): JSX.Element {
  const [useLlm, setUseLlm] = useState<boolean | null>(null)
  const [searchValue, setSearchValue] = useState("")
  const [pool, setPool] = useState("all")
  const [movies, setMovies] = useState<Movie[]>([])

  useEffect(() => {
    fetch('/api/config').then(r => r.json()).then(data => setUseLlm(data.use_llm))
  }, [])

  const handleSearch = async (event: React.KeyboardEvent<HTMLInputElement>): Promise<void> => {
    if (event.key == "Enter") {
      const response = await fetch(`/api/movies?title=${encodeURIComponent(searchValue)}&pool=${pool}`)
      const data: Movie[] = await response.json()
      setMovies(data)
    }
  }

  if (useLlm === null) return <></>

  return (
    <div className={`full-body-container ${useLlm ? 'llm-mode' : ''}`}>
      {/* Search bar (always shown) */}
      <div className="top-text">
        <div className="google-colors">
          <h1 id="google-4">Mood</h1>
          <h1 id="google-3">Match</h1>
          <h1 id="google-0-1">Movies</h1>
          <h1 id="google-0-2">!</h1>
        </div>
        <div className="input-box" onClick={() => document.getElementById('search-input')?.focus()}>
          <img src={SearchIcon} alt="search" />
          <input
            id="search-input"
            placeholder="Tell us the vibe your feeling"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            onKeyDown={handleSearch}
          />
          <select value={pool} onChange={(e) => setPool(e.target.value)} onClick={(e) => e.stopPropagation()}>
            <option value="all">IMDB + RT + Letterboxd</option>
            <option value="top1000">RT + Letterboxd</option>
            <option value="top250">Letterboxd only</option>
          </select>
        </div>
      </div>

      {/* Search results (always shown) */}
      <div id="answer-box">
        {movies.map((movie, index) => (
          <div key={index} className="episode-item">
            <h3 className="episode-title">{movie.title}</h3>
            <p className="episode-desc">{movie.source} — {movie.score.toFixed(2)}</p>
          </div>
        ))}
      </div>

      {/* Chat (only when USE_LLM = True in routes.py) */}
      {/*useLlm && <Chat onSearchTerm={handleSearch} />*/}
    </div>
  )
}

export default App
