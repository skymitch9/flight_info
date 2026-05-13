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
  mainCabin: number | null;
  premium: number | null;
}

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

function transformData(priceHistory: PriceHistoryEntry[]): ChartDataPoint[] {
  // Group by collectedAt timestamp (within 1 minute window)
  const grouped = new Map<number, { mainCabin: number[]; premium: number[]; raw: string }>();

  for (const entry of priceHistory) {
    const ts = new Date(entry.collectedAt).getTime();
    // Round to nearest minute to group batch entries
    const roundedTs = Math.round(ts / 60000) * 60000;

    if (!grouped.has(roundedTs)) grouped.set(roundedTs, { mainCabin: [], premium: [], raw: entry.collectedAt });
    const group = grouped.get(roundedTs)!;
    const priceDollars = entry.priceCents / 100;
    if (entry.fareClass === 'main_cabin') group.mainCabin.push(priceDollars);
    else group.premium.push(priceDollars);
  }

  const sortedKeys = Array.from(grouped.keys()).sort((a, b) => a - b);

  return sortedKeys.map((key) => {
    const group = grouped.get(key)!;
    const avg = (arr: number[]) => arr.length > 0 ? Math.round((arr.reduce((s, p) => s + p, 0) / arr.length) * 100) / 100 : null;
    return { timestamp: key, collectedAt: group.raw, mainCabin: avg(group.mainCabin), premium: avg(group.premium) };
  });
}

export default function PriceChart({ priceHistory }: PriceChartProps) {
  if (!priceHistory || priceHistory.length === 0) {
    return (
      <p style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: '0.8rem', color: '#555577' }}>
        No telemetry data. Awaiting first scan cycle...
      </p>
    );
  }

  const data = transformData(priceHistory);
  const scale = getTimeScale(data);

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
        <Line
          type="monotone"
          dataKey="mainCabin"
          name="MAIN CABIN"
          stroke="#00F0FF"
          strokeWidth={2}
          dot={data.length < 20}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="premium"
          name="PREMIUM"
          stroke="#FCEE09"
          strokeWidth={2}
          dot={data.length < 20}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
