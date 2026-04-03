export const POLYMARKET_CATEGORY_COLORS: Record<string, string> = {
  uncategorized: '#64748b',
  politics: '#f43f5e',
  geopolitics: '#ef4444',
  elections: '#f43f5e',
  'us-election': '#f43f5e',
  economics: '#f59e0b',
  economy: '#eab308',
  finance: '#d97706',
  business: '#f97316',
  crypto: '#a855f7',
  bitcoin: '#a855f7',
  ethereum: '#a855f7',
  tech: '#00d4ff',
  science: '#06b6d4',
  ai: '#00d4ff',
  stocks: '#22c55e',
  equities: '#22c55e',
  health: '#10b981',
  climate: '#06b6d4',
  sports: '#ec4899',
  football: '#ec4899',
  basketball: '#ec4899',
  nfl: '#ec4899',
  nba: '#ec4899',
  entertainment: '#c026d3',
  culture: '#c026d3',
  world: '#38bdf8',
}

export const CATEGORY_GROUP: Record<string, string> = {
  soccer: 'Soccer', 'fifa-world-cup': 'Soccer', '2026-fifa-world-cup': 'Soccer',
  'world-cup': 'Soccer', 'champions-league': 'Soccer', 'premier-league': 'Soccer',
  'la-liga': 'Soccer', 'la-liga-2': 'Soccer', 'ligue-1': 'Soccer', epl: 'Soccer',
  ucl: 'Soccer', mls: 'Soccer', 'australian-a-league': 'Soccer', 'brazil-serie-a': 'Soccer',

  basketball: 'Basketball', nba: 'Basketball', 'nba-finals': 'Basketball',
  'nba-champion': 'Basketball', 'euroleague-basketball': 'Basketball',
  'march-madness': 'Basketball', ncaa: 'Basketball', 'ncaa-basketball': 'Basketball',
  'ncaa-cbb': 'Basketball', cbb: 'Basketball', cba: 'Basketball', mvp: 'Basketball',

  esports: 'Esports', 'league-of-legends': 'Esports', 'counter-strike-2': 'Esports',
  cs2: 'Esports', 'dota-2': 'Esports', valorant: 'Esports',

  nfl: 'NFL', football: 'NFL',

  mlb: 'MLB', 'mlb-playoffs': 'MLB', 'world-series': 'MLB', baseball: 'MLB',

  nhl: 'Hockey', hockey: 'Hockey', 'stanley-cup': 'Hockey',

  f1: 'Motors', formula1: 'Motors',

  golf: 'Golf & Tennis', 'pga-tour': 'Golf & Tennis', 'the-masters': 'Golf & Tennis',
  invitational: 'Golf & Tennis', augusta: 'Golf & Tennis', tennis: 'Golf & Tennis',
  atp: 'Golf & Tennis',

  cricket: 'Cricket', 'indian-premier-league': 'Cricket',

  sports: 'Sports', games: 'Sports', 'world-games': 'Sports',

  politics: 'US Politics', 'us-election': 'US Politics', 'us-politics': 'US Politics',
  'us-presidential-election': 'US Politics', primaries: 'US Politics',
  'primary-elections': 'US Politics', 'united-states': 'US Politics',
  'donald-trump': 'US Politics', 'trump-presidency': 'US Politics', trump: 'US Politics',
  president: 'US Politics', congress: 'US Politics', 'republican-primary': 'US Politics',
  'democratic-primary': 'US Politics', 'trump-cabinet': 'US Politics',
  'texas-senate': 'US Politics', 'senate-primary': 'US Politics',
  'texas-primary': 'US Politics', 'march-3-primaries': 'US Politics',
  epstein: 'US Politics', 'tweets-markets': 'US Politics',

  'world-elections': 'Elections', 'global-elections': 'Elections', elections: 'Elections',
  presidential: 'Elections', 'macro-election-1': 'Elections', 'macro-election-2': 'Elections',
  'hungary-election': 'Elections', 'colombia-election': 'Elections',

  iran: 'Middle East', israel: 'Middle East', gaza: 'Middle East', palestine: 'Middle East',
  hamas: 'Middle East', 'middle-east': 'Middle East', 'strait-of-hormuz': 'Middle East',
  hormuz: 'Middle East', ships: 'Middle East', transit: 'Middle East',
  'trump-iran': 'Middle East', 'iranian-leadership-regime': 'Middle East',
  'us-iran': 'Middle East', 'reza-pahlavi': 'Middle East', khamenei: 'Middle East',
  'mojtaba-khamenei': 'Middle East', 'kharg-island': 'Middle East',
  'iran-offensive-actions': 'Middle East', 'regional-spillover': 'Middle East',
  'israel-x-iran': 'Middle East',

  china: 'Asia Pacific', india: 'Asia Pacific', vietnam: 'Asia Pacific',
  'south-korea': 'Asia Pacific', seoul: 'Asia Pacific', 'hong-kong': 'Asia Pacific',
  shanghai: 'Asia Pacific', tokyo: 'Asia Pacific', tiktok: 'Asia Pacific',

  ukraine: 'Europe', france: 'Europe', london: 'Europe', hungary: 'Europe',
  nato: 'Europe', greenland: 'Europe',

  brazil: 'Americas', colombia: 'Americas', columbia: 'Americas', cuba: 'Americas',
  venezuela: 'Americas', maduro: 'Americas', peru: 'Americas', arg: 'Americas',
  'trump-machado': 'Americas',

  geopolitics: 'World', world: 'World',
  'diplomacy-ceasefire': 'World', 'military-strikes': 'World',
  'regional-splitbar': 'World', 'foreign-policy': 'World',
  'ukraine-peace-deal': 'World', 'trump-zelenskyy': 'World', 'trump-zelensky': 'World',
  'trump-xi': 'World', 'trade-war': 'World', tariffs: 'World',
  'macro-geopolitics': 'World', nuclear: 'World', strikes: 'World', strike: 'World',
  'multi-strikes': 'World', communist: 'World',

  stocks: 'Stocks', equities: 'Stocks', ipo: 'Stocks', 'pre-market': 'Stocks',

  fed: 'Fed & Rates', 'fed-rates': 'Fed & Rates', fomc: 'Fed & Rates',
  'jerome-powell': 'Fed & Rates', 'judy-shelton': 'Fed & Rates',
  'kevin-warsh': 'Fed & Rates', 'economic-policy': 'Fed & Rates',

  commodities: 'Commodities', oil: 'Commodities', gold: 'Commodities',
  'nymex-crude-oil-futures': 'Commodities', 'comex-gold-futures': 'Commodities',
  'hit-price': 'Commodities',

  economics: 'Economy', economy: 'Economy', finance: 'Economy', business: 'Economy',
  'finance-updown': 'Economy', fdv: 'Economy', 'up-or-down': 'Economy',

  crypto: 'Crypto', bitcoin: 'Crypto', ethereum: 'Crypto', airdrops: 'Crypto',
  'crypto-prices': 'Crypto', solana: 'Crypto', megaeth: 'Crypto', p2p: 'Crypto',

  tech: 'Tech', science: 'Tech', ai: 'Tech', spacex: 'Tech', 'big-tech': 'Tech',

  entertainment: 'Culture', culture: 'Culture', 'pop-culture': 'Culture',
  'box-office': 'Culture', 'academy-awards': 'Culture', 'mario-election': 'Culture',
  awards: 'Culture', music: 'Culture', movies: 'Culture', aliens: 'Culture',

  health: 'Weather', climate: 'Weather', 'global-warming': 'Weather',
  pandemic: 'Weather', 'daily-temperature': 'Weather', weather: 'Weather',
  temperature: 'Weather', miami: 'Weather',
}

const GROUP_COLORS: Record<string, string> = {
  'Soccer': '#22c55e',
  'Basketball': '#f97316',
  'Sports': '#ec4899',
  'Esports': '#8b5cf6',
  'NFL': '#b91c1c',
  'MLB': '#1d4ed8',
  'Hockey': '#0ea5e9',
  'Motors': '#64748b',
  'Golf & Tennis': '#059669',
  'Cricket': '#ca8a04',
  'US Politics': '#f43f5e',
  'Elections': '#e11d48',
  'Middle East': '#d97706',
  'Asia Pacific': '#f472b6',
  'Europe': '#3b82f6',
  'Americas': '#84cc16',
  'World': '#38bdf8',
  'Stocks': '#22c55e',
  'Fed & Rates': '#eab308',
  'Commodities': '#a16207',
  'Economy': '#f59e0b',
  'Crypto': '#a855f7',
  'Tech': '#00d4ff',
  'Culture': '#c026d3',
  'Weather': '#10b981',
}

export const KNOWN_GROUP_ORDER: string[] = [
  'Soccer', 'Basketball', 'NFL', 'MLB', 'Hockey', 'Motors', 'Golf & Tennis', 'Cricket',
  'Esports', 'Sports',
  'US Politics', 'Elections', 'Middle East', 'Asia Pacific', 'Europe', 'Americas', 'World',
  'Stocks', 'Fed & Rates', 'Commodities', 'Economy',
  'Crypto', 'Tech', 'Culture', 'Weather',
]

export function categoryGroup(slug: string): string {
  return CATEGORY_GROUP[slug] ?? slug
}

export function groupColor(group: string): string {
  return GROUP_COLORS[group] ?? POLYMARKET_CATEGORY_COLORS[group] ?? '#64748b'
}

export function categoryColor(category: string, fallback: string): string {
  return POLYMARKET_CATEGORY_COLORS[category] ?? fallback
}
