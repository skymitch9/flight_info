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
  collectedAt: string;
  mainCabin: number | null;
  premium: number | null;
}

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function transformData(priceHistory: PriceHistoryEntry[]): ChartDataPoint[] {
  const grouped = new Map<string, { mainCabin: number[]; premium: number[] }>();

  for (const entry of priceHistory) {
    const key = entry.collectedAt;
    if (!grouped.has(key)) grouped.set(key, { mainCabin: [], premium: [] });
    const group = grouped.get(key)!;
    const priceDollars = entry.priceCents / 100;
    if (entry.fareClass === 'main_cabin') group.mainCabin.push(priceDollars);
    else group.premium.push(priceDollars);
  }

  const sortedKeys = Array.from(grouped.keys()).sort(
    (a, b) => new Date(a).getTime() - new Date(b).getTime()
  );

  return sortedKeys.map((key) => {
    const group = grouped.get(key)!;
    const avg = (arr: number[]) => arr.length > 0 ? Math.round((arr.reduce((s, p) => s + p, 0) / arr.length) * 100) / 100 : null;
    return { collectedAt: key, mainCabin: avg(group.mainCabin), premium: avg(group.premium) };
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

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
        <XAxis
          dataKey="collectedAt"
          tickFormatter={formatDate}
          stroke="#555577"
          tick={{ fontSize: 11, fontFamily: 'Share Tech Mono' }}
        />
        <YAxis
          tickFormatter={(value: number) => `$${value}`}
          stroke="#555577"
          tick={{ fontSize: 11, fontFamily: 'Share Tech Mono' }}
        />
        <Tooltip
          labelFormatter={(label) => formatDate(String(label))}
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
          dot={false}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="premium"
          name="PREMIUM"
          stroke="#FCEE09"
          strokeWidth={2}
          dot={false}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
