import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { ragSummarize } from '../api/client'
import { STORAGE_CHAT_EXTRA } from '../constants/storage'
import type { SelectedItem } from '../types'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  conversationId: string | null
  onConversationCreated: (id: string) => void
  selectedItem?: SelectedItem | null
  summarizeEnabled?: boolean
  onGenerateImpactMap?: (chatText: string) => void
  impactLoading?: boolean
}

export default function AiChatPanel({ conversationId, onConversationCreated, selectedItem = null, summarizeEnabled = false, onGenerateImpactMap, impactLoading }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [summarizeLoading, setSummarizeLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const handleSummarize = useCallback(async () => {
    if (!selectedItem || !summarizeEnabled || summarizeLoading) return
    const label =
      selectedItem.kind === 'polymarket'
        ? `[Polymarket] ${selectedItem.title}`
        : selectedItem.kind === 'news'
          ? `[News] ${selectedItem.title}`
          : selectedItem.kind === 'crypto'
            ? `[Crypto] ${selectedItem.title} (${selectedItem.symbol})`
            : `[${selectedItem.kind === 'stock' ? 'Stock' : 'Other'}] ${selectedItem.title}`
    setSummarizeLoading(true)
    setMessages((prev) => [...prev, { role: 'user', content: `Summarize: ${label}` }])
    try {
      const payload =
        selectedItem.kind === 'polymarket'
          ? {
              kind: 'polymarket' as const,
              title: selectedItem.title,
              market_id: selectedItem.market_id,
              description: selectedItem.description,
              probability: (selectedItem.meta as { probability?: number } | undefined)?.probability,
              volume_24h: (selectedItem.meta as { volume_24h?: number } | undefined)?.volume_24h,
            }
          : selectedItem.kind === 'news'
            ? {
                kind: 'news' as const,
                title: selectedItem.title,
                description: selectedItem.description,
                url: selectedItem.url ?? undefined,
                news_source: selectedItem.source,
              }
            : selectedItem.kind === 'stock'
              ? { kind: 'stock' as const, title: selectedItem.title, symbol: selectedItem.symbol }
              : selectedItem.kind === 'crypto'
                ? {
                    kind: 'other' as const,
                    title: `${selectedItem.title} (${selectedItem.symbol})`,
                    symbol: selectedItem.symbol,
                  }
                : { kind: 'other' as const, title: selectedItem.title, symbol: selectedItem.symbol }
      const data = await ragSummarize(payload)
      setMessages((prev) => [...prev, { role: 'assistant', content: data.answer }])
    } catch (e: any) {
      setMessages((prev) => [...prev, { role: 'assistant', content: e?.message || 'Summarize failed.' }])
    } finally {
      setSummarizeLoading(false)
    }
  }, [selectedItem, summarizeEnabled, summarizeLoading])

  useEffect(() => {
    if (!conversationId) {
      setMessages([])
      return
    }
    fetch(`${import.meta.env.VITE_API_BASE_URL || ''}/api/rag/conversations/${conversationId}/messages`)
      .then((r) => r.json())
      .then((data: Message[]) => setMessages(data))
      .catch(() => {})
  }, [conversationId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send() {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: q }])
    setLoading(true)
    try {
      const extra = (localStorage.getItem(STORAGE_CHAT_EXTRA) ?? '').trim().slice(0, 2000)
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || ''}/api/rag/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          conversation_id: conversationId,
          top_k: 8,
          ...(extra ? { extra_instructions: extra } : {}),
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        throw new Error(err?.detail || res.statusText)
      }
      const data = await res.json()
      setMessages((prev) => [...prev, { role: 'assistant', content: data.answer }])
      if (!conversationId && data.conversation_id) {
        onConversationCreated(data.conversation_id)
      }
    } catch (e: any) {
      const msg = e?.message?.includes('rate limit') ? 'Rate limited. Please try again shortly.' : `Error: ${e?.message || 'failed to get response.'}`
      setMessages((prev) => [...prev, { role: 'assistant', content: msg }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
        {messages.length === 0 && !loading && !summarizeLoading && (
          <div className="flex items-center justify-center h-full">
            <p className="text-text-muted text-[13px]">Ask anything about the data…</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 text-[13px] leading-relaxed ${
                m.role === 'user'
                  ? 'bg-accent-cyan/20 text-text-primary'
                  : 'bg-slate-100 text-text-secondary'
              }`}
            >
              {m.role === 'assistant' ? (
                <div className="prose prose-slate prose-sm max-w-none [&_p]:m-0 [&_p]:mb-2 [&_ul]:m-0 [&_ol]:m-0 [&_li]:m-0 [&_h1]:text-sm [&_h2]:text-sm [&_h3]:text-xs [&_a]:text-accent-cyan [&_code]:bg-slate-200 [&_code]:px-1 [&_code]:rounded [&_pre]:bg-slate-200 [&_pre]:p-2 [&_pre]:rounded-lg [&_blockquote]:border-accent-cyan/40">
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              ) : (
                <span>{m.content}</span>
              )}
            </div>
          </div>
        ))}
        {(loading || summarizeLoading) && (
          <div className="flex justify-start">
            <div className="bg-slate-100 rounded-xl px-3 py-2">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-accent-cyan/60 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 bg-accent-cyan/60 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 bg-accent-cyan/60 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-slate-200 p-2 space-y-2">
        {summarizeEnabled && (
          <div className="flex items-center justify-between gap-2 px-1">
            <span className="text-[11px] text-text-muted truncate min-w-0">
              {selectedItem ? selectedItem.title : 'Select an item to summarize'}
            </span>
            <button
              type="button"
              onClick={handleSummarize}
              disabled={!selectedItem || loading || summarizeLoading}
              className="shrink-0 text-[12px] px-3 py-1.5 rounded-lg bg-accent-cyan/20 text-accent-cyan hover:bg-accent-cyan/30 disabled:opacity-40"
            >
              {summarizeLoading ? 'Summarizing…' : 'AI Summarize'}
            </button>
          </div>
        )}
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
            placeholder="Type a message…"
            className="flex-1 bg-slate-100 border border-slate-200 rounded-lg px-3 py-2 text-[13px] text-text-primary placeholder:text-text-muted outline-none focus:border-accent-cyan/40 transition-colors"
            disabled={loading || summarizeLoading}
          />
          <button
            onClick={send}
            disabled={loading || summarizeLoading || !input.trim()}
            className="px-3 py-2 rounded-lg bg-accent-cyan/20 text-accent-cyan text-[13px] font-medium hover:bg-accent-cyan/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Send
          </button>
          {onGenerateImpactMap && (
            <button
              type="button"
              onClick={() => {
                const text = input.trim()
                if (!text) return
                onGenerateImpactMap(text)
              }}
              disabled={!input.trim() || !!impactLoading}
              className="px-3 py-2 rounded-lg bg-accent-amber/15 text-accent-amber text-[13px] font-medium hover:bg-accent-amber/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="Generate impact map from chat input"
            >
              {impactLoading ? '…' : '⚡'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
