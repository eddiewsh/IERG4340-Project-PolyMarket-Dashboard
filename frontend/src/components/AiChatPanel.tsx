import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  conversationId: string | null
  onConversationCreated: (id: string) => void
}

export default function AiChatPanel({ conversationId, onConversationCreated }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!conversationId) {
      setMessages([])
      return
    }
    fetch(`/api/rag/conversations/${conversationId}/messages`)
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
      const res = await fetch('/api/rag/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, conversation_id: conversationId, top_k: 8 }),
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
      const msg = e?.message?.includes('rate limit') ? 'API 頻率限制，請稍後再試。' : `Error: ${e?.message || 'failed to get response.'}`
      setMessages((prev) => [...prev, { role: 'assistant', content: msg }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
        {messages.length === 0 && !loading && (
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
                  : 'bg-white/[0.06] text-text-secondary'
              }`}
            >
              {m.role === 'assistant' ? (
                <div className="prose prose-invert prose-sm max-w-none [&_p]:m-0 [&_p]:mb-2 [&_ul]:m-0 [&_ol]:m-0 [&_li]:m-0 [&_h1]:text-sm [&_h2]:text-sm [&_h3]:text-xs [&_a]:text-accent-cyan [&_code]:bg-white/10 [&_code]:px-1 [&_code]:rounded [&_pre]:bg-white/10 [&_pre]:p-2 [&_pre]:rounded-lg [&_blockquote]:border-accent-cyan/40">
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              ) : (
                <span>{m.content}</span>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white/[0.06] rounded-xl px-3 py-2">
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

      <div className="border-t border-white/[0.06] p-2">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
            placeholder="Type a message…"
            className="flex-1 bg-white/[0.06] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-text-primary placeholder:text-text-muted outline-none focus:border-accent-cyan/40 transition-colors"
            disabled={loading}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="px-3 py-2 rounded-lg bg-accent-cyan/20 text-accent-cyan text-[13px] font-medium hover:bg-accent-cyan/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
