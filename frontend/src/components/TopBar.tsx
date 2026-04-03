interface Props {
  marketCount: number
  onOpenSettings?: () => void
  earthBlank?: boolean
  onToggleEarthBlank?: () => void
}

export default function TopBar({ marketCount, onOpenSettings, earthBlank, onToggleEarthBlank }: Props) {
  return (
    <div className="glass-strong rounded-full px-5 py-2 flex items-center gap-4 select-none">
      <div className="flex items-center gap-2">
        <div className="w-2.5 h-2.5 rounded-full bg-accent-cyan animate-pulse shadow-[0_0_8px_rgba(2,132,199,0.45)]" />
        <span className="text-[15px] font-bold tracking-wider text-text-primary">
          POLYMONITOR
        </span>
      </div>
      <div className="w-px h-4 bg-slate-300" />
      <span className="text-[13px] text-text-secondary">
        {marketCount} live markets
      </span>
      <div className="w-px h-4 bg-slate-300" />
      <span className="text-[13px] text-accent-teal">
        ● LIVE
      </span>
      {onToggleEarthBlank && (
        <>
          <div className="w-px h-4 bg-slate-300" />
          <button
            type="button"
            onClick={onToggleEarthBlank}
            className={`text-[12px] px-2 py-1 rounded-md transition-colors ${earthBlank ? 'bg-accent-cyan/10 text-accent-cyan font-medium' : 'text-text-secondary hover:text-text-primary hover:bg-slate-100/80'}`}
            title={earthBlank ? 'Show globe' : 'Impact Map'}
          >
            {earthBlank ? '← Earth' : 'Impact Map'}
          </button>
        </>
      )}
      {onOpenSettings && (
        <>
          <div className="w-px h-4 bg-slate-300" />
          <button
            type="button"
            onClick={onOpenSettings}
            className="text-[18px] text-text-secondary hover:text-text-primary w-8 h-8 rounded-md hover:bg-slate-100/80 transition-colors flex items-center justify-center"
            title="Settings"
            aria-label="Settings"
          >
            ⚙
          </button>
        </>
      )}
    </div>
  )
}
