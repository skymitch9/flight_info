import { useState, useMemo } from 'react';

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
  totalPriceCents: number;
  flightDate: string;
  stops: number;
  totalDurationMinutes: number;
  segments: FlightSegment[];
}

interface RoundTripOption {
  outbound: FlightOption;
  returnFlight: FlightOption;
  combinedPriceCents: number;
  totalCombinedPriceCents: number;
}

interface FlightOptionsProps {
  options: FlightOption[];
  roundTripOptions?: RoundTripOption[];
  origin: string;
  destination: string;
}

function googleFlightsUrl(origin: string, destination: string, date: string): string {
  const q = `Flights from ${origin} to ${destination} on ${date}`;
  return `https://www.google.com/travel/flights?q=${encodeURIComponent(q)}`;
}

const ALL_TAB = 'All';

const FARE_CLASS_ORDER = ['main_cabin', 'premium_economy', 'business', 'first'];

function getUniqueFareClasses(options: FlightOption[]): string[] {
  const seen = new Set<string>();
  for (const o of options) {
    if (o.fareClass) seen.add(o.fareClass);
  }
  // Sort by predefined order, unknown classes go at the end
  return Array.from(seen).sort((a, b) => {
    const ai = FARE_CLASS_ORDER.indexOf(a.toLowerCase());
    const bi = FARE_CLASS_ORDER.indexOf(b.toLowerCase());
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
  });
}

function formatFareClassLabel(fareClass: string): string {
  return fareClass
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

function filterByFareClass(options: FlightOption[], fareClass: string): FlightOption[] {
  if (fareClass === ALL_TAB) return options;
  return options.filter(o => o.fareClass.toLowerCase() === fareClass.toLowerCase());
}

function filterRoundTripsByFareClass(roundTrips: RoundTripOption[], fareClass: string): RoundTripOption[] {
  if (fareClass === ALL_TAB) return roundTrips;
  const lower = fareClass.toLowerCase();
  return roundTrips.filter(
    rt => rt.outbound.fareClass.toLowerCase() === lower
       && rt.returnFlight.fareClass.toLowerCase() === lower
  );
}

function countByFareClass(options: FlightOption[], fareClasses: string[]): Record<string, number> {
  const counts: Record<string, number> = { [ALL_TAB]: options.length };
  for (const fc of fareClasses) {
    counts[fc] = options.filter(o => o.fareClass.toLowerCase() === fc.toLowerCase()).length;
  }
  return counts;
}

function formatBadgeCount(count: number): string {
  return count > 999 ? '999+' : String(count);
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

function formatFlightDate(dateStr: string): string {
  if (!dateStr) return '--';
  try {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
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

interface FareClassTabsProps {
  activeTab: string;
  onTabChange: (fareClass: string) => void;
  counts: Record<string, number>;
  fareClasses: string[];
}

function FareClassTabs({ activeTab, onTabChange, counts, fareClasses }: FareClassTabsProps) {
  const tabs = [ALL_TAB, ...fareClasses];
  return (
    <div style={styles.tabBar}>
      {tabs.map((fc) => {
        const isActive = fc === activeTab;
        return (
          <button
            key={fc}
            onClick={() => onTabChange(fc)}
            style={isActive ? styles.tabActive : styles.tabInactive}
          >
            <span style={styles.tabLabel}>{fc === ALL_TAB ? 'All' : formatFareClassLabel(fc)}</span>
            <span style={styles.tabBadge}>{formatBadgeCount(counts[fc] || 0)}</span>
          </button>
        );
      })}
    </div>
  );
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

function FlightRow({ option, origin, destination }: { option: FlightOption; origin: string; destination: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr style={styles.tr} onClick={() => setExpanded(!expanded)}>
        <td style={styles.td}>
          <span style={styles.dateBadge}>{formatFlightDate(option.flightDate)}</span>
        </td>
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
        <td style={{ ...styles.td, textAlign: 'right' }}>
          <span style={{ color: '#8888aa', fontSize: '0.8rem' }}>{formatPrice(option.priceCents)}</span>
          {option.totalPriceCents !== option.priceCents && (
            <span style={{ color: '#00F0FF', fontWeight: 700, marginLeft: '0.5rem' }}>{formatPrice(option.totalPriceCents)}</span>
          )}
          {option.totalPriceCents === option.priceCents && (
            <span style={{ color: '#00F0FF', fontWeight: 700, marginLeft: '0.5rem' }}>{formatPrice(option.priceCents)}</span>
          )}
        </td>
        <td style={styles.td}>
          <a
            href={googleFlightsUrl(origin, destination, option.flightDate)}
            target="_blank"
            rel="noopener noreferrer"
            style={styles.bookLink}
            onClick={(e) => e.stopPropagation()}
            title="Open this route and date on Google Flights"
          >
            BOOK ↗
          </a>
        </td>
        <td style={{ ...styles.td, color: '#555577', cursor: 'pointer' }}>
          {option.segments.length > 0 ? (expanded ? '▾' : '▸') : ''}
        </td>
      </tr>
      {expanded && option.segments.length > 0 && (
        <tr>
          <td colSpan={10} style={{ padding: 0 }}>
            <SegmentDetail segments={option.segments} />
          </td>
        </tr>
      )}
    </>
  );
}

export default function FlightOptions({ options, roundTripOptions, origin, destination }: FlightOptionsProps) {
  const [activeTab, setActiveTab] = useState(ALL_TAB);
  const [selectedAirlines, setSelectedAirlines] = useState<Set<string>>(new Set());
  const [minPrice, setMinPrice] = useState<string>('');
  const [maxPrice, setMaxPrice] = useState<string>('');
  const [maxStops, setMaxStops] = useState<number>(-1); // -1 = any
  // Get unique airlines from all options
  const availableAirlines = useMemo(() => {
    const airlines = new Set<string>();
    for (const o of options) {
      if (o.airline) airlines.add(o.airline);
    }
    return Array.from(airlines).sort();
  }, [options]);

  // Initialize selected airlines to all when options change
  useMemo(() => {
    if (selectedAirlines.size === 0 && availableAirlines.length > 0) {
      setSelectedAirlines(new Set(availableAirlines));
    }
  }, [availableAirlines]);

  const fareClasses = useMemo(() => getUniqueFareClasses(options), [options]);
  const counts = useMemo(() => countByFareClass(options, fareClasses), [options, fareClasses]);

  // Apply fare class filter, then airline + price filters
  const filteredOptions = useMemo(() => {
    let result = filterByFareClass(options, activeTab);
    // Airline filter
    if (selectedAirlines.size > 0 && selectedAirlines.size < availableAirlines.length) {
      result = result.filter(o => selectedAirlines.has(o.airline));
    }
    // Price filter (using totalPriceCents, input is in dollars)
    const min = minPrice ? parseInt(minPrice) * 100 : 0;
    const max = maxPrice ? parseInt(maxPrice) * 100 : Infinity;
    if (min > 0 || max < Infinity) {
      result = result.filter(o => o.totalPriceCents >= min && o.totalPriceCents <= max);
    }
    // Stops filter
    if (maxStops >= 0) {
      result = result.filter(o => o.stops <= maxStops);
    }
    return result;
  }, [options, activeTab, selectedAirlines, availableAirlines.length, minPrice, maxPrice, maxStops]);

  const filteredRoundTrips = useMemo(() => {
    let result = filterRoundTripsByFareClass(roundTripOptions || [], activeTab);
    if (selectedAirlines.size > 0 && selectedAirlines.size < availableAirlines.length) {
      result = result.filter(rt => selectedAirlines.has(rt.outbound.airline) && selectedAirlines.has(rt.returnFlight.airline));
    }
    const min = minPrice ? parseInt(minPrice) * 100 : 0;
    const max = maxPrice ? parseInt(maxPrice) * 100 : Infinity;
    if (min > 0 || max < Infinity) {
      result = result.filter(rt => rt.totalCombinedPriceCents >= min && rt.totalCombinedPriceCents <= max);
    }
    if (maxStops >= 0) {
      result = result.filter(rt => rt.outbound.stops <= maxStops && rt.returnFlight.stops <= maxStops);
    }
    return result;
  }, [roundTripOptions, activeTab, selectedAirlines, availableAirlines.length, minPrice, maxPrice, maxStops]);

  function toggleAirline(code: string) {
    setSelectedAirlines(prev => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  function selectAllAirlines() {
    setSelectedAirlines(new Set(availableAirlines));
  }

  function clearAllAirlines() {
    setSelectedAirlines(new Set());
  }

  if (!options || options.length === 0) {
    return (
      <p style={styles.noData}>
        No flight data available. Run a scan to collect prices.
      </p>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <FareClassTabs activeTab={activeTab} onTabChange={setActiveTab} counts={counts} fareClasses={fareClasses} />

      {/* Filters */}
      <div style={styles.filterBar}>
        <div style={styles.filterSection}>
          <span style={styles.filterLabel}>AIRLINES</span>
          <span style={styles.filterLink} onClick={selectAllAirlines}>All</span>
          <span style={styles.filterLink} onClick={clearAllAirlines}>None</span>
          {availableAirlines.map(code => (
            <label key={code} style={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={selectedAirlines.has(code)}
                onChange={() => toggleAirline(code)}
                style={styles.checkbox}
              />
              {airlineName(code)}
            </label>
          ))}
        </div>
        <div style={styles.filterSection}>
          <span style={styles.filterLabel}>PRICE</span>
          <input
            className="cp-input"
            style={styles.priceInput}
            type="number"
            placeholder="Min $"
            value={minPrice}
            onChange={e => setMinPrice(e.target.value)}
          />
          <span style={{ color: '#555577', margin: '0 0.3rem' }}>–</span>
          <input
            className="cp-input"
            style={styles.priceInput}
            type="number"
            placeholder="Max $"
            value={maxPrice}
            onChange={e => setMaxPrice(e.target.value)}
          />
        </div>
        <div style={styles.filterSection}>
          <span style={styles.filterLabel}>STOPS</span>
          {[
            { label: 'Any', value: -1 },
            { label: 'Nonstop', value: 0 },
            { label: '≤1', value: 1 },
            { label: '≤2', value: 2 },
          ].map(opt => (
            <label key={opt.value} style={styles.checkboxLabel}>
              <input
                type="radio"
                name="stops"
                checked={maxStops === opt.value}
                onChange={() => setMaxStops(opt.value)}
                style={styles.checkbox}
              />
              {opt.label}
            </label>
          ))}
        </div>
      </div>
      {filteredOptions.length === 0 ? (
        <p style={styles.noData}>No {activeTab} flights available.</p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>DATE</th>
              <th style={styles.th}>AIRLINE</th>
              <th style={styles.th}>FLIGHT</th>
              <th style={styles.th}>DEP</th>
              <th style={styles.th}>ARR</th>
              <th style={styles.th}>STOPS</th>
              <th style={styles.th}>DURATION</th>
              <th style={{ ...styles.th, textAlign: 'right' }}>PRICE</th>
              <th style={styles.th}></th>
              <th style={styles.th}></th>
            </tr>
          </thead>
          <tbody>
            {[...filteredOptions].sort((a, b) => a.totalPriceCents - b.totalPriceCents).map((option, index) => (
              <FlightRow key={index} option={option} origin={origin} destination={destination} />
            ))}
          </tbody>
        </table>
      )}

      {roundTripOptions && roundTripOptions.length > 0 && (
        <div style={styles.roundTripSection}>
          <h3 style={styles.roundTripTitle}>ROUND-TRIP COMBINATIONS</h3>
          {filteredRoundTrips.length === 0 ? (
            <p style={styles.noData}>No {activeTab} round-trip combinations available.</p>
          ) : (
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>OUT DATE</th>
                  <th style={styles.th}>OUTBOUND</th>
                  <th style={styles.th}>RET DATE</th>
                  <th style={styles.th}>RETURN</th>
                  <th style={{ ...styles.th, textAlign: 'right' }}>TOTAL</th>
                  <th style={styles.th}></th>
                </tr>
              </thead>
              <tbody>
                {filteredRoundTrips.map((rt, index) => {
                  return (
                    <tr key={index} style={styles.tr}>
                      <td style={styles.td}>
                        <span style={styles.dateBadge}>{formatFlightDate(rt.outbound.flightDate)}</span>
                      </td>
                      <td style={styles.td}>
                        <span style={styles.rtFlight}>
                          {airlineName(rt.outbound.airline)} {rt.outbound.flightNumber}
                        </span>
                      </td>
                      <td style={styles.td}>
                        <span style={styles.dateBadge}>{formatFlightDate(rt.returnFlight.flightDate)}</span>
                      </td>
                      <td style={styles.td}>
                        <span style={styles.rtFlight}>
                          {airlineName(rt.returnFlight.airline)} {rt.returnFlight.flightNumber}
                        </span>
                      </td>
                      <td style={{ ...styles.td, textAlign: 'right' }}>
                        <span style={{ color: '#8888aa', fontSize: '0.8rem' }}>{formatPrice(rt.combinedPriceCents)}</span>
                        {rt.totalCombinedPriceCents !== rt.combinedPriceCents && (
                          <span style={{ color: '#00F0FF', fontWeight: 700, marginLeft: '0.5rem' }}>{formatPrice(rt.totalCombinedPriceCents)}</span>
                        )}
                        {rt.totalCombinedPriceCents === rt.combinedPriceCents && (
                          <span style={{ color: '#00F0FF', fontWeight: 700, marginLeft: '0.5rem' }}>{formatPrice(rt.combinedPriceCents)}</span>
                        )}
                      </td>
                      <td style={styles.td}>
                        <a
                          href={googleFlightsUrl(origin, destination, rt.outbound.flightDate)}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={styles.bookLink}
                          onClick={(e) => e.stopPropagation()}
                          title="Open this route on Google Flights"
                        >
                          BOOK ↗
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
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
  dateBadge: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.7rem',
    color: '#00F0FF',
    background: '#00F0FF15',
    border: '1px solid #00F0FF44',
    padding: '0.15rem 0.4rem',
    borderRadius: '2px',
    letterSpacing: '0.5px',
    whiteSpace: 'nowrap',
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
  roundTripSection: {
    marginTop: '2rem',
    paddingTop: '1.5rem',
    borderTop: '1px solid #2a2a4a',
  },
  roundTripTitle: {
    fontFamily: "'Orbitron', sans-serif",
    fontSize: '0.8rem',
    fontWeight: 600,
    color: '#FCEE09',
    letterSpacing: '2px',
    marginBottom: '0.75rem',
    margin: '0 0 0.75rem 0',
  },
  rtFlight: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.8rem',
    color: '#e0e0e0',
  },
  tabBar: {
    display: 'flex',
    overflowX: 'auto',
    whiteSpace: 'nowrap',
    borderBottom: '1px solid #2a2a4a',
    marginBottom: '1rem',
    gap: '0',
  },
  tabActive: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.4rem',
    padding: '0.6rem 1rem',
    background: '#00F0FF15',
    border: 'none',
    borderBottom: '2px solid #00F0FF',
    color: '#00F0FF',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  tabInactive: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.4rem',
    padding: '0.6rem 1rem',
    background: 'transparent',
    border: 'none',
    borderBottom: '2px solid transparent',
    color: '#555577',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  tabLabel: {
    fontFamily: "'Orbitron', sans-serif",
    fontSize: '0.7rem',
    letterSpacing: '0.5px',
  },
  tabBadge: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.65rem',
  },
  filterBar: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: '1.5rem',
    alignItems: 'center',
    padding: '0.6rem 0',
    marginBottom: '0.75rem',
    borderBottom: '1px solid #1a1a2e',
  },
  filterSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    flexWrap: 'wrap' as const,
  },
  filterLabel: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.65rem',
    color: '#00F0FF',
    letterSpacing: '1px',
    marginRight: '0.25rem',
  },
  filterLink: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.6rem',
    color: '#FCEE09',
    cursor: 'pointer',
    textDecoration: 'underline',
  },
  checkboxLabel: {
    fontFamily: "'Rajdhani', sans-serif",
    fontSize: '0.8rem',
    color: '#e0e0e0',
    display: 'flex',
    alignItems: 'center',
    gap: '0.2rem',
    cursor: 'pointer',
  },
  checkbox: {
    accentColor: '#00F0FF',
  },
  priceInput: {
    width: '70px',
    padding: '0.3rem 0.4rem',
    fontSize: '0.75rem',
  },
  bookLink: {
    fontFamily: "'Orbitron', sans-serif",
    fontSize: '0.6rem',
    color: '#FCEE09',
    border: '1px solid #FCEE0944',
    padding: '0.2rem 0.5rem',
    textDecoration: 'none',
    letterSpacing: '1px',
    whiteSpace: 'nowrap',
  },
};
