interface Props {
  marketCount: number
}

export default function TopBar({ marketCount }: Props) {
  return (
    <div className="glass-strong rounded-full px-5 py-2 flex items-center gap-4 select-none">
      <div className="flex items-center gap-2">
        <div className="w-2.5 h-2.5 rounded-full bg-accent-cyan animate-pulse shadow-[0_0_8px_#00d4ff88]" />
        <span className="text-[15px] font-bold tracking-wider text-text-primary">
          POLYMONITOR
        </span>
      </div>
      <div className="w-px h-4 bg-white/10" />
      <span className="text-[13px] text-text-secondary">
        {marketCount} live markets
      </span>
      <div className="w-px h-4 bg-white/10" />
      <span className="text-[13px] text-accent-teal">
        ● LIVE
      </span>
    </div>
  )
}
