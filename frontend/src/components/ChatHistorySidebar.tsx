import { useState, useEffect } from 'react'
import { deleteRagConversation, listImpactMaps, deleteImpactMap } from '../api/client'
import type { ImpactMapSummary } from '../types'

interface Conversation {
  conversation_id: string
  title: string
  updated_at: string
}

interface Props {
  activeId: string | null
  onSelect: (id: string) => void
  onNewChat: () => void
  refreshKey: number
  onDeleted?: (deletedId: string) => void
  activeMapId?: string | null
  onSelectMap?: (mapId: string) => void
  onDeletedMap?: (mapId: string) => void
  mapRefreshKey?: number
}

export default function ChatHistorySidebar({ activeId, onSelect, onNewChat, refreshKey, onDeleted, activeMapId, onSelectMap, onDeletedMap, mapRefreshKey }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [maps, setMaps] = useState<ImpactMapSummary[]>([])
  const [deleting, setDeleting] = useState<string | null>(null)
  const [tab, setTab] = useState<'chats' | 'maps'>('chats')

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_BASE_URL || ''}/api/rag/conversations`)
      .then((r) => r.json())
      .then((data: Conversation[]) => setConversations(data))
      .catch(() => {})
  }, [refreshKey])

  useEffect(() => {
    listImpactMaps().then((data) => {
      setMaps(data)
      if (data.length > 0) setTab('maps')
    }).catch(() => {})
  }, [mapRefreshKey])

  async function handleDelete(e: React.MouseEvent, id: string) {
    e.stopPropagation()
    if (deleting) return
    setDeleting(id)
    try {
      await deleteRagConversation(id)
      onDeleted?.(id)
      setConversations((prev) => prev.filter((c) => c.conversation_id !== id))
    } catch {
      /* list unchanged */
    } finally {
      setDeleting(null)
    }
  }

  async function handleDeleteMap(e: React.MouseEvent, id: string) {
    e.stopPropagation()
    if (deleting) return
    setDeleting(id)
    try {
      await deleteImpactMap(id)
      onDeletedMap?.(id)
      setMaps((prev) => prev.filter((m) => m.map_id !== id))
    } catch {
      /* unchanged */
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-2 border-b border-slate-200 space-y-1.5">
        <button
          onClick={onNewChat}
          className="w-full text-[12px] px-3 py-1.5 rounded-lg bg-accent-cyan/15 text-accent-cyan hover:bg-accent-cyan/25 transition-colors"
        >
          + New Chat
        </button>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={() => setTab('chats')}
            className={`flex-1 text-[11px] py-1 rounded-md transition-colors ${tab === 'chats' ? 'bg-slate-200 text-text-primary' : 'text-text-muted hover:bg-slate-100'}`}
          >
            Chats
          </button>
          <button
            type="button"
            onClick={() => setTab('maps')}
            className={`flex-1 text-[11px] py-1 rounded-md transition-colors ${tab === 'maps' ? 'bg-amber-100 text-amber-700' : 'text-text-muted hover:bg-slate-100'}`}
          >
            Maps
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        {tab === 'chats' && (
          <>
            {conversations.map((c) => (
              <div
                key={c.conversation_id}
                className={`flex items-stretch gap-0 border-b border-slate-100 group ${
                  activeId === c.conversation_id ? 'bg-accent-cyan/10' : 'hover:bg-slate-100'
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelect(c.conversation_id)}
                  className={`flex-1 min-w-0 text-left px-3 py-2 text-[12px] transition-colors truncate ${
                    activeId === c.conversation_id ? 'text-text-primary' : 'text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {c.title}
                </button>
                <button
                  type="button"
                  title="Delete chat"
                  aria-label="Delete chat"
                  disabled={deleting === c.conversation_id}
                  onClick={(e) => handleDelete(e, c.conversation_id)}
                  className="shrink-0 px-2 text-[14px] text-text-muted hover:text-rose-600 hover:bg-rose-50/80 opacity-70 group-hover:opacity-100 transition-opacity disabled:opacity-30"
                >
                  ×
                </button>
              </div>
            ))}
            {conversations.length === 0 && (
              <p className="text-text-muted text-[11px] p-3 text-center">No conversations yet</p>
            )}
          </>
        )}

        {tab === 'maps' && (
          <>
            {maps.map((m) => (
              <div
                key={m.map_id}
                className={`flex items-stretch gap-0 border-b border-slate-100 group ${
                  activeMapId === m.map_id ? 'bg-amber-50' : 'hover:bg-slate-100'
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelectMap?.(m.map_id)}
                  className={`flex-1 min-w-0 text-left px-3 py-2 text-[12px] transition-colors truncate ${
                    activeMapId === m.map_id ? 'text-amber-700' : 'text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {m.event_kind && <span className="text-[9px] uppercase bg-slate-200 text-text-muted rounded px-1 mr-1">{m.event_kind}</span>}
                  {m.title}
                </button>
                <button
                  type="button"
                  title="Delete map"
                  aria-label="Delete map"
                  disabled={deleting === m.map_id}
                  onClick={(e) => handleDeleteMap(e, m.map_id)}
                  className="shrink-0 px-2 text-[14px] text-text-muted hover:text-rose-600 hover:bg-rose-50/80 opacity-70 group-hover:opacity-100 transition-opacity disabled:opacity-30"
                >
                  ×
                </button>
              </div>
            ))}
            {maps.length === 0 && (
              <p className="text-text-muted text-[11px] p-3 text-center">No saved maps yet</p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
