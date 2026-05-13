import { useQuery } from '@apollo/client/react';
import { GET_ROUTE } from '../graphql/queries';

interface PriceHistoryEntry {
  airlineCode: string;
  fareClass: string;
  priceCents: number;
  flightDate: string;
  collectedAt: string;
}

interface ActiveContract {
  id: number;
  origin: string;
  destination: string;
  earliestDeparture: string;
  latestDeparture: string;
  status: string;
}

interface RouteData {
  route: {
    id: number;
    origin: string;
    destination: string;
    status: string;
    lastCollectedAt: string | null;
    priceHistory: PriceHistoryEntry[];
    activeContracts: ActiveContract[];
  } | null;
}

interface RoutePriceHistoryProps {
  routeId: number;
}

function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(0)}`;
}

function formatCollectedAt(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export default function RoutePriceHistory({ routeId }: RoutePriceHistoryProps) {
  const { data, loading, error } = useQuery<RouteData>(GET_ROUTE, {
    variables: { routeId },
    skip: !routeId,
  });

  if (loading) {
    return (
      <div style={styles.container}>
        <p style={styles.loadingText}>◌ LOADING ROUTE TELEMETRY...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.container}>
        <p style={styles.errorText} role="alert">⚠ ROUTE DATA ERROR: {error.message}</p>
      </div>
    );
  }

  if (!data?.route) {
    return (
      <div style={styles.container}>
        <p style={styles.errorText}>⚠ ROUTE NOT FOUND</p>
      </div>
    );
  }

  const route = data.route;

  return (
    <div style={styles.container}>
      {/* Route Header */}
      <header style={styles.header}>
        <div>
          <h2 style={styles.title}>
            {route.origin} <span style={styles.arrow}>→</span> {route.destination}
          </h2>
          <div style={styles.meta}>
            <span style={styles.statusBadge} data-status={route.status}>
              {route.status.toUpperCase()}
            </span>
            {route.lastCollectedAt && (
              <span style={styles.lastCollected}>
                LAST SCAN // {formatCollectedAt(route.lastCollectedAt)}
              </span>
            )}
          </div>
        </div>
      </header>

      <div style={styles.divider} aria-hidden="true" />

      {/* Active Contracts Section */}
      <section style={styles.section}>
        <h3 style={styles.sectionTitle}>ACTIVE CONTRACTS ON ROUTE</h3>
        {route.activeContracts.length === 0 ? (
          <p style={styles.noData}>No active contracts on this route.</p>
        ) : (
          <div style={styles.contractGrid}>
            {route.activeContracts.map((contract) => (
              <div key={contract.id} style={styles.contractCard}>
                <div style={styles.contractHeader}>
                  <span style={styles.contractId}>ID: {String(contract.id).padStart(4, '0')}</span>
                  <span
                    style={
                      contract.status === 'active'
                        ? styles.contractStatusActive
                        : styles.contractStatusFulfilled
                    }
                  >
                    {contract.status.toUpperCase()}
                  </span>
                </div>
                <div style={styles.contractDates}>
                  <span style={styles.dateLabel}>DEPART //</span>
                  <span style={styles.dateValue}>
                    {formatDate(contract.earliestDeparture)} — {formatDate(contract.latestDeparture)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Price History Section */}
      <section style={styles.section}>
        <h3 style={styles.sectionTitle}>ALL-TIME PRICE HISTORY</h3>
        {route.priceHistory.length === 0 ? (
          <p style={styles.noData}>No price data collected yet. Run a scan to begin tracking.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>COLLECTED</th>
                  <th style={styles.th}>AIRLINE</th>
                  <th style={styles.th}>CLASS</th>
                  <th style={{ ...styles.th, textAlign: 'right' }}>PRICE</th>
                  <th style={styles.th}>FLIGHT DATE</th>
                </tr>
              </thead>
              <tbody>
                {route.priceHistory.map((entry, index) => (
                  <tr key={index} style={styles.tr}>
                    <td style={{ ...styles.td, color: '#8888aa' }}>
                      {formatCollectedAt(entry.collectedAt)}
                    </td>
                    <td style={styles.td}>{entry.airlineCode}</td>
                    <td style={{ ...styles.td, color: '#FCEE09' }}>{entry.fareClass}</td>
                    <td style={{ ...styles.td, textAlign: 'right', color: '#00F0FF', fontWeight: 700 }}>
                      {formatPrice(entry.priceCents)}
                    </td>
                    <td style={styles.td}>{formatDate(entry.flightDate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p style={styles.recordCount}>
              {route.priceHistory.length} RECORD{route.priceHistory.length !== 1 ? 'S' : ''} TOTAL
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: 1000,
    margin: '0 auto',
  },
  header: {
    marginBottom: '1rem',
  },
  title: {
    fontFamily: "'Orbitron', sans-serif",
    fontSize: '1.5rem',
    fontWeight: 900,
    color: '#e0e0e0',
    margin: 0,
    letterSpacing: '3px',
  },
  arrow: {
    color: '#FCEE09',
    textShadow: '0 0 10px #FCEE09',
  },
  meta: {
    display: 'flex',
    alignItems: 'center',
    gap: '1rem',
    marginTop: '0.5rem',
  },
  statusBadge: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.7rem',
    color: '#00F0FF',
    border: '1px solid #00F0FF',
    padding: '0.15rem 0.5rem',
    letterSpacing: '1px',
  },
  lastCollected: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.7rem',
    color: '#555577',
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
  contractGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: '0.75rem',
  },
  contractCard: {
    background: '#12121a',
    border: '1px solid #2a2a4a',
    padding: '0.75rem 1rem',
  },
  contractHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '0.5rem',
  },
  contractId: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.75rem',
    color: '#8888aa',
  },
  contractStatusActive: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.65rem',
    color: '#00F0FF',
    border: '1px solid #00F0FF',
    padding: '0.1rem 0.4rem',
    letterSpacing: '1px',
  },
  contractStatusFulfilled: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.65rem',
    color: '#FCEE09',
    border: '1px solid #FCEE09',
    padding: '0.1rem 0.4rem',
    letterSpacing: '1px',
  },
  contractDates: {
    display: 'flex',
    gap: '0.5rem',
  },
  dateLabel: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.7rem',
    color: '#00F0FF',
  },
  dateValue: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.7rem',
    color: '#8888aa',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.8rem',
  },
  th: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.65rem',
    color: '#555577',
    textAlign: 'left',
    padding: '0.5rem 0.75rem',
    borderBottom: '1px solid #2a2a4a',
    letterSpacing: '1px',
  },
  tr: {
    borderBottom: '1px solid #1a1a2e',
  },
  td: {
    padding: '0.5rem 0.75rem',
    color: '#e0e0e0',
  },
  noData: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.8rem',
    color: '#555577',
    fontStyle: 'italic',
  },
  recordCount: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.7rem',
    color: '#555577',
    marginTop: '0.75rem',
    textAlign: 'right',
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
