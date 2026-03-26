import { useState, useEffect } from 'react'

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
}

export default function ChatHistorySidebar({ activeId, onSelect, onNewChat, refreshKey }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([])

  useEffect(() => {
    fetch('/api/rag/conversations')
      .then((r) => r.json())
      .then((data: Conversation[]) => setConversations(data))
      .catch(() => {})
  }, [refreshKey])

  return (
    <div className="flex flex-col h-full">
      <div className="p-2 border-b border-white/[0.06]">
        <button
          onClick={onNewChat}
          className="w-full text-[12px] px-3 py-1.5 rounded-lg bg-accent-cyan/15 text-accent-cyan hover:bg-accent-cyan/25 transition-colors"
        >
          + New Chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto min-h-0">
        {conversations.map((c) => (
          <button
            key={c.conversation_id}
            onClick={() => onSelect(c.conversation_id)}
            className={`w-full text-left px-3 py-2 text-[12px] border-b border-white/[0.04] transition-colors truncate ${
              activeId === c.conversation_id
                ? 'bg-accent-cyan/10 text-text-primary'
                : 'text-text-muted hover:text-text-secondary hover:bg-white/[0.04]'
            }`}
          >
            {c.title}
          </button>
        ))}
        {conversations.length === 0 && (
          <p className="text-text-muted text-[11px] p-3 text-center">No conversations yet</p>
        )}
      </div>
    </div>
  )
}
