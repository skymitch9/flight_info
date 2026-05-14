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
      passengerCount
      carryOnBags
      checkedBags
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
      passengerCount
      carryOnBags
      checkedBags
      status
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
        totalPriceCents
        flightDate
        stops
        totalDurationMinutes
        segments {
          airline
          flightNumber
          origin
          destination
          departureTime
          arrivalTime
          durationMinutes
        }
      }
      roundTripOptions {
        outbound {
          airline
          flightNumber
          departureTime
          arrivalTime
          fareClass
          priceCents
          totalPriceCents
          flightDate
          stops
          totalDurationMinutes
          segments {
            airline
            flightNumber
            origin
            destination
            departureTime
            arrivalTime
            durationMinutes
          }
        }
        returnFlight {
          airline
          flightNumber
          departureTime
          arrivalTime
          fareClass
          priceCents
          totalPriceCents
          flightDate
          stops
          totalDurationMinutes
          segments {
            airline
            flightNumber
            origin
            destination
            departureTime
            arrivalTime
            durationMinutes
          }
        }
        combinedPriceCents
        totalCombinedPriceCents
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

export const GET_FULFILLED_TRIPS = gql`
  query GetFulfilledTrips {
    fulfilledTrips {
      id
      origin
      destination
      earliestDeparture
      latestDeparture
      earliestReturn
      latestReturn
      status
      fulfilledAt
      latestAnalysis {
        recommendation
        explanation
        analyzedAt
      }
    }
  }
`;

export const GET_ROUTE = gql`
  query GetRoute($routeId: Int!) {
    route(routeId: $routeId) {
      id
      origin
      destination
      status
      lastCollectedAt
      priceHistory {
        airlineCode
        fareClass
        priceCents
        flightDate
        collectedAt
      }
      activeContracts {
        id
        origin
        destination
        earliestDeparture
        latestDeparture
        status
      }
    }
  }
`;

export const GET_ROUTES = gql`
  query GetRoutes {
    routes {
      id
      origin
      destination
      status
      lastCollectedAt
    }
  }
`;

export const FULFILL_TRIP = gql`
  mutation FulfillTrip($tripId: Int!) {
    fulfillTrip(tripId: $tripId) {
      id
      status
      fulfilledAt
    }
  }
`;
