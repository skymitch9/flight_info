"""RouteTracker service for route-level deduplication and lifecycle management."""

from datetime import datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Route, TripRequest

logger = structlog.get_logger(__name__)

DORMANCY_THRESHOLD_DAYS = 90


class RouteTracker:
    """Manages route lifecycle: creation, deduplication, dormancy, and reactivation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_route(self, origin: str, destination: str) -> Route:
        """Find an existing route or create a new one for the given origin-destination pair.

        Handles the unique constraint race condition by catching IntegrityError
        and retrying with a SELECT query.

        Args:
            origin: 3-letter IATA airport code for the origin.
            destination: 3-letter IATA airport code for the destination.

        Returns:
            The existing or newly created Route record.
        """
        # Try to find existing route first
        route = await self._find_route(origin, destination)
        if route is not None:
            return route

        # No existing route — attempt to create one
        try:
            route = Route(
                origin=origin,
                destination=destination,
                status="active",
            )
            self.session.add(route)
            await self.session.flush()
            logger.info(
                "route_created",
                origin=origin,
                destination=destination,
                route_id=route.id,
            )
            return route
        except IntegrityError:
            # Race condition: another transaction created the same route
            await self.session.rollback()
            logger.debug(
                "route_create_race_condition",
                origin=origin,
                destination=destination,
            )
            # Retry with SELECT — the route must exist now
            route = await self._find_route(origin, destination)
            if route is None:
                raise RuntimeError(
                    f"Failed to find route {origin}->{destination} after IntegrityError"
                )
            return route

    async def get_active_routes(self) -> list[Route]:
        """Return all routes with status 'active' (not dormant).

        These are the routes that should be included in collection cycles.

        Returns:
            List of active Route records.
        """
        result = await self.session.execute(
            select(Route).where(Route.status == "active")
        )
        return list(result.scalars().all())

    async def mark_dormant(self, route_id: int) -> Route:
        """Set a route's status to 'dormant', excluding it from collection.

        Args:
            route_id: The ID of the route to mark dormant.

        Returns:
            The updated Route record.
        """
        route = await self._get_route(route_id)
        route.status = "dormant"
        await self.session.flush()
        logger.info("route_marked_dormant", route_id=route_id)
        return route

    async def reactivate_route(self, route_id: int) -> Route:
        """Reactivate a dormant route, including it in collection again.

        Args:
            route_id: The ID of the route to reactivate.

        Returns:
            The updated Route record.
        """
        route = await self._get_route(route_id)
        route.status = "active"
        await self.session.flush()
        logger.info("route_reactivated", route_id=route_id)
        return route

    async def check_dormancy(self) -> list[Route]:
        """Find routes eligible for dormancy and mark them dormant.

        A route is eligible for dormancy when:
        1. It has no active contracts (TripRequests with status == "active")
        2. Its last_collected_at is more than 90 days ago

        Returns:
            List of routes that were marked dormant.
        """
        cutoff = datetime.utcnow() - timedelta(days=DORMANCY_THRESHOLD_DAYS)

        # Find active routes that have no active contracts
        # and last_collected_at is older than the threshold
        result = await self.session.execute(
            select(Route).where(
                Route.status == "active",
                Route.last_collected_at.isnot(None),
                Route.last_collected_at < cutoff,
                Route.id.notin_(
                    select(TripRequest.route_id)
                    .where(TripRequest.status == "active")
                    .where(TripRequest.route_id.isnot(None))
                    .distinct()
                ),
            )
        )
        routes_to_dormant = list(result.scalars().all())

        for route in routes_to_dormant:
            route.status = "dormant"
            logger.info(
                "route_auto_dormant",
                route_id=route.id,
                origin=route.origin,
                destination=route.destination,
                last_collected_at=str(route.last_collected_at),
            )

        if routes_to_dormant:
            await self.session.flush()

        logger.info("dormancy_check_complete", routes_marked=len(routes_to_dormant))
        return routes_to_dormant

    async def _find_route(self, origin: str, destination: str) -> Route | None:
        """Find a route by origin-destination pair."""
        result = await self.session.execute(
            select(Route).where(
                Route.origin == origin,
                Route.destination == destination,
            )
        )
        return result.scalar_one_or_none()

    async def _get_route(self, route_id: int) -> Route:
        """Fetch a route by ID. Raises ValueError if not found."""
        result = await self.session.execute(
            select(Route).where(Route.id == route_id)
        )
        route = result.scalar_one_or_none()
        if route is None:
            raise ValueError(f"Route with id {route_id} not found")
        return route
