interface FlightOption {
  airline: string;
  flightNumber: string;
  departureTime: string;
  arrivalTime: string;
  fareClass: string;
  priceCents: number;
}

interface FlightOptionsProps {
  options: FlightOption[];
}

function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function formatTime(isoTime: string): string {
  try {
    // Handle "YYYY-MM-DD HH:MM" format
    if (isoTime.includes(' ') && isoTime.length >= 16) {
      const timePart = isoTime.split(' ')[1];
      const [h, m] = timePart.split(':');
      const hour = parseInt(h, 10);
      const ampm = hour >= 12 ? 'PM' : 'AM';
      const hour12 = hour % 12 || 12;
      return `${hour12}:${m} ${ampm}`;
    }
    const date = new Date(isoTime);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return isoTime;
  }
}

const AIRLINE_NAMES: Record<string, string> = {
  AA: 'American',
  DL: 'Delta',
  UA: 'United',
  WN: 'Southwest',
  F9: 'Frontier',
  NK: 'Spirit',
  B6: 'JetBlue',
  AS: 'Alaska',
  HA: 'Hawaiian',
  SY: 'Sun Country',
  G4: 'Allegiant',
};

function airlineName(code: string): string {
  return AIRLINE_NAMES[code] || code;
}

function OptionsTable({ options, title, accentColor }: { options: FlightOption[]; title: string; accentColor: string }) {
  if (options.length === 0) return null;

  return (
    <div style={{ marginBottom: '1.5rem' }}>
      <h4 style={{ ...styles.tableTitle, borderLeftColor: accentColor }}>{title}</h4>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>AIRLINE</th>
            <th style={styles.th}>FLIGHT</th>
            <th style={styles.th}>DEP</th>
            <th style={styles.th}>ARR</th>
            <th style={{ ...styles.th, textAlign: 'right' }}>PRICE</th>
          </tr>
        </thead>
        <tbody>
          {options.map((option, index) => (
            <tr key={index} style={styles.tr}>
              <td style={styles.td}>{airlineName(option.airline)}</td>
              <td style={{ ...styles.td, fontFamily: "'Share Tech Mono', monospace" }}>{option.flightNumber}</td>
              <td style={styles.td}>{formatTime(option.departureTime)}</td>
              <td style={styles.td}>{formatTime(option.arrivalTime)}</td>
              <td style={{ ...styles.td, textAlign: 'right', color: accentColor, fontWeight: 700 }}>
                {formatPrice(option.priceCents)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function FlightOptions({ options }: FlightOptionsProps) {
  const targetFare = options.filter((o) => o.fareClass === 'main_cabin');
  const premiumFare = options.filter((o) => o.fareClass !== 'main_cabin');

  if (options.length === 0) {
    return (
      <p style={styles.noData}>
        No flight data available. Run a scan to collect prices.
      </p>
    );
  }

  return (
    <div>
      <OptionsTable options={targetFare} title="TARGET FARE // MAIN CABIN" accentColor="#00F0FF" />
      <OptionsTable options={premiumFare} title="PREMIUM FARE // UPGRADE" accentColor="#FCEE09" />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  tableTitle: {
    fontFamily: "'Orbitron', sans-serif",
    fontSize: '0.7rem',
    fontWeight: 600,
    color: '#8888aa',
    letterSpacing: '1.5px',
    marginBottom: '0.75rem',
    paddingLeft: '0.75rem',
    borderLeft: '3px solid',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontFamily: "'Rajdhani', sans-serif",
    fontSize: '0.9rem',
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
    padding: '0.6rem 0.75rem',
    color: '#e0e0e0',
  },
  noData: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.8rem',
    color: '#555577',
  },
};
