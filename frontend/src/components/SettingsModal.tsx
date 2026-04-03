import { useState, useEffect } from 'react'
import { STORAGE_CHAT_EXTRA } from '../constants/storage'

interface Props {
  open: boolean
  onClose: () => void
}

export default function SettingsModal({ open, onClose }: Props) {
  const [extra, setExtra] = useState('')

  useEffect(() => {
    if (open) {
      setExtra(() => localStorage.getItem(STORAGE_CHAT_EXTRA) ?? '')
    }
  }, [open])

  if (!open) return null

  function save() {
    const v = extra.trim()
    if (v) localStorage.setItem(STORAGE_CHAT_EXTRA, v)
    else localStorage.removeItem(STORAGE_CHAT_EXTRA)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl border border-slate-200 bg-white shadow-xl max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
          <h2 className="text-[16px] font-semibold text-text-primary">Settings</h2>
          <button type="button" onClick={onClose} className="text-text-muted hover:text-text-primary text-[20px] leading-none px-1">
            ×
          </button>
        </div>
        <div className="p-4 overflow-y-auto space-y-4">
          <div>
            <div className="text-[12px] font-semibold text-text-secondary mb-1">Platform</div>
            <p className="text-[13px] text-text-muted leading-relaxed">
              PolyMonitor aggregates Polymarket, news, and market data. Chat uses your Supabase-backed history and Gemini.
            </p>
          </div>
          <div>
            <label className="text-[12px] font-semibold text-text-secondary block mb-1.5">
              Extra instructions for AI chat
            </label>
            <p className="text-[11px] text-text-muted mb-2">
              Appended to the assistant system context on each message (max ~2000 chars). Leave empty for defaults only.
            </p>
            <textarea
              value={extra}
              onChange={(e) => setExtra(e.target.value.slice(0, 2000))}
              rows={6}
              placeholder="e.g. Prefer bullet points. Cite tickers when discussing stocks."
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[13px] text-text-primary placeholder:text-text-muted outline-none focus:border-accent-cyan/50 resize-y min-h-[120px]"
            />
            <div className="text-[11px] text-text-muted mt-1">{extra.length} / 2000</div>
          </div>
        </div>
        <div className="px-4 py-3 border-t border-slate-200 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="text-[13px] px-4 py-2 rounded-lg border border-slate-200 text-text-secondary hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            className="text-[13px] px-4 py-2 rounded-lg bg-accent-cyan/20 text-accent-cyan font-medium hover:bg-accent-cyan/30"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  )
}
