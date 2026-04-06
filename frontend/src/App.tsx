import { useState, useEffect } from 'react'
import './App.css'
import SearchIcon from './assets/mag.png'

type MovieResult = {
  title: string
  score: number
  source?: string
  genre?: string
  runtime?: string
  rtScore?: string | number
  imdbScore?: string | number
  letterboxdScore?: string | number
  releaseYear?: string | number
  moods?: string[]
  explanation?: string
}

function App() {
  const [useLlm, setUseLlm] = useState<boolean | null>(null)
  const [searchValue, setSearchValue] = useState('')
  const [movies, setMovies] = useState<MovieResult[]>([])
  const [loading, setLoading] = useState(false)

  const [sourceFilters, setSourceFilters] = useState<string[]>([])
  const [genreFilters, setGenreFilters] = useState<string[]>([])
  const [runtimeFilters, setRuntimeFilters] = useState<string[]>([])
  const [rtScoreFilters, setRtScoreFilters] = useState<string[]>([])
  const [imdbScoreFilters, setImdbScoreFilters] = useState<string[]>([])
  const [letterboxdScoreFilters, setLetterboxdScoreFilters] = useState<string[]>([])
  const [moodFilters, setMoodFilters] = useState<string[]>([])
  const [yearFilters, setYearFilters] = useState<string[]>([])

  useEffect(() => {
    fetch('/api/config')
      .then((r) => r.json())
      .then((data) => setUseLlm(data.use_llm))
      .catch(() => setUseLlm(false))
  }, [])

  const toggleFilter = (
    value: string,
    current: string[],
    setter: React.Dispatch<React.SetStateAction<string[]>>
  ) => {
    if (current.includes(value)) {
      setter(current.filter((item) => item !== value))
    } else {
      setter([...current, value])
    }
  }

  const handleSearch = async (
    event: React.KeyboardEvent<HTMLInputElement>
  ): Promise<void> => {
    if (event.key !== 'Enter') return

    const trimmedQuery = searchValue.trim()
    if (!trimmedQuery) return

    setLoading(true)

    try {
      const params = new URLSearchParams()
      params.append('title', trimmedQuery)

      sourceFilters.forEach((value) => params.append('source', value))
      genreFilters.forEach((value) => params.append('genre', value))
      runtimeFilters.forEach((value) => params.append('runtime', value))
      rtScoreFilters.forEach((value) => params.append('rtScore', value))
      imdbScoreFilters.forEach((value) => params.append('imdbScore', value))
      letterboxdScoreFilters.forEach((value) =>
        params.append('letterboxdScore', value)
      )
      moodFilters.forEach((value) => params.append('mood', value))
      yearFilters.forEach((value) => params.append('releaseYear', value))

      const response = await fetch(`/api/movies?${params.toString()}`)
      const data = await response.json()

      if (Array.isArray(data)) {
        const normalized: MovieResult[] = data.map((item: any) => ({
          title: item.title ?? item.name ?? 'Unknown Title',
          score:
            typeof item.score === 'number'
              ? item.score
              : typeof item.strength === 'number'
              ? item.strength
              : 0,
          source: item.source,
          genre: item.genre,
          runtime: item.runtime,
          rtScore: item.rtScore,
          imdbScore: item.imdbScore,
          letterboxdScore: item.letterboxdScore,
          releaseYear: item.releaseYear,
          moods: item.moods,
          explanation: item.explanation,
        }))

        normalized.sort((a, b) => b.score - a.score)
        setMovies(normalized)
      } else {
        setMovies([])
      }
    } catch (error) {
      console.error('Search failed:', error)
      setMovies([])
    } finally {
      setLoading(false)
    }
  }

  if (useLlm === null) return <></>

  return (
    <div className={`full-body-container ${useLlm ? 'llm-mode' : ''}`}>
      <div className="top-text">
        <div className="google-colors">
          <h1 id="google-4">Mood</h1>
          <h1 id="google-3">Match</h1>
          <h1 id="google-0-1">Movies</h1>
          <h1 id="google-0-2">!</h1>
        </div>

        <p className="subtitle">
          Describe the feeling or vibe you want, and we’ll suggest movies that
          match it.
        </p>
      </div>

      <div
        className="input-box"
        onClick={() => document.getElementById('search-input')?.focus()}
      >
        <img src={SearchIcon} alt="search" />
        <input
          id="search-input"
          placeholder="Tell us the vibe you're feeling"
          value={searchValue}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            setSearchValue(e.target.value)
          }
          onKeyDown={handleSearch}
        />
      </div>

      <div className="filter-panel">
        <details className="filter-dropdown">
          <summary>Source</summary>
          <div className="filter-options">
            <label>
              <input
                type="checkbox"
                checked={sourceFilters.includes('imdb')}
                onChange={() => toggleFilter('imdb', sourceFilters, setSourceFilters)}
              />
              IMDb
            </label>
            <label>
              <input
                type="checkbox"
                checked={sourceFilters.includes('rt')}
                onChange={() => toggleFilter('rt', sourceFilters, setSourceFilters)}
              />
              Rotten Tomatoes
            </label>
            <label>
              <input
                type="checkbox"
                checked={sourceFilters.includes('letterboxd')}
                onChange={() =>
                  toggleFilter('letterboxd', sourceFilters, setSourceFilters)
                }
              />
              Letterboxd
            </label>
          </div>
        </details>

        <details className="filter-dropdown">
          <summary>Genre</summary>
          <div className="filter-options">
            {[
              'Drama',
              'Comedy',
              'Thriller',
              'Romance',
              'Sci-Fi',
              'Animation',
              'Action',
              'Horror',
            ].map((genre) => (
              <label key={genre}>
                <input
                  type="checkbox"
                  checked={genreFilters.includes(genre)}
                  onChange={() => toggleFilter(genre, genreFilters, setGenreFilters)}
                />
                {genre}
              </label>
            ))}
          </div>
        </details>

        <details className="filter-dropdown">
          <summary>Runtime</summary>
          <div className="filter-options">
            <label>
              <input
                type="checkbox"
                checked={runtimeFilters.includes('under_90')}
                onChange={() =>
                  toggleFilter('under_90', runtimeFilters, setRuntimeFilters)
                }
              />
              Under 90 min
            </label>
            <label>
              <input
                type="checkbox"
                checked={runtimeFilters.includes('90_120')}
                onChange={() =>
                  toggleFilter('90_120', runtimeFilters, setRuntimeFilters)
                }
              />
              90–120 min
            </label>
            <label>
              <input
                type="checkbox"
                checked={runtimeFilters.includes('over_120')}
                onChange={() =>
                  toggleFilter('over_120', runtimeFilters, setRuntimeFilters)
                }
              />
              Over 120 min
            </label>
          </div>
        </details>

        <details className="filter-dropdown">
          <summary>Rotten Tomatoes</summary>
          <div className="filter-options">
            {['70', '80', '90'].map((score) => (
              <label key={score}>
                <input
                  type="checkbox"
                  checked={rtScoreFilters.includes(score)}
                  onChange={() =>
                    toggleFilter(score, rtScoreFilters, setRtScoreFilters)
                  }
                />
                {score}+
              </label>
            ))}
          </div>
        </details>

        <details className="filter-dropdown">
          <summary>IMDb Score</summary>
          <div className="filter-options">
            {['6.5', '7.0', '7.5', '8.0'].map((score) => (
              <label key={score}>
                <input
                  type="checkbox"
                  checked={imdbScoreFilters.includes(score)}
                  onChange={() =>
                    toggleFilter(score, imdbScoreFilters, setImdbScoreFilters)
                  }
                />
                {score}+
              </label>
            ))}
          </div>
        </details>

        <details className="filter-dropdown">
          <summary>Letterboxd Score</summary>
          <div className="filter-options">
            {['3.0', '3.5', '4.0', '4.5'].map((score) => (
              <label key={score}>
                <input
                  type="checkbox"
                  checked={letterboxdScoreFilters.includes(score)}
                  onChange={() =>
                    toggleFilter(
                      score,
                      letterboxdScoreFilters,
                      setLetterboxdScoreFilters
                    )
                  }
                />
                {score}+
              </label>
            ))}
          </div>
        </details>

        <details className="filter-dropdown">
          <summary>Mood / Emotion</summary>
          <div className="filter-options">
            {[
              'comforting',
              'dark',
              'funny',
              'heartwarming',
              'suspenseful',
              'thought-provoking',
              'sad',
              'uplifting',
              'tense',
              'romantic',
            ].map((mood) => (
              <label key={mood}>
                <input
                  type="checkbox"
                  checked={moodFilters.includes(mood)}
                  onChange={() =>
                    toggleFilter(mood, moodFilters, setMoodFilters)
                  }
                />
                {mood}
              </label>
            ))}
          </div>
        </details>

        <details className="filter-dropdown">
          <summary>Release Year</summary>
          <div className="filter-options">
            {[
              'before_1980',
              '1980s',
              '1990s',
              '2000s',
              '2010s',
              '2020s',
            ].map((yearBucket) => (
              <label key={yearBucket}>
                <input
                  type="checkbox"
                  checked={yearFilters.includes(yearBucket)}
                  onChange={() =>
                    toggleFilter(yearBucket, yearFilters, setYearFilters)
                  }
                />
                {yearBucket === 'before_1980'
                  ? 'Before 1980'
                  : yearBucket === '1980s'
                  ? '1980s'
                  : yearBucket === '1990s'
                  ? '1990s'
                  : yearBucket === '2000s'
                  ? '2000s'
                  : yearBucket === '2010s'
                  ? '2010s'
                  : '2020s'}
              </label>
            ))}
          </div>
        </details>
      </div>

      <div id="answer-box">
        {loading ? (
          <div className="empty-state">Searching for matching movies...</div>
        ) : movies.length === 0 ? (
          <div className="empty-state">
            Try a search like “dark psychological movie that makes me think” or
            “comforting movie for a rainy night.”
          </div>
        ) : (
          movies.map((movie, i) => (
            <div className="movie-item" key={`${movie.title}-${i}`}>
              <div className="movie-title-row">
                <h2 className="movie-title">{movie.title}</h2>
                <div className="movie-score">
                  Match {Math.round(movie.score * 100)}%
                </div>
              </div>

              <div className="movie-meta">
                {movie.source && (
                  <span className="movie-tag">
                    {movie.source.toUpperCase()}
                  </span>
                )}
                <span className="movie-tag">{movie.genre || 'Genre TBD'}</span>
                <span className="movie-tag">
                  {movie.runtime || 'Runtime TBD'}
                </span>
                <span className="movie-tag">
                  RT {movie.rtScore ?? 'TBD'}
                </span>
                <span className="movie-tag">
                  IMDb {movie.imdbScore ?? 'TBD'}
                </span>
                <span className="movie-tag">
                  Letterboxd {movie.letterboxdScore ?? 'TBD'}
                </span>
                <span className="movie-tag">
                  Year {movie.releaseYear ?? 'TBD'}
                </span>
                {movie.moods && movie.moods.length > 0 && (
                  <span className="movie-tag">
                    {movie.moods.slice(0, 2).join(', ')}
                  </span>
                )}
              </div>

              <p className="movie-desc">
                {movie.explanation ||
                  'A strong emotional match for your search based on our current retrieval model.'}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default App