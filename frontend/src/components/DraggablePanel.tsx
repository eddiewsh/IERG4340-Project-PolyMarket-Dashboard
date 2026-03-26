import { useEffect, useRef, useState } from 'react'

type Pos = { x: number; y: number }

export default function DraggablePanel({
  title,
  children,
  defaultPos = { x: 16, y: 72 },
  className = '',
}: {
  title: string
  children: React.ReactNode
  defaultPos?: Pos
  className?: string
}) {
  const [pos, setPos] = useState<Pos>(defaultPos)
  const dragging = useRef(false)
  const start = useRef<{ mx: number; my: number; x: number; y: number } | null>(null)

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!dragging.current || !start.current) return
      const dx = e.clientX - start.current.mx
      const dy = e.clientY - start.current.my
      setPos({ x: start.current.x + dx, y: start.current.y + dy })
    }
    function onUp() {
      dragging.current = false
      start.current = null
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [])

  return (
    <div
      className={`absolute z-30 ${className}`}
      style={{ transform: `translate(${pos.x}px, ${pos.y}px)` }}
    >
      <div className="rounded-xl border border-white/[0.12] bg-black/55 backdrop-blur-md shadow-lg overflow-hidden w-[min(320px,92vw)]">
        <div
          className="px-3 py-2 text-[11px] text-text-muted border-b border-white/[0.06] cursor-move select-none flex items-center justify-between"
          onMouseDown={(e) => {
            dragging.current = true
            start.current = { mx: e.clientX, my: e.clientY, x: pos.x, y: pos.y }
          }}
        >
          <span className="truncate">{title}</span>
          <span className="text-[10px] opacity-70">drag</span>
        </div>
        {children}
      </div>
    </div>
  )
}

