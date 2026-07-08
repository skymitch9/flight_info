import { useState } from 'react';
import { useQuery, useMutation } from '@apollo/client/react';
import { Link } from 'react-router-dom';
import { GET_TRIPS, TRIGGER_COLLECTION } from '../graphql/queries';
import TripForm from '../components/TripForm';

interface AnalysisResult {
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
  earliestReturn: string | null;
  latestReturn: string | null;
  isActive: boolean;
  collectionStartsOn: string | null;
  lastCollectedAt: string | null;
  latestAnalysis: AnalysisResult | null;
}

interface TripsData {
  trips: Trip[];
}

function getRecommendationBadge(recommendation: string | undefined) {
  if (!recommendation) return { label: 'PENDING', className: 'cp-badge cp-badge--pending' };
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

function formatAgo(isoTimestamp: string | null): string | null {
  if (!isoTimestamp) return null;
  // Backend timestamps are UTC without a zone suffix
  const ts = new Date(isoTimestamp.endsWith('Z') ? isoTimestamp : isoTimestamp + 'Z').getTime();
  if (isNaN(ts)) return null;
  const mins = Math.floor((Date.now() - ts) / 60000);
  if (mins < 1) return 'JUST NOW';
  if (mins < 60) return `${mins}M AGO`;
  const hours = Math.floor(mins / 60);
  if (hours < 48) return `${hours}H AGO`;
  return `${Math.floor(hours / 24)}D AGO`;
}

export default function TripList() {
  const [showForm, setShowForm] = useState(false);
  const [scanStatus, setScanStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const { data, loading, error } = useQuery<TripsData>(GET_TRIPS);
  const [triggerCollection] = useMutation(TRIGGER_COLLECTION, {
    refetchQueries: [{ query: GET_TRIPS }],
  });

  const handleScan = async () => {
    setScanStatus('running');
    try {
      await triggerCollection();
      setScanStatus('done');
      setTimeout(() => setScanStatus('idle'), 4000);
    } catch {
      setScanStatus('error');
      setTimeout(() => setScanStatus('idle'), 5000);
    }
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <p style={styles.loadingText}>INITIALIZING NEURAL LINK...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.container}>
        <p style={styles.errorText}>⚠ SYSTEM ERROR: {error.message}</p>
      </div>
    );
  }

  const trips = data?.trips ?? [];

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>FLIGHT TRACKER</h1>
          <p style={styles.subtitle}>// NIGHT CITY DEPARTURES</p>
        </div>
        <div style={styles.actions}>
          <Link to="/history" className="cp-button" style={{ textDecoration: 'none' }}>
            ◈ CONTRACT ARCHIVE
          </Link>
          <button
            className="cp-button cp-button--cyan"
            onClick={handleScan}
            disabled={scanStatus === 'running'}
          >
            {scanStatus === 'running' ? '◌ SCANNING...' : '⟳ RUN SCAN'}
          </button>
          <button className="cp-button" onClick={() => setShowForm(true)}>
            + NEW TRIP
          </button>
        </div>
      </div>

      {/* Scan status feedback */}
      {scanStatus === 'running' && (
        <div style={styles.scanBanner}>
          <span style={styles.scanPulse}>●</span> REQUESTING SCAN...
        </div>
      )}
      {scanStatus === 'done' && (
        <div style={{ ...styles.scanBanner, borderColor: '#00F0FF', color: '#00F0FF' }}>
          ✓ SCAN STARTED — RUNS IN BACKGROUND, PRICES REFRESH IN A FEW MINUTES
        </div>
      )}
      {scanStatus === 'error' && (
        <div style={{ ...styles.scanBanner, borderColor: '#FF003C', color: '#FF003C' }}>
          ✗ SCAN FAILED — CHECK SYSTEM LOGS
        </div>
      )}

      {/* Divider */}
      <div style={styles.divider} />

      {/* Trip Grid */}
      {trips.length === 0 ? (
        <div style={styles.emptyState}>
          {/* Drop scene-city.jpg in public/images/cyberpunk/ for this background */}
          <div style={styles.emptyBg} />
          <p style={styles.emptyIcon}>◇</p>
          <p style={styles.emptyText}>NO ACTIVE CONTRACTS</p>
          <p style={styles.emptySubtext}>Create a trip to start tracking flight prices, choom.</p>
        </div>
      ) : (
        <div style={styles.grid}>
          {trips.map((trip) => {
            const badge = trip.collectionStartsOn
              ? { label: `TRACKING FROM ${formatDate(trip.collectionStartsOn)}`, className: 'cp-badge cp-badge--pending' }
              : getRecommendationBadge(trip.latestAnalysis?.recommendation);
            const updatedAgo = formatAgo(trip.lastCollectedAt);
            return (
              <Link key={trip.id} to={`/trips/${trip.id}`} style={{ textDecoration: 'none' }}>
                <div className="cp-card" style={styles.card}>
                  <div style={styles.cardHeader}>
                    <span style={styles.route}>
                      {trip.origin} <span style={styles.arrow}>→</span> {trip.destination}
                    </span>
                    <span className={badge.className}>{badge.label}</span>
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

                  {trip.latestAnalysis?.explanation && (
                    <p style={styles.explanation}>{trip.latestAnalysis.explanation}</p>
                  )}

                  <div style={styles.cardFooter}>
                    <span style={styles.cardId}>ID: {String(trip.id).padStart(4, '0')}</span>
                    {updatedAgo && <span style={styles.cardId}>UPDATED {updatedAgo}</span>}
                    <span style={styles.cardAction}>ACCESS →</span>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {/* Trip Form Modal */}
      {showForm && <TripForm onClose={() => setShowForm(false)} />}
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
  actions: {
    display: 'flex',
    gap: '0.75rem',
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
    position: 'relative',
    overflow: 'hidden',
  },
  emptyBg: {
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundImage: "url('/images/cyberpunk/1273320.jpg')",
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    opacity: 0.15,
    zIndex: 0,
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
    animation: 'flicker 2s infinite',
  },
  errorText: {
    fontFamily: "'Share Tech Mono', monospace",
    textAlign: 'center',
    color: '#FF003C',
    fontSize: '1rem',
    marginTop: '4rem',
  },
  scanBanner: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.8rem',
    color: '#FCEE09',
    border: '1px solid #FCEE09',
    background: '#FCEE0910',
    padding: '0.6rem 1rem',
    marginBottom: '1.5rem',
    letterSpacing: '1px',
  },
  scanPulse: {
    display: 'inline-block',
    animation: 'flicker 1s infinite',
    marginRight: '0.5rem',
  },
};
