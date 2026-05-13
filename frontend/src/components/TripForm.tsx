import { useState, useEffect, type FormEvent } from 'react';
import { useMutation } from '@apollo/client/react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import { CREATE_TRIP, UPDATE_TRIP, GET_TRIPS } from '../graphql/queries';

interface TripData {
  id: number;
  origin: string;
  destination: string;
  earliestDeparture: string;
  latestDeparture: string;
  earliestReturn?: string | null;
  latestReturn?: string | null;
  latestDepartureTime?: string | null;
  latestReturnTime?: string | null;
}

interface TripFormProps {
  onClose: () => void;
  existingTrip?: TripData | null;
}

interface FormErrors {
  origin?: string;
  destination?: string;
  earliestDeparture?: string;
  latestDeparture?: string;
  earliestReturn?: string;
  latestReturn?: string;
}

function parseDate(dateStr: string | null | undefined): Date | null {
  if (!dateStr) return null;
  const d = new Date(dateStr + 'T00:00:00');
  return isNaN(d.getTime()) ? null : d;
}

function formatDateForApi(date: Date | null): string | null {
  if (!date) return null;
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export default function TripForm({ onClose, existingTrip }: TripFormProps) {
  const isEditMode = !!existingTrip;

  const [origin, setOrigin] = useState(existingTrip?.origin ?? '');
  const [destination, setDestination] = useState(existingTrip?.destination ?? '');
  const [earliestDeparture, setEarliestDeparture] = useState<Date | null>(parseDate(existingTrip?.earliestDeparture));
  const [latestDeparture, setLatestDeparture] = useState<Date | null>(parseDate(existingTrip?.latestDeparture));
  const [earliestReturn, setEarliestReturn] = useState<Date | null>(parseDate(existingTrip?.earliestReturn));
  const [latestReturn, setLatestReturn] = useState<Date | null>(parseDate(existingTrip?.latestReturn));
  const [latestDepartureTime, setLatestDepartureTime] = useState(existingTrip?.latestDepartureTime ?? '');
  const [latestReturnTime, setLatestReturnTime] = useState(existingTrip?.latestReturnTime ?? '');
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [createTrip, { loading: creating }] = useMutation(CREATE_TRIP, {
    refetchQueries: [{ query: GET_TRIPS }],
    onCompleted: () => onClose(),
    onError: (err) => setSubmitError(err.message),
  });

  const [updateTrip, { loading: updating }] = useMutation(UPDATE_TRIP, {
    refetchQueries: [{ query: GET_TRIPS }],
    onCompleted: () => onClose(),
    onError: (err) => setSubmitError(err.message),
  });

  const loading = creating || updating;

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  // Smart logic: return date picker opens to the departure month
  const returnOpenToDate = earliestDeparture || latestDeparture || new Date();

  function validate(): FormErrors {
    const newErrors: FormErrors = {};
    const codeRegex = /^[A-Z]{3}$/;
    if (!codeRegex.test(origin)) newErrors.origin = 'INVALID IATA CODE';
    if (!codeRegex.test(destination)) newErrors.destination = 'INVALID IATA CODE';

    if (!earliestDeparture) newErrors.earliestDeparture = 'REQUIRED';
    else if (earliestDeparture < new Date()) newErrors.earliestDeparture = 'MUST BE FUTURE';

    if (!latestDeparture) newErrors.latestDeparture = 'REQUIRED';
    else if (earliestDeparture && latestDeparture < earliestDeparture) newErrors.latestDeparture = 'INVALID RANGE';

    if (earliestReturn && earliestDeparture && earliestReturn < earliestDeparture) newErrors.earliestReturn = 'BEFORE DEPARTURE';
    if (latestReturn && earliestReturn && latestReturn < earliestReturn) newErrors.latestReturn = 'INVALID RANGE';
    return newErrors;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    const validationErrors = validate();
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;

    const input = {
      origin,
      destination,
      earliestDeparture: formatDateForApi(earliestDeparture),
      latestDeparture: formatDateForApi(latestDeparture),
      earliestReturn: formatDateForApi(earliestReturn),
      latestReturn: formatDateForApi(latestReturn),
      latestDepartureTime: latestDepartureTime || null,
      latestReturnTime: latestReturnTime || null,
    };

    if (isEditMode && existingTrip) {
      updateTrip({ variables: { tripId: existingTrip.id, input } });
    } else {
      createTrip({ variables: { input } });
    }
  }

  return (
    <div style={styles.backdrop} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h2 style={styles.title}>{isEditMode ? 'EDIT CONTRACT' : 'NEW CONTRACT'}</h2>
        <div style={styles.titleDivider} />

        {submitError && <div style={styles.submitError}>⚠ {submitError}</div>}

        <form onSubmit={handleSubmit} noValidate>
          {/* Origin / Destination */}
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>ORIGIN</label>
              <input
                className="cp-input"
                style={styles.input}
                type="text"
                maxLength={3}
                placeholder="ATL"
                value={origin}
                onChange={(e) => setOrigin(e.target.value.toUpperCase())}
              />
              {errors.origin && <span style={styles.error}>{errors.origin}</span>}
            </div>
            <div style={styles.field}>
              <label style={styles.label}>DESTINATION</label>
              <input
                className="cp-input"
                style={styles.input}
                type="text"
                maxLength={3}
                placeholder="LAX"
                value={destination}
                onChange={(e) => setDestination(e.target.value.toUpperCase())}
              />
              {errors.destination && <span style={styles.error}>{errors.destination}</span>}
            </div>
          </div>

          {/* Departure Dates */}
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>EARLIEST DEPARTURE</label>
              <DatePicker
                selected={earliestDeparture}
                onChange={(date: Date | null) => setEarliestDeparture(date)}
                minDate={new Date()}
                dateFormat="MMM d, yyyy"
                placeholderText="Select date..."
                className="cp-input"
                calendarClassName="cp-calendar"
                wrapperClassName="cp-datepicker-wrapper"
                portalId="root"
              />
              {errors.earliestDeparture && <span style={styles.error}>{errors.earliestDeparture}</span>}
            </div>
            <div style={styles.field}>
              <label style={styles.label}>LATEST DEPARTURE</label>
              <DatePicker
                selected={latestDeparture}
                onChange={(date: Date | null) => setLatestDeparture(date)}
                minDate={earliestDeparture || new Date()}
                openToDate={earliestDeparture || undefined}
                dateFormat="MMM d, yyyy"
                placeholderText="Select date..."
                className="cp-input"
                calendarClassName="cp-calendar"
                wrapperClassName="cp-datepicker-wrapper"
                portalId="root"
              />
              {errors.latestDeparture && <span style={styles.error}>{errors.latestDeparture}</span>}
            </div>
          </div>

          {/* Return Dates */}
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>EARLIEST RETURN <span style={styles.optional}>(OPT)</span></label>
              <DatePicker
                selected={earliestReturn}
                onChange={(date: Date | null) => setEarliestReturn(date)}
                minDate={earliestDeparture || new Date()}
                openToDate={returnOpenToDate}
                dateFormat="MMM d, yyyy"
                placeholderText="Select date..."
                className="cp-input"
                calendarClassName="cp-calendar"
                wrapperClassName="cp-datepicker-wrapper"
                portalId="root"
                isClearable
              />
              {errors.earliestReturn && <span style={styles.error}>{errors.earliestReturn}</span>}
            </div>
            <div style={styles.field}>
              <label style={styles.label}>LATEST RETURN <span style={styles.optional}>(OPT)</span></label>
              <DatePicker
                selected={latestReturn}
                onChange={(date: Date | null) => setLatestReturn(date)}
                minDate={earliestReturn || earliestDeparture || new Date()}
                openToDate={earliestReturn || returnOpenToDate}
                dateFormat="MMM d, yyyy"
                placeholderText="Select date..."
                className="cp-input"
                calendarClassName="cp-calendar"
                wrapperClassName="cp-datepicker-wrapper"
                portalId="root"
                isClearable
              />
              {errors.latestReturn && <span style={styles.error}>{errors.latestReturn}</span>}
            </div>
          </div>

          {/* Time Constraints */}
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>ARRIVE BY (OUTBOUND) <span style={styles.optional}>(OPT)</span></label>
              <input
                className="cp-input"
                style={styles.input}
                type="time"
                value={latestDepartureTime}
                onChange={(e) => setLatestDepartureTime(e.target.value)}
              />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>ARRIVE BY (RETURN) <span style={styles.optional}>(OPT)</span></label>
              <input
                className="cp-input"
                style={styles.input}
                type="time"
                value={latestReturnTime}
                onChange={(e) => setLatestReturnTime(e.target.value)}
              />
            </div>
          </div>

          <div style={styles.formActions}>
            <button type="button" className="cp-button cp-button--magenta" onClick={onClose} disabled={loading}>
              CANCEL
            </button>
            <button type="submit" className="cp-button" disabled={loading}>
              {loading ? '◌ PROCESSING...' : isEditMode ? 'UPDATE' : 'DEPLOY'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  backdrop: {
    position: 'fixed',
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.85)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    backdropFilter: 'blur(4px)',
  },
  modal: {
    background: '#12121a',
    border: '1px solid #2a2a4a',
    borderTop: '3px solid #FCEE09',
    padding: '2rem',
    width: '100%',
    maxWidth: '540px',
    overflow: 'visible',
  },
  title: {
    fontFamily: "'Orbitron', sans-serif",
    fontSize: '1.1rem',
    fontWeight: 700,
    color: '#FCEE09',
    letterSpacing: '2px',
    margin: 0,
  },
  titleDivider: {
    height: '1px',
    background: 'linear-gradient(90deg, #FCEE09, transparent)',
    margin: '0.75rem 0 1.5rem',
    opacity: 0.5,
  },
  row: {
    display: 'flex',
    gap: '1rem',
    marginBottom: '1rem',
  },
  field: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
  },
  label: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.7rem',
    color: '#00F0FF',
    marginBottom: '0.3rem',
    letterSpacing: '1px',
  },
  optional: {
    color: '#555577',
  },
  input: {
    width: '100%',
  },
  error: {
    fontFamily: "'Share Tech Mono', monospace",
    fontSize: '0.65rem',
    color: '#FF003C',
    marginTop: '0.25rem',
  },
  submitError: {
    fontFamily: "'Share Tech Mono', monospace",
    background: '#FF003C15',
    border: '1px solid #FF003C44',
    padding: '0.6rem 0.8rem',
    color: '#FF003C',
    fontSize: '0.8rem',
    marginBottom: '1rem',
  },
  formActions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '0.75rem',
    marginTop: '1.5rem',
    paddingTop: '1rem',
    borderTop: '1px solid #2a2a4a',
  },
};
