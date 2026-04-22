import { useState, useEffect } from 'react'
import './App.css'
import SearchIcon from './assets/mag.png'

type EmotionScore = { label: string; score: number }

// Canonical label order — must match the backend EMOTION_LABELS list
const EMOTION_ORDER = [
    'amusement', 'anger', 'caring',
    'confusion', 'curiosity', 'desire', 'disgust',
    'embarrassment', 'excitement', 'fear', 'gratitude', 'grief', 'joy', 'love',
    'nervousness', 'optimism', 'pride', 'realization', 'remorse',
    'sadness', 'surprise'
]

function RadarChart({
  queryEmotions,
  movieEmotions,
}: {
  queryEmotions: EmotionScore[]
  movieEmotions: EmotionScore[]
}) {
  const N   = EMOTION_ORDER.length   // 21
  const vb  = 360
  const cx  = vb / 2
  const cy  = vb / 2
  const R   = 108   // data polygon radius
  const lR  = R + 16  // label anchor radius

  const movieMap = Object.fromEntries(movieEmotions.map((e) => [e.label, e.score]))
  const queryMap = Object.fromEntries(queryEmotions.map((e) => [e.label, e.score]))

  // Log scale so low-scoring dimensions aren't crushed near the centre
  const scale = (s: number) => Math.log1p(s * 9) / Math.log1p(9)

  const rad = (i: number) => (i / N) * 2 * Math.PI - Math.PI / 2
  const pt  = (i: number, s: number): [number, number] => [
    cx + R * scale(s) * Math.cos(rad(i)),
    cy + R * scale(s) * Math.sin(rad(i)),
  ]
  const poly = (scores: number[]) =>
    scores.map((s, i) => pt(i, s).join(',')).join(' ')

  const movieScores = EMOTION_ORDER.map((l) => movieMap[l] ?? 0)
  const queryScores = EMOTION_ORDER.map((l) => queryMap[l] ?? 0)
  const rings = [0.25, 0.5, 0.75, 1.0]

  return (
    <div className="radar-wrap">
      <svg viewBox={`0 0 ${vb} ${vb}`} className="radar-svg">
        {/* Grid rings */}
        {rings.map((r) => (
          <polygon
            key={r}
            points={EMOTION_ORDER.map((_, i) => pt(i, r).join(',')).join(' ')}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth="0.75"
          />
        ))}

        {/* Axis spokes */}
        {EMOTION_ORDER.map((_, i) => {
          const [x, y] = pt(i, 1)
          return (
            <line key={i} x1={cx} y1={cy} x2={x} y2={y}
              stroke="rgba(255,255,255,0.06)" strokeWidth="0.75" />
          )
        })}

        {/* Movie polygon */}
        <polygon points={poly(movieScores)}
          fill="rgba(110,231,183,0.14)" stroke="#6ee7b7"
          strokeWidth="1.5" strokeLinejoin="round" />

        {/* Query polygon (only when a mood query was used) */}
        {queryEmotions.length > 0 && (
          <polygon points={poly(queryScores)}
            fill="rgba(96,165,250,0.10)" stroke="#60a5fa"
            strokeWidth="1.5" strokeDasharray="3,2" strokeLinejoin="round" />
        )}

        {/* Rotated spoke labels */}
        {EMOTION_ORDER.map((label, i) => {
          const a   = rad(i)
          const lx  = cx + lR * Math.cos(a)
          const ly  = cy + lR * Math.sin(a)
          // degrees for SVG rotate(); flip left-half labels so they read outward
          const deg = (i / N) * 360 - 90
          const flip = Math.cos(a) < -0.05
          return (
            <text
              key={label}
              transform={`translate(${lx},${ly}) rotate(${flip ? deg + 180 : deg})`}
              textAnchor={flip ? 'end' : 'start'}
              dominantBaseline="middle"
              fontSize="6.8"
              fill="#64748b"
            >
              {label}
            </text>
          )
        })}
      </svg>

      <div className="radar-legend">
        <span className="legend-movie">&#9632; film</span>
        {queryEmotions.length > 0 && (
          <span className="legend-query">&#9632; your mood</span>
        )}
      </div>
    </div>
  )
}

type MovieResult = {
  title: string
  score: number
  tconst?: string
  genre?: string
  runtime?: number
  rtScore?: number | null
  imdbScore?: number | null
  releaseYear?: number | null
  explanation?: string
  plot?: string
  director?: string
  actors?: string
  emotions?: Array<{ label: string; score: number }>
}

const YEAR_MIN = 1924
const YEAR_MAX = 2025
const RUNTIME_MIN = 0
const RUNTIME_MAX = 240

function formatRuntime(mins: number): string {
  if (!mins) return ''
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function App() {
  const [useLlm, setUseLlm] = useState<boolean | null>(null)
  const [topicValue, setTopicValue] = useState('')
  const [moodValue, setMoodValue] = useState('')
  const [movies, setMovies] = useState<MovieResult[]>([])
  const [queryEmotions, setQueryEmotions] = useState<EmotionScore[]>([])
  const [selectedMovie, setSelectedMovie] = useState<MovieResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [filtersDirty, setFiltersDirty] = useState(false)

  // Pill filters
  const [genreFilters, setGenreFilters] = useState<string[]>([])

  // Range filters
  const [yearRange, setYearRange] = useState<[number, number]>([YEAR_MIN, YEAR_MAX])
  const [runtimeRange, setRuntimeRange] = useState<[number, number]>([RUNTIME_MIN, RUNTIME_MAX])
  const [rtMin, setRtMin] = useState(0)
  const [imdbMin, setImdbMin] = useState(0)

  const yearActive = yearRange[0] > YEAR_MIN || yearRange[1] < YEAR_MAX
  const runtimeActive = runtimeRange[0] > RUNTIME_MIN || runtimeRange[1] < RUNTIME_MAX
  const anyActiveFilters =
    genreFilters.length > 0 ||
    yearActive ||
    runtimeActive ||
    rtMin > 0 ||
    imdbMin > 0

  const clearAllFilters = () => {
    setGenreFilters([])
    setYearRange([YEAR_MIN, YEAR_MAX])
    setRuntimeRange([RUNTIME_MIN, RUNTIME_MAX])
    setRtMin(0)
    setImdbMin(0)
  }

  useEffect(() => {
    fetch('/api/config')
      .then((r) => r.json())
      .then((data) => setUseLlm(data.use_llm))
      .catch(() => setUseLlm(false))
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setSelectedMovie(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
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

  const doSearch = async (topic: string, mood: string): Promise<void> => {
    if (!topic.trim() && !mood.trim()) return
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (topic.trim()) params.append('topic', topic.trim())
      if (mood.trim()) params.append('title', mood.trim())
      genreFilters.forEach((v) => params.append('genre', v))
      if (yearRange[0] > YEAR_MIN) params.append('yearMin', String(yearRange[0]))
      if (yearRange[1] < YEAR_MAX) params.append('yearMax', String(yearRange[1]))
      if (runtimeRange[0] > RUNTIME_MIN) params.append('runtimeMin', String(runtimeRange[0]))
      if (runtimeRange[1] < RUNTIME_MAX) params.append('runtimeMax', String(runtimeRange[1]))
      if (rtMin > 0) params.append('rtMin', String(rtMin))
      if (imdbMin > 0) params.append('imdbMin', String(imdbMin))
      const response = await fetch(`/api/movies?${params.toString()}`)
      const data = await response.json()
      const rawResults = Array.isArray(data) ? data : (data.results ?? [])
      setQueryEmotions(Array.isArray(data) ? [] : (data.queryEmotions ?? []))
      if (rawResults.length > 0) {
        const normalized: MovieResult[] = rawResults.map((item: any) => ({
          title: item.title ?? 'Unknown Title',
          score: typeof item.score === 'number' ? item.score : 0,
          tconst: item.tconst,
          genre: item.genre,
          runtime: item.runtime,
          rtScore: item.rtScore,
          imdbScore: item.imdbScore,
          releaseYear: item.releaseYear,
          explanation: item.explanation,
          plot: item.plot ?? '',
          director: item.director ?? '',
          actors: item.actors ?? '',
          emotions: item.emotions ?? [],
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

  useEffect(() => {
    if (hasSearched) setFiltersDirty(true)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [genreFilters, yearRange, runtimeRange, rtMin, imdbMin])

  useEffect(() => {
    if (!topicValue.trim() && !moodValue.trim()) {
      setMovies([])
      setHasSearched(false)
      setFiltersDirty(false)
    }
  }, [topicValue, moodValue])

  const handleSearch = (event: React.KeyboardEvent<HTMLInputElement>): void => {
    if (event.key !== 'Enter') return
    if (!topicValue.trim() && !moodValue.trim()) {
      setMovies([])
      return
    }
    setHasSearched(true)
    setFiltersDirty(false)
    doSearch(topicValue, moodValue)
  }

  const handleApply = (): void => {
    setFiltersDirty(false)
    doSearch(topicValue, moodValue)
  }

  // Dual range fill percentages
  const yearLeftPct  = ((yearRange[0] - YEAR_MIN) / (YEAR_MAX - YEAR_MIN)) * 100
  const yearRightPct = ((yearRange[1] - YEAR_MIN) / (YEAR_MAX - YEAR_MIN)) * 100
  const rtLeftPct    = (runtimeRange[0] / RUNTIME_MAX) * 100
  const rtRightPct   = (runtimeRange[1] / RUNTIME_MAX) * 100

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
          Describe what it's about, how it should feel, or both.
        </p>
      </div>

      <div className="dual-search">
        <div className="dual-search-row">
          <span className="dual-search-label">about</span>
          <div
            className="input-box"
            onClick={() => document.getElementById('topic-input')?.focus()}
          >
            <img src={SearchIcon} alt="search" />
            <input
              id="topic-input"
              placeholder="heist, space travel, found family…"
              value={topicValue}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTopicValue(e.target.value)}
              onKeyDown={handleSearch}
            />
          </div>
        </div>
        <div className="dual-search-row">
          <span className="dual-search-label">feels like</span>
          <div
            className="input-box"
            onClick={() => document.getElementById('mood-input')?.focus()}
          >
            <img src={SearchIcon} alt="search" />
            <input
              id="mood-input"
              placeholder="dark and tense, warm and cozy…"
              value={moodValue}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMoodValue(e.target.value)}
              onKeyDown={handleSearch}
            />
          </div>
        </div>
      </div>

      <div className="filter-panel">
        {/* Genre — pills */}
        <div className="filter-row">
          <span className="filter-label">Genre</span>
          <div className="filter-pills">
            {['Drama', 'Comedy', 'Thriller', 'Romance', 'Sci-Fi', 'Animation', 'Action', 'Horror'].map(
              (g) => (
                <button
                  key={g}
                  className={`filter-pill${genreFilters.includes(g) ? ' active' : ''}`}
                  onClick={() => toggleFilter(g, genreFilters, setGenreFilters)}
                >
                  {g}
                </button>
              )
            )}
          </div>
        </div>

        {/* Year — dual range */}
        <div className="filter-row">
          <span className="filter-label">Year</span>
          <div className="range-control">
            <span className={`range-val${yearRange[0] > YEAR_MIN ? ' active' : ''}`}>{yearRange[0]}</span>
            <div className="range-track-wrap">
              <div className="range-track" />
              <div
                className="range-fill"
                style={{ left: `${yearLeftPct}%`, width: `${yearRightPct - yearLeftPct}%` }}
              />
              <input
                type="range"
                min={YEAR_MIN}
                max={YEAR_MAX}
                step={1}
                value={yearRange[0]}
                className={yearRange[0] >= yearRange[1] ? 'thumb-min on-top' : 'thumb-min'}
                onChange={(e) => {
                  const v = Math.min(Number(e.target.value), yearRange[1])
                  setYearRange([v, yearRange[1]])
                }}
              />
              <input
                type="range"
                min={YEAR_MIN}
                max={YEAR_MAX}
                step={1}
                value={yearRange[1]}
                className="thumb-max"
                onChange={(e) => {
                  const v = Math.max(Number(e.target.value), yearRange[0])
                  setYearRange([yearRange[0], v])
                }}
              />
            </div>
            <span className={`range-val${yearRange[1] < YEAR_MAX ? ' active' : ''}`}>
              {yearRange[1]}
            </span>
          </div>
        </div>

        {/* Runtime — dual range */}
        <div className="filter-row">
          <span className="filter-label">Runtime</span>
          <div className="range-control">
            <span className={`range-val${runtimeRange[0] > RUNTIME_MIN ? ' active' : ''}`}>
              {runtimeRange[0] === 0 ? 'Any' : formatRuntime(runtimeRange[0])}
            </span>
            <div className="range-track-wrap">
              <div className="range-track" />
              <div
                className="range-fill"
                style={{ left: `${rtLeftPct}%`, width: `${rtRightPct - rtLeftPct}%` }}
              />
              <input
                type="range"
                min={RUNTIME_MIN}
                max={RUNTIME_MAX}
                step={5}
                value={runtimeRange[0]}
                className={runtimeRange[0] >= runtimeRange[1] ? 'thumb-min on-top' : 'thumb-min'}
                onChange={(e) => {
                  const v = Math.min(Number(e.target.value), runtimeRange[1])
                  setRuntimeRange([v, runtimeRange[1]])
                }}
              />
              <input
                type="range"
                min={RUNTIME_MIN}
                max={RUNTIME_MAX}
                step={5}
                value={runtimeRange[1]}
                className="thumb-max"
                onChange={(e) => {
                  const v = Math.max(Number(e.target.value), runtimeRange[0])
                  setRuntimeRange([runtimeRange[0], v])
                }}
              />
            </div>
            <span className={`range-val${runtimeRange[1] < RUNTIME_MAX ? ' active' : ''}`}>
              {runtimeRange[1] === RUNTIME_MAX ? '4h+' : formatRuntime(runtimeRange[1])}
            </span>
          </div>
        </div>

        {/* RT Score — single min slider */}
        <div className="filter-row">
          <span className="filter-label">RT Score</span>
          <div className="range-control">
            <span className={`range-val single${rtMin > 0 ? ' active' : ''}`}>{rtMin > 0 ? `${rtMin}%+` : 'Any'}</span>
            <div className="range-track-wrap">
              <div className="range-track" />
              <div className="range-fill" style={{ left: 0, width: `${rtMin}%` }} />
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={rtMin}
                className="thumb-max"
                onChange={(e) => setRtMin(Number(e.target.value))}
              />
            </div>
          </div>
        </div>

        {/* IMDb Score — single min slider */}
        <div className="filter-row">
          <span className="filter-label">IMDb</span>
          <div className="range-control">
            <span className={`range-val single${imdbMin > 0 ? ' active' : ''}`}>{imdbMin > 0 ? `${imdbMin}+` : 'Any'}</span>
            <div className="range-track-wrap">
              <div className="range-track" />
              <div className="range-fill" style={{ left: 0, width: `${(imdbMin / 10) * 100}%` }} />
              <input
                type="range"
                min={0}
                max={10}
                step={0.1}
                value={imdbMin}
                className="thumb-max"
                onChange={(e) => setImdbMin(Number(e.target.value))}
              />
            </div>
          </div>
        </div>

        {(anyActiveFilters || filtersDirty) && (
          <div className="filter-row filter-row-actions">
            <span className="filter-label" />
            <div className="filter-actions">
              {anyActiveFilters && (
                <button className="clear-filters" onClick={clearAllFilters}>
                  Clear all
                </button>
              )}
              {filtersDirty && (
                <button className="apply-filters" onClick={handleApply}>
                  Apply
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      <div id="answer-box">
        {loading ? (
          <div className="empty-state">Searching for matching movies...</div>
        ) : movies.length === 0 ? (
          <div className="empty-state">
            Try "heist" + "tense and thrilling", or just one field on its own
            like "space travel" or "warm and nostalgic."
          </div>
        ) : (
          movies.map((movie, i) => (
            <div
              className={`movie-item`}
              key={`${movie.title}-${i}`}
              onClick={() => setSelectedMovie(movie)}
            >
              {movie.tconst && (
                <img
                  className="movie-poster"
                  src={`/api/poster/${movie.tconst}`}
                  alt={movie.title}
                  onError={(e) => { ;(e.target as HTMLImageElement).style.display = 'none' }}
                />
              )}
              <div className="movie-info">
                <div className="movie-title-row">
                  <h2 className="movie-title">{movie.title}</h2>
                  <div className="movie-score">{Math.round(movie.score * 100)}% match</div>
                </div>

                <div className="movie-subtitle">
                  <span className="movie-details">
                    {[
                      ...(movie.genre ? movie.genre.split(',').slice(0, 2).map((g) => g.trim()) : []),
                      movie.runtime ? formatRuntime(movie.runtime) : null,
                      movie.releaseYear != null ? String(movie.releaseYear) : null,
                    ].filter(Boolean).join(' · ')}
                  </span>
                </div>

                {(movie.imdbScore != null || movie.rtScore != null) && (
                  <div className="movie-scores">
                    {movie.imdbScore != null && (
                      <span className="score-item score-imdb">
                        <span className="score-label">IMDb</span>
                        <span className="score-value">{movie.imdbScore}</span>
                      </span>
                    )}
                    {movie.rtScore != null && (
                      <span className="score-item score-rt">
                        <span className="score-label">RT</span>
                        <span className="score-value">{movie.rtScore}%</span>
                      </span>
                    )}
                  </div>
                )}

                {movie.director && <p className="movie-director">Dir. {movie.director}</p>}

                {movie.actors && (
                  <p className="movie-actors">
                    {movie.actors.split(',').slice(0, 3).map((a) => a.trim()).join(', ')}
                  </p>
                )}

                {(movie.plot || movie.explanation) && (
                  <p className="movie-desc">{movie.plot || movie.explanation}</p>
                )}

                <div className="card-hint">Click to see emotion breakdown</div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Modal */}
      {selectedMovie && (
        <div className="modal-backdrop" onClick={() => setSelectedMovie(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setSelectedMovie(null)}>✕</button>

            <div className="modal-header">
              {selectedMovie.tconst && (
                <img
                  className="modal-poster"
                  src={`/api/poster/${selectedMovie.tconst}`}
                  alt={selectedMovie.title}
                  onError={(e) => { ;(e.target as HTMLImageElement).style.display = 'none' }}
                />
              )}
              <div className="modal-meta">
                <div className="modal-title-row">
                  <h2 className="modal-title">{selectedMovie.title}</h2>
                  <div className="movie-score">{Math.round(selectedMovie.score * 100)}% match</div>
                </div>

                <div className="movie-subtitle">
                  <span className="movie-details">
                    {[
                      ...(selectedMovie.genre ? selectedMovie.genre.split(',').map((g) => g.trim()) : []),
                      selectedMovie.runtime ? formatRuntime(selectedMovie.runtime) : null,
                      selectedMovie.releaseYear != null ? String(selectedMovie.releaseYear) : null,
                    ].filter(Boolean).join(' · ')}
                  </span>
                </div>

                {(selectedMovie.imdbScore != null || selectedMovie.rtScore != null) && (
                  <div className="movie-scores">
                    {selectedMovie.imdbScore != null && (
                      <span className="score-item score-imdb">
                        <span className="score-label">IMDb</span>
                        <span className="score-value">{selectedMovie.imdbScore}</span>
                      </span>
                    )}
                    {selectedMovie.rtScore != null && (
                      <span className="score-item score-rt">
                        <span className="score-label">RT</span>
                        <span className="score-value">{selectedMovie.rtScore}%</span>
                      </span>
                    )}
                  </div>
                )}

                {selectedMovie.director && (
                  <p className="movie-director">Dir. {selectedMovie.director}</p>
                )}
                {selectedMovie.actors && (
                  <p className="movie-actors">{selectedMovie.actors}</p>
                )}
                {(selectedMovie.plot || selectedMovie.explanation) && (
                  <p className="modal-plot">{selectedMovie.plot || selectedMovie.explanation}</p>
                )}
              </div>
            </div>

            {selectedMovie.emotions && selectedMovie.emotions.length > 0 && (
              <div className="modal-chart">
                <RadarChart queryEmotions={queryEmotions} movieEmotions={selectedMovie.emotions} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default App
