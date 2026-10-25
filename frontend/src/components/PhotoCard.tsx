import { Check, Layers, X, Star, CircleHelp } from 'lucide-react'
import type { Photo } from '../types'

export function PhotoCard({ photo: p, open, decide }: { photo: Photo; open: () => void; decide: (id: string, data: Partial<Pick<Photo, 'decision' | 'stars'>>) => void }) {
  return <article className={`photo-card ${p.selected ? 'is-selected' : ''} ${p.decision === 'reject' ? 'is-rejected' : ''}`}>
    <button className="image-button" onClick={open} aria-label={`Inspect ${p.filename}`}>
      {p.thumbnail ? <img src={p.thumbnail} alt={p.filename} loading="lazy" width={560} height={374} /> : <div className="photo-placeholder"><CircleHelp size={28}/><span>{p.status === 'failed' ? 'Preview unavailable' : 'Waiting for preview'}</span></div>}
      <div className="image-top"><span className="file-tag">{p.filename.split('.').pop()}</span>{p.selected && <span className="selection-mark"><Check size={14}/></span>}</div>
      {p.group_id && <span className={`group-badge ${p.group_protected ? 'protected' : ''}`}><Layers size={12}/>{p.group_rank} / {p.group_count}{p.group_protected ? ' · review' : ''}</span>}
    </button>
    <div className="photo-info"><div><span className="photo-name">{p.filename}</span><span className={`recommendation ${p.selected ? 'sage' : ''}`}>{p.decision !== 'auto' ? `Your ${p.decision === 'keep' ? 'pick' : p.decision}` : p.recommendation === 'pick' ? 'Recommended' : p.recommendation === 'low' ? 'Low priority' : p.recommendation}</span></div><span className="score">{p.score?.toFixed(1) ?? '—'}<small> / 100</small></span></div>
    <div className="card-controls"><div className="star-controls">{[1,2,3,4,5].map(n => <button key={n} aria-label={`Rate ${p.filename} ${n} stars`} onClick={() => decide(p.id, { stars: p.stars === n ? 0 : n })}><Star size={12} fill={p.stars >= n ? 'currentColor' : 'none'}/></button>)}</div><div className="pick-controls"><button className={p.decision === 'keep' ? 'sage' : ''} title="Keep" aria-label={`Keep ${p.filename}`} onClick={() => decide(p.id, { decision: p.decision === 'keep' ? 'auto' : 'keep' })}><Check size={15}/></button><button className={p.decision === 'reject' ? 'rose' : ''} title="Exclude" aria-label={`Exclude ${p.filename}`} onClick={() => decide(p.id, { decision: 'reject' })}><X size={15}/></button></div></div>
  </article>
}
