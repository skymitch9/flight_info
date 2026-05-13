import { Link } from 'react-router-dom';

interface LatestAnalysis {
  recommendation: string;
  explanation: string;
  analyzedAt: string;
}

interface Trip {
  id: number;
  origin: string;
  destination: string;
  earliestDeparture: string;
  latestDeparture: string;
  latestAnalysis: LatestAnalysis | null;
}

interface TripCardProps {
  trip: Trip;
}

function getRecommendationLabel(recommendation: string): string {
  switch (recommendation) {
    case 'buy_now':
      return 'Buy Now';
    case 'wait':
      return 'Wait';
    case 'prices_rising':
      return 'Prices Rising';
    default:
      return recommendation;
  }
}

function getRecommendationColor(recommendation: string): string {
  switch (recommendation) {
    case 'buy_now':
      return '#16a34a';
    case 'wait':
      return '#6b7280';
    case 'prices_rising':
      return '#ea580c';
    default:
      return '#6b7280';
  }
}

export default function TripCard({ trip }: TripCardProps) {
  const { id, origin, destination, earliestDeparture, latestDeparture, latestAnalysis } = trip;

  return (
    <Link to={`/trips/${id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
      <div
        style={{
          border: '1px solid var(--border)',
          borderRadius: '8px',
          padding: '20px',
          boxShadow: 'var(--shadow)',
          transition: 'box-shadow 0.2s',
          cursor: 'pointer',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, color: 'var(--text-h)', fontSize: '20px' }}>
            {origin} → {destination}
          </h3>
          {latestAnalysis && (
            <span
              style={{
                fontSize: '13px',
                fontWeight: 600,
                padding: '4px 10px',
                borderRadius: '12px',
                color: '#fff',
                backgroundColor: getRecommendationColor(latestAnalysis.recommendation),
              }}
            >
              {getRecommendationLabel(latestAnalysis.recommendation)}
            </span>
          )}
        </div>
        <p style={{ margin: '8px 0 0', color: 'var(--text)', fontSize: '15px' }}>
          {earliestDeparture} – {latestDeparture}
        </p>
      </div>
    </Link>
  );
}
