import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation } from '@apollo/client/react';
import { GET_TRIP_DETAIL, DELETE_TRIP, GET_TRIPS, TRIGGER_COLLECTION, FULFILL_TRIP, GET_FULFILLED_TRIPS } from '../graphql/queries';
import PriceChart from '../components/PriceChart';
import FlightOptions from '../components/FlightOptions';
import TripForm from '../components/TripForm';

interface PriceHistoryEntry {
  airlineCode: string;
  fareClass: string;
  priceCents: number;
  flightDate: string;
  collectedAt: string;
}

interface AnalysisResult {
  recommendation: string;
  explanation: string;
  analyzedAt: string;
}

interface FlightOption {
  airline: string;
  flightNumber: string;
  departureTime: string;
  arrivalTime: string;
  fareClass: string;
  priceCents: number;
  totalPriceCents: number;
  flightDate: string;
  stops: number;
  totalDurationMinutes: number;
  segments: {
    airline: string;
    flightNumber: string;
    origin: string;
    destination: string;
    departureTime: string;
    arrivalTime: string;
    durationMinutes: number;
  }[];
}

interface RoundTripOption {
  outbound: FlightOption;
  returnFlight: FlightOption;
  combinedPriceCents: number;
  totalCombinedPriceCents: number;
}

interface TripData {
  trip: {
    id: number;
    origin: string;
    destination: string;
    earliestDeparture: string;
    latestDeparture: string;
    earliestReturn: string | null;
    latestReturn: string | null;
    isActive: boolean;
    status: string;
    passengerCount: number;
    carryOnBags: number;
    checkedBags: number;
    targetPriceCents: number | null;
    maxStops: number | null;
    collectionStartsOn: string | null;
    lastCollectedAt: string | null;
    priceHistory: PriceHistoryEntry[];
    latestAnalysis: AnalysisResult | null;
    topFlightOptions: FlightOption[];
    roundTripOptions: RoundTripOption[];
  } | null;
}

function getBadgeClass(recommendation: string | undefined): string {
  if (!recommendation) return 'cp-badge cp-badge--wait';
  switch (recommendation) {
    case 'buy_now': return 'cp-badge cp-badge--buy';
    case 'prices_rising': return 'cp-badge cp-badge--rising';
    default: return 'cp-badge cp-badge--wait';
  }
}

function getBadgeLabel(recommendation: string | undefined): string {
  if (!recommendation) return 'NO DATA';
  switch (recommendation) {
    case 'buy_now': return 'BUY NOW';
    case 'prices_rising': return 'PRICES RISING';
    case 'wait': return 'WAIT';
    default: return recommendation.toUpperCase();
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

export default function TripDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [showEditModal, setShowEditModal] = useState(false);
  const tripId = parseInt(id ?? '0', 10);

  const { data, loading, error } = useQuery<TripData>(GET_TRIP_DETAIL, {
    variables: { tripId },
    skip: !tripId,
  });

  const [deleteTrip, { loading: deleting }] = useMutation(DELETE_TRIP, {
    variables: { tripId },
    refetchQueries: [{ query: GET_TRIPS }],
    onCompleted: () => navigate('/'),
  });

  const [triggerCollection, { loading: scanning }] = useMutation(TRIGGER_COLLECTION, {
    refetchQueries: [{ query: GET_TRIP_DETAIL, variables: { tripId } }],
  });

  const [fulfillTrip, { loading: fulfilling }] = useMutation(FULFILL_TRIP, {
    variables: { tripId },
    refetchQueries: [{ query: GET_TRIPS }, { query: GET_FULFILLED_TRIPS }],
    onCompleted: () => navigate('/history'),
  });

  if (loading) {
    return (
      <div style={styles.container}>
        <p style={styles.loadingText}>◌ ACCESSING NETRUNNER DATABASE...</p>
      </div>
    );
  }

  if (error || !data?.trip) {
    return (
      <div style={styles.container}>
        <p style={styles.errorText}>⚠ {error?.message || 'CONTRACT NOT FOUND'}</p>
        <Link to="/" style={styles.backLink}>← RETURN TO HQ</Link>
      </div>
    );
  }

  const trip = data.trip;

  function handleDelete() {
    if (window.confirm('Flatline this contract? This cannot be undone.')) {
      deleteTrip();
    }
  }

  function handleFulfill() {
    if (window.confirm('Mark this contract as fulfilled? It will move to your history.')) {
      fulfillTrip();
    }
  }

  return (
    <div style={styles.container}>
      <Link to="/" style={styles.backLink}>← BACK TO CONTRACTS</Link>

      {/* Hero accent image */}
      <div style={styles.heroAccent} />

      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>
            {trip.origin} <span style={styles.arrow}>→</span> {trip.destination}
          </h1>
          <div style={styles.dates}>
            <span style={styles.dateLabel}>DEPART //</span>
            <span style={styles.dateValue}>{formatDate(trip.earliestDeparture)} — {formatDate(trip.latestDeparture)}</span>
            {trip.earliestReturn && trip.latestReturn && (
              <>
                <span style={{ ...styles.dateLabel, marginLeft: '1.5rem' }}>RETURN //</span>
                <span style={styles.dateValue}>{formatDate(trip.earliestReturn)} — {formatDate(trip.latestReturn)}</span>
              </>
            )}
          </div>
          <div style={styles.dates}>
            {trip.targetPriceCents != null && (
              <>
                <span style={styles.dateLabel}>TARGET //</span>
                <span style={styles.dateValue}>${Math.round(trip.targetPriceCents / 100)} MAIN CABIN{trip.earliestReturn ? ' (ROUND-TRIP TOTAL)' : ' PER TICKET'}</span>
              </>
            )}
            {trip.maxStops != null && (
              <>
                <span style={{ ...styles.dateLabel, marginLeft: '1.5rem' }}>STOPS //</span>
                <span style={styles.dateValue}>{trip.maxStops === 0 ? 'NONSTOP ONLY' : `UP TO ${trip.maxStops}`}</span>
              </>
            )}
            {trip.lastCollectedAt && (
              <>
                <span style={{ ...styles.dateLabel, marginLeft: trip.targetPriceCents != null ? '1.5rem' : 0 }}>UPDATED //</span>
                <span style={styles.dateValue}>
                  {new Date(trip.lastCollectedAt.endsWith('Z') ? trip.lastCollectedAt : trip.lastCollectedAt + 'Z').toLocaleString()}
                </span>
              </>
            )}
            {trip.collectionStartsOn && (
              <>
                <span style={styles.dateLabel}>TRACKING //</span>
                <span style={styles.dateValue}>STARTS {formatDate(trip.collectionStartsOn)} (FARES NOT PUBLISHED YET)</span>
              </>
            )}
          </div>
        </div>
        <div style={styles.actions}>
          <button className="cp-button" onClick={() => triggerCollection()} disabled={scanning}>
            {scanning ? '◌ SCANNING...' : '⟳ RUN SCAN'}
          </button>
          {trip.status === 'active' && (
            <button className="cp-button cp-button--green" onClick={handleFulfill} disabled={fulfilling}>
              {fulfilling ? '◌ PROCESSING...' : '✓ FULFILLED'}
            </button>
          )}
          <button className="cp-button cp-button--cyan" onClick={() => setShowEditModal(true)}>
            EDIT
          </button>
          <button className="cp-button cp-button--magenta" onClick={handleDelete} disabled={deleting}>
            {deleting ? '...' : 'FLATLINE'}
          </button>
        </div>
      </div>

      <div style={styles.divider} />

      {/* Recommendation */}
      <div style={styles.section}>
        <div style={styles.recRow}>
          <span className={getBadgeClass(trip.latestAnalysis?.recommendation)}>
            {getBadgeLabel(trip.latestAnalysis?.recommendation)}
          </span>
          {trip.latestAnalysis?.analyzedAt && (
            <span style={styles.analyzedAt}>
              SCANNED {new Date(trip.latestAnalysis.analyzedAt).toLocaleDateString()}
            </span>
          )}
        </div>
        {trip.latestAnalysis?.explanation ? (
          <p style={styles.explanation}>{trip.latestAnalysis.explanation}</p>
        ) : (
          <p style={styles.noData}>Awaiting next scan cycle for analysis data...</p>
        )}
      </div>

      {/* Price Chart */}
      <div style={styles.section}>
        <h2 style={styles.sectionTitle}>PRICE TELEMETRY</h2>
        <div style={styles.chartContainer}>
          <PriceChart priceHistory={trip.priceHistory} />
        </div>
      </div>

      {/* Flight Options */}
      <div style={styles.section}>
        <h2 style={styles.sectionTitle}>AVAILABLE FLIGHTS</h2>
        <FlightOptions
          options={trip.topFlightOptions}
          roundTripOptions={trip.roundTripOptions}
          origin={trip.origin}
          destination={trip.destination}
        />
      </div>

      {/* Edit Modal */}
      {showEditModal && (
        <TripForm
          onClose={() => setShowEditModal(false)}
          existingTrip={{
            id: trip.id,
            origin: trip.origin,
            destination: trip.destination,
            earliestDeparture: trip.earliestDeparture,
            latestDeparture: trip.latestDeparture,
            earliestReturn: trip.earliestReturn,
            latestReturn: trip.latestReturn,
            passengerCount: trip.passengerCount,
            carryOnBags: trip.carryOnBags,
            checkedBags: trip.checkedBags,
            targetPriceCents: trip.targetPriceCents,
            maxStops: trip.maxStops,
          }}
        />
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
  backLink: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.8rem',
    color: '#FCEE09',
    textDecoration: 'none',
    display: 'inline-block',
    marginBottom: '1.5rem',
    letterSpacing: '1px',
  },
  heroAccent: {
    width: '100%',
    height: '120px',
    backgroundImage: "url('/images/cyberpunk/1273320.jpg')",
    backgroundSize: 'cover',
    backgroundPosition: 'center 30%',
    opacity: 0.25,
    marginBottom: '1.5rem',
    borderLeft: '3px solid #FCEE09',
    clipPath: 'polygon(0 0, calc(100% - 30px) 0, 100% 30px, 100% 100%, 0 100%)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    gap: '1rem',
    marginBottom: '1rem',
  },
  title: {
    fontFamily: "'Orbitron', sans-serif",
    fontSize: '1.8rem',
    fontWeight: 900,
    color: '#e0e0e0',
    margin: 0,
    letterSpacing: '3px',
  },
  arrow: {
    color: '#FCEE09',
    textShadow: '0 0 10px #FCEE09',
  },
  dates: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    marginTop: '0.5rem',
    flexWrap: 'wrap',
  },
  dateLabel: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.75rem',
    color: '#00F0FF',
  },
  dateValue: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.75rem',
    color: '#8888aa',
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
  section: {
    marginBottom: '2.5rem',
  },
  sectionTitle: {
    fontFamily: "'Orbitron', sans-serif",
    fontSize: '0.9rem',
    fontWeight: 600,
    color: '#FCEE09',
    letterSpacing: '2px',
    marginBottom: '1rem',
    paddingBottom: '0.5rem',
    borderBottom: '1px solid #2a2a4a',
  },
  recRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '1rem',
    marginBottom: '0.75rem',
  },
  analyzedAt: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.7rem',
    color: '#555577',
  },
  explanation: {
    fontFamily: "'Rajdhani', sans-serif",
    fontSize: '0.95rem',
    color: '#8888aa',
    lineHeight: 1.6,
  },
  noData: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.8rem',
    color: '#555577',
    fontStyle: 'italic',
  },
  chartContainer: {
    background: '#12121a',
    border: '1px solid #2a2a4a',
    padding: '1rem',
    borderRadius: '2px',
  },
  loadingText: {
    fontFamily: "'Share Tech Mono', monospace",
    textAlign: 'center',
    color: '#00F0FF',
    marginTop: '4rem',
  },
  errorText: {
    fontFamily: "'Share Tech Mono', monospace",
    textAlign: 'center',
    color: '#FF003C',
    marginTop: '4rem',
    marginBottom: '1rem',
  },
};
