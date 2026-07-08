import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

export interface PriceHistoryEntry {
  airlineCode: string;
  fareClass: string;
  priceCents: number;
  flightDate: string;
  collectedAt: string;
}

interface PriceChartProps {
  priceHistory: PriceHistoryEntry[];
}

interface ChartDataPoint {
  timestamp: number;
  collectedAt: string;
  // Dynamic keys: one series per departure date (`d_2026-08-28`) plus `premium`
  [key: string]: number | string | null;
}

const SERIES_COLORS = ['#00F0FF', '#16f0a0', '#c792ea', '#ff9e64', '#FF003C', '#7aa2f7'];

type TimeScale = 'minutes' | 'hours' | 'days' | 'months';

function getTimeScale(dataPoints: ChartDataPoint[]): TimeScale {
  if (dataPoints.length < 2) return 'minutes';
  const first = dataPoints[0].timestamp;
  const last = dataPoints[dataPoints.length - 1].timestamp;
  const rangeMs = last - first;
  const rangeHours = rangeMs / (1000 * 60 * 60);

  if (rangeHours < 2) return 'minutes';
  if (rangeHours < 48) return 'hours';
  if (rangeHours < 24 * 60) return 'days';
  return 'months';
}

function formatTick(timestamp: number, scale: TimeScale): string {
  const date = new Date(timestamp);
  switch (scale) {
    case 'minutes':
      return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    case 'hours':
      return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    case 'days':
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    case 'months':
      return date.toLocaleDateString([], { month: 'short', year: '2-digit' });
  }
}

function formatTooltipLabel(timestamp: number, scale: TimeScale): string {
  const date = new Date(timestamp);
  switch (scale) {
    case 'minutes':
    case 'hours':
      return date.toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    case 'days':
      return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
    case 'months':
      return date.toLocaleDateString([], { month: 'long', year: 'numeric' });
  }
}

function transformData(priceHistory: PriceHistoryEntry[]): { data: ChartDataPoint[]; dateKeys: string[] } {
  // Group by collectedAt timestamp (within a 5-minute batch window), then
  // track the *cheapest* main-cabin fare per departure date as its own
  // series, plus a single cheapest-premium series across dates.
  const grouped = new Map<number, { byDate: Map<string, number>; premium: number[]; raw: string }>();
  const dateKeySet = new Set<string>();

  for (const entry of priceHistory) {
    const ts = new Date(entry.collectedAt).getTime();
    const roundedTs = Math.round(ts / 300000) * 300000; // 5-minute buckets

    if (!grouped.has(roundedTs)) grouped.set(roundedTs, { byDate: new Map(), premium: [], raw: entry.collectedAt });
    const group = grouped.get(roundedTs)!;
    const priceDollars = entry.priceCents / 100;

    if (entry.fareClass === 'main_cabin') {
      const key = `d_${entry.flightDate}`;
      dateKeySet.add(key);
      const existing = group.byDate.get(key);
      if (existing === undefined || priceDollars < existing) group.byDate.set(key, priceDollars);
    } else {
      group.premium.push(priceDollars);
    }
  }

  const sortedKeys = Array.from(grouped.keys()).sort((a, b) => a - b);
  const dateKeys = Array.from(dateKeySet).sort();

  const data = sortedKeys.map((key) => {
    const group = grouped.get(key)!;
    const point: ChartDataPoint = { timestamp: key, collectedAt: group.raw };
    for (const dk of dateKeys) {
      point[dk] = group.byDate.get(dk) ?? null;
    }
    point.premium = group.premium.length > 0 ? Math.min(...group.premium) : null;
    return point;
  });

  return { data, dateKeys };
}

function dateKeyLabel(dateKey: string): string {
  // "d_2026-08-28" -> "AUG 28"
  const d = new Date(dateKey.slice(2) + 'T00:00:00');
  return isNaN(d.getTime())
    ? dateKey
    : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }).toUpperCase();
}

export default function PriceChart({ priceHistory }: PriceChartProps) {
  if (!priceHistory || priceHistory.length === 0) {
    return (
      <p style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: '0.8rem', color: '#555577' }}>
        No telemetry data. Awaiting first scan cycle...
      </p>
    );
  }

  const { data, dateKeys } = transformData(priceHistory);
  const scale = getTimeScale(data);
  const hasPremium = data.some((p) => p.premium !== null);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
        <XAxis
          dataKey="timestamp"
          type="number"
          domain={['dataMin', 'dataMax']}
          tickFormatter={(ts) => formatTick(ts, scale)}
          stroke="#555577"
          tick={{ fontSize: 11, fontFamily: 'Share Tech Mono' }}
        />
        <YAxis
          tickFormatter={(value: number) => `$${value}`}
          stroke="#555577"
          tick={{ fontSize: 11, fontFamily: 'Share Tech Mono' }}
        />
        <Tooltip
          labelFormatter={(ts) => formatTooltipLabel(Number(ts), scale)}
          formatter={(value) => [`$${Number(value).toFixed(2)}`, '']}
          contentStyle={{
            background: '#12121a',
            border: '1px solid #2a2a4a',
            fontFamily: 'Share Tech Mono',
            fontSize: '0.8rem',
          }}
          labelStyle={{ color: '#FCEE09' }}
        />
        <Legend
          wrapperStyle={{ fontFamily: 'Share Tech Mono', fontSize: '0.75rem' }}
        />
        {dateKeys.map((dk, i) => (
          <Line
            key={dk}
            type="monotone"
            dataKey={dk}
            name={dateKeyLabel(dk)}
            stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
            strokeWidth={2}
            dot={data.length < 20}
            connectNulls
          />
        ))}
        {hasPremium && (
          <Line
            type="monotone"
            dataKey="premium"
            name="PREMIUM"
            stroke="#FCEE09"
            strokeWidth={2}
            strokeDasharray="6 3"
            dot={data.length < 20}
            connectNulls
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
