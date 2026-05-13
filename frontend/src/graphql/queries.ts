import { gql } from '@apollo/client';

export const GET_TRIPS = gql`
  query GetTrips {
    trips {
      id
      origin
      destination
      earliestDeparture
      latestDeparture
      earliestReturn
      latestReturn
      latestDepartureTime
      latestReturnTime
      isActive
      latestAnalysis {
        recommendation
        explanation
        analyzedAt
      }
    }
  }
`;

export const GET_TRIP_DETAIL = gql`
  query GetTripDetail($tripId: Int!) {
    trip(tripId: $tripId) {
      id
      origin
      destination
      earliestDeparture
      latestDeparture
      earliestReturn
      latestReturn
      latestDepartureTime
      latestReturnTime
      isActive
      priceHistory {
        airlineCode
        fareClass
        priceCents
        flightDate
        collectedAt
      }
      latestAnalysis {
        recommendation
        explanation
        analyzedAt
      }
      topFlightOptions {
        airline
        flightNumber
        departureTime
        arrivalTime
        fareClass
        priceCents
      }
    }
  }
`;

export const CREATE_TRIP = gql`
  mutation CreateTrip($input: TripRequestInput!) {
    createTrip(input: $input) {
      id
      origin
      destination
      earliestDeparture
      latestDeparture
    }
  }
`;

export const UPDATE_TRIP = gql`
  mutation UpdateTrip($tripId: Int!, $input: TripRequestInput!) {
    updateTrip(tripId: $tripId, input: $input) {
      id
      origin
      destination
      earliestDeparture
      latestDeparture
    }
  }
`;

export const DELETE_TRIP = gql`
  mutation DeleteTrip($tripId: Int!) {
    deleteTrip(tripId: $tripId)
  }
`;

export const TRIGGER_COLLECTION = gql`
  mutation TriggerCollection {
    triggerCollection
  }
`;
