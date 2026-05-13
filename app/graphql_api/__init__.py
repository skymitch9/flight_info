"""GraphQL API package for the Flight Deal Tracker."""

from app.graphql_api.schema import graphql_router, schema

__all__ = ["graphql_router", "schema"]
