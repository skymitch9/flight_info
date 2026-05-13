import { useQuery } from '@apollo/client/react';
import { Link } from 'react-router-dom';
import { GET_FULFILLED_TRIPS } from '../graphql/queries';

interface AnalysisResult {
  recommendation: string;
  explanation: string;
  analyzedAt: string;
}

interface FulfilledTrip {
  id: number;
  origin: string;
  destination: string;
  earliestDeparture: string;
  latestDeparture: string;
  earliestReturn: string | null;
  latestReturn: string | null;
  status: string;
  fulfilledAt: string;
  latestAnalysis: AnalysisResult | null;
}

interface FulfilledTripsData {
  fulfilledTrips: FulfilledTrip[];
}

function getRecommendationBadge(recommendation: string | undefined) {
  if (!recommendation) return { label: 'N/A', className: 'cp-badge cp-badge--pending' };
  switch (recommendation) {
    case 'buy_now': return { label: 'BUY NOW', className: 'cp-badge cp-badge--buy' };
    case 'prices_rising': return { label: 'PRICES RISING', className: 'cp-badge cp-badge--rising' };
    case 'wait': return { label: 'WAIT', className: 'cp-badge cp-badge--wait-active' };
    default: return { label: recommendation.toUpperCase(), className: 'cp-badge cp-badge--wait-active' };
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric',
  });
}

function formatFulfilledDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

export default function ContractHistory() {
  const { data, loading, error } = useQuery<FulfilledTripsData>(GET_FULFILLED_TRIPS);

  if (loading) {
    return (
      <div style={styles.container}>
        <p style={styles.loadingText}>ACCESSING ARCHIVES...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.container}>
        <p style={styles.errorText} role="alert">⚠ ARCHIVE ERROR: {error.message}</p>
      </div>
    );
  }

  const trips = data?.fulfilledTrips ?? [];

  return (
    <div style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <div>
          <h1 style={styles.title}>CONTRACT ARCHIVE</h1>
          <p style={styles.subtitle}>// FULFILLED MISSIONS</p>
        </div>
        <nav aria-label="Navigation">
          <Link to="/" className="cp-button" style={{ textDecoration: 'none' }}>
            ← ACTIVE CONTRACTS
          </Link>
        </nav>
      </header>

      {/* Divider */}
      <div style={styles.divider} aria-hidden="true" />

      {/* Contract List */}
      {trips.length === 0 ? (
        <div style={styles.emptyState} role="status">
          <p style={styles.emptyIcon}>◇</p>
          <p style={styles.emptyText}>NO FULFILLED CONTRACTS</p>
          <p style={styles.emptySubtext}>Complete a trip to see it archived here.</p>
        </div>
      ) : (
        <section aria-label="Fulfilled contracts list">
          <div style={styles.grid}>
            {trips.map((trip) => {
              const badge = getRecommendationBadge(trip.latestAnalysis?.recommendation);
              return (
                <Link
                  key={trip.id}
                  to={`/trips/${trip.id}`}
                  style={{ textDecoration: 'none' }}
                  aria-label={`View details for ${trip.origin} to ${trip.destination}, fulfilled ${formatFulfilledDate(trip.fulfilledAt)}`}
                >
                  <article className="cp-card" style={styles.card}>
                    <div style={styles.cardHeader}>
                      <span style={styles.route}>
                        {trip.origin} <span style={styles.arrow}>→</span> {trip.destination}
                      </span>
                      <span style={styles.fulfilledBadge}>FULFILLED</span>
                    </div>

                    <div style={styles.cardDates}>
                      <span style={styles.dateLabel}>DEPART //</span>
                      <span style={styles.dateValue}>
                        {formatDate(trip.earliestDeparture)} — {formatDate(trip.latestDeparture)}
                      </span>
                    </div>

                    {trip.earliestReturn && trip.latestReturn && (
                      <div style={styles.cardDates}>
                        <span style={styles.dateLabel}>RETURN //</span>
                        <span style={styles.dateValue}>
                          {formatDate(trip.earliestReturn)} — {formatDate(trip.latestReturn)}
                        </span>
                      </div>
                    )}

                    <div style={styles.cardDates}>
                      <span style={styles.dateLabel}>CLOSED //</span>
                      <span style={styles.dateValue}>
                        {formatFulfilledDate(trip.fulfilledAt)}
                      </span>
                    </div>

                    <div style={styles.recommendationRow}>
                      <span style={styles.dateLabel}>FINAL REC //</span>
                      <span className={badge.className}>{badge.label}</span>
                    </div>

                    {trip.latestAnalysis?.explanation && (
                      <p style={styles.explanation}>{trip.latestAnalysis.explanation}</p>
                    )}

                    <div style={styles.cardFooter}>
                      <span style={styles.cardId}>ID: {String(trip.id).padStart(4, '0')}</span>
                      <span style={styles.cardAction}>VIEW DETAILS →</span>
                    </div>
                  </article>
                </Link>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: 1000,
    margin: '0 auto',
    padding: '2.5rem 1.5rem',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    marginBottom: '1rem',
    flexWrap: 'wrap',
    gap: '1rem',
  },
  title: {
    fontFamily: "'Orbitron', sans-serif",
    fontSize: '2rem',
    fontWeight: 900,
    color: '#FCEE09',
    textShadow: '0 0 10px #FCEE09, 0 0 30px #FCEE0944',
    margin: 0,
    letterSpacing: '3px',
  },
  subtitle: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.85rem',
    color: '#8888aa',
    marginTop: '0.25rem',
  },
  divider: {
    height: '1px',
    background: 'linear-gradient(90deg, #FCEE09, #00F0FF, #FF003C, transparent)',
    marginBottom: '2rem',
    opacity: 0.6,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))',
    gap: '1.25rem',
  },
  card: {
    cursor: 'pointer',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '0.75rem',
  },
  route: {
    fontFamily: "'Orbitron', sans-serif",
    fontSize: '1.2rem',
    fontWeight: 700,
    color: '#e0e0e0',
    letterSpacing: '2px',
  },
  arrow: {
    color: '#FCEE09',
    margin: '0 0.25rem',
  },
  fulfilledBadge: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.7rem',
    color: '#00F0FF',
    border: '1px solid #00F0FF',
    padding: '0.15rem 0.5rem',
    letterSpacing: '1px',
  },
  cardDates: {
    display: 'flex',
    gap: '0.5rem',
    marginBottom: '0.3rem',
  },
  dateLabel: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.75rem',
    color: '#00F0FF',
    minWidth: '5.5rem',
  },
  dateValue: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.75rem',
    color: '#8888aa',
  },
  recommendationRow: {
    display: 'flex',
    gap: '0.5rem',
    alignItems: 'center',
    marginTop: '0.4rem',
    marginBottom: '0.3rem',
  },
  explanation: {
    fontFamily: "'Rajdhani', sans-serif",
    fontSize: '0.8rem',
    color: '#8888aa',
    marginTop: '0.5rem',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    borderTop: '1px solid #2a2a4a',
    paddingTop: '0.5rem',
  },
  cardFooter: {
    display: 'flex',
    justifyContent: 'space-between',
    marginTop: '0.75rem',
    paddingTop: '0.5rem',
    borderTop: '1px solid #2a2a4a',
  },
  cardId: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.7rem',
    color: '#555577',
  },
  cardAction: {
    fontFamily: "'Orbitron', sans-serif",
    fontSize: '0.65rem',
    color: '#FCEE09',
    letterSpacing: '1px',
  },
  emptyState: {
    textAlign: 'center',
    padding: '4rem 1rem',
    border: '1px dashed #2a2a4a',
  },
  emptyIcon: {
    fontSize: '3rem',
    color: '#FCEE09',
    marginBottom: '1rem',
    textShadow: '0 0 20px #FCEE0944',
  },
  emptyText: {
    fontFamily: "'Orbitron', sans-serif",
    fontSize: '1.1rem',
    color: '#8888aa',
    letterSpacing: '2px',
  },
  emptySubtext: {
    fontFamily: "'Rajdhani', sans-serif",
    fontSize: '0.9rem',
    color: '#555577',
    marginTop: '0.5rem',
  },
  loadingText: {
    fontFamily: "'Share Tech Mono', monospace",
    textAlign: 'center',
    color: '#00F0FF',
    fontSize: '1rem',
    marginTop: '4rem',
  },
  errorText: {
    fontFamily: "'Share Tech Mono', monospace",
    textAlign: 'center',
    color: '#FF003C',
    fontSize: '1rem',
    marginTop: '4rem',
  },
};
