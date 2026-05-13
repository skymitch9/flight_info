import { useState } from 'react';

interface FlightSegment {
  airline: string;
  flightNumber: string;
  origin: string;
  destination: string;
  departureTime: string;
  arrivalTime: string;
  durationMinutes: number;
}

interface FlightOption {
  airline: string;
  flightNumber: string;
  departureTime: string;
  arrivalTime: string;
  fareClass: string;
  priceCents: number;
  stops: number;
  totalDurationMinutes: number;
  segments: FlightSegment[];
}

interface FlightOptionsProps {
  options: FlightOption[];
}

function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(0)}`;
}

function formatTime(isoTime: string): string {
  if (!isoTime) return '--';
  try {
    let timePart = isoTime;
    if (isoTime.includes(' ')) {
      timePart = isoTime.split(' ')[1];
    } else if (isoTime.includes('T')) {
      timePart = isoTime.split('T')[1];
    }
    const [hStr, mStr] = timePart.split(':');
    const hour = parseInt(hStr, 10);
    const min = mStr || '00';
    if (isNaN(hour)) return isoTime;
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const hour12 = hour % 12 || 12;
    return `${hour12}:${min} ${ampm}`;
  } catch {
    return isoTime;
  }
}

function formatDuration(minutes: number): string {
  if (!minutes) return '--';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function stopsLabel(stops: number): string {
  if (stops === 0) return 'Nonstop';
  if (stops === 1) return '1 stop';
  return `${stops} stops`;
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

function SegmentDetail({ segments }: { segments: FlightSegment[] }) {
  if (!segments || segments.length === 0) return null;

  return (
    <div style={styles.segmentContainer}>
      {segments.map((seg, i) => (
        <div key={i}>
          <div style={styles.segmentRow}>
            <span style={styles.segmentAirline}>{airlineName(seg.airline)} {seg.flightNumber}</span>
            <span style={styles.segmentRoute}>{seg.origin} → {seg.destination}</span>
            <span style={styles.segmentTime}>{formatTime(seg.departureTime)} – {formatTime(seg.arrivalTime)}</span>
            <span style={styles.segmentDuration}>{formatDuration(seg.durationMinutes)}</span>
          </div>
          {i < segments.length - 1 && (
            <div style={styles.layover}>
              ↓ LAYOVER at {segments[i + 1]?.origin || seg.destination}
              {seg.arrivalTime && segments[i + 1]?.departureTime && (() => {
                const arrParts = seg.arrivalTime.includes(' ') ? seg.arrivalTime.split(' ')[1] : seg.arrivalTime;
                const depParts = segments[i + 1].departureTime.includes(' ') ? segments[i + 1].departureTime.split(' ')[1] : segments[i + 1].departureTime;
                const [ah, am] = arrParts.split(':').map(Number);
                const [dh, dm] = depParts.split(':').map(Number);
                const layoverMin = (dh * 60 + dm) - (ah * 60 + am);
                if (layoverMin > 0) return ` — ${formatDuration(layoverMin)}`;
                return '';
              })()}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function FlightRow({ option }: { option: FlightOption }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr style={styles.tr} onClick={() => setExpanded(!expanded)}>
        <td style={styles.td}>{airlineName(option.airline)}</td>
        <td style={{ ...styles.td, fontFamily: "'Share Tech Mono', monospace" }}>{option.flightNumber}</td>
        <td style={styles.td}>{formatTime(option.departureTime)}</td>
        <td style={styles.td}>{formatTime(option.arrivalTime)}</td>
        <td style={styles.td}>
          <span style={option.stops === 0 ? styles.nonstop : styles.hasStops}>
            {stopsLabel(option.stops)}
          </span>
        </td>
        <td style={styles.td}>{formatDuration(option.totalDurationMinutes)}</td>
        <td style={{ ...styles.td, textAlign: 'right', color: '#00F0FF', fontWeight: 700 }}>
          {formatPrice(option.priceCents)}
        </td>
        <td style={{ ...styles.td, color: '#555577', cursor: 'pointer' }}>
          {option.segments.length > 0 ? (expanded ? '▾' : '▸') : ''}
        </td>
      </tr>
      {expanded && option.segments.length > 0 && (
        <tr>
          <td colSpan={8} style={{ padding: 0 }}>
            <SegmentDetail segments={option.segments} />
          </td>
        </tr>
      )}
    </>
  );
}

export default function FlightOptions({ options }: FlightOptionsProps) {
  if (!options || options.length === 0) {
    return (
      <p style={styles.noData}>
        No flight data available. Run a scan to collect prices.
      </p>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>AIRLINE</th>
            <th style={styles.th}>FLIGHT</th>
            <th style={styles.th}>DEP</th>
            <th style={styles.th}>ARR</th>
            <th style={styles.th}>STOPS</th>
            <th style={styles.th}>DURATION</th>
            <th style={{ ...styles.th, textAlign: 'right' }}>PRICE</th>
            <th style={styles.th}></th>
          </tr>
        </thead>
        <tbody>
          {options.map((option, index) => (
            <FlightRow key={index} option={option} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
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
    cursor: 'pointer',
  },
  td: {
    padding: '0.6rem 0.75rem',
    color: '#e0e0e0',
  },
  nonstop: {
    color: '#00F0FF',
    fontSize: '0.8rem',
  },
  hasStops: {
    color: '#FCEE09',
    fontSize: '0.8rem',
  },
  noData: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.8rem',
    color: '#555577',
  },
  segmentContainer: {
    background: '#0f0f18',
    padding: '0.75rem 1.5rem',
    borderLeft: '2px solid #2a2a4a',
    margin: '0 0.75rem 0.5rem 2rem',
  },
  segmentRow: {
    display: 'flex',
    gap: '1.5rem',
    padding: '0.3rem 0',
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.75rem',
    color: '#8888aa',
  },
  segmentAirline: {
    minWidth: '140px',
    color: '#e0e0e0',
  },
  segmentRoute: {
    minWidth: '80px',
    color: '#00F0FF',
  },
  segmentTime: {
    minWidth: '140px',
  },
  segmentDuration: {
    color: '#555577',
  },
  layover: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.7rem',
    color: '#FCEE09',
    padding: '0.2rem 0 0.2rem 1rem',
    borderLeft: '1px dashed #FCEE0944',
    margin: '0.2rem 0',
  },
};
