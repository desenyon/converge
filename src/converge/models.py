from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    REPOSITORY = "repository"
    PACKAGE = "package"
    ENVIRONMENT = "environment"
    PYTHON_VERSION = "python_version"
    MODULE = "module"
    ROUTE = "route"
    EXTERNAL_API = "external_api"


class RelationshipType(StrEnum):
    IMPORTS = "imports"
    REQUIRES = "requires"
    CONFLICTS_WITH = "conflicts_with"
    CALLS = "calls"
    EXPOSES = "exposes"
    CONFIGURED_BY = "configured_by"
    DEPENDS_ON = "depends_on"
    VALIDATED_BY = "validated_by"
    BROKEN_BY = "broken_by"
    FIXED_BY = "fixed_by"
    SERVED_AT = "served_at"
    REFERENCES_ENV = "references_env"
    USES_INTERPRETER = "uses_interpreter"
    BELONGS_TO = "belongs_to"


class GraphEntity(BaseModel):
    id: str
    type: EntityType
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphRelationship(BaseModel):
    source_id: str
    target_id: str
    type: RelationshipType
    metadata: dict[str, Any] = Field(default_factory=dict)


# Specialized Entity Models
class Repository(GraphEntity):
    type: EntityType = EntityType.REPOSITORY
    path: str


class Package(GraphEntity):
    type: EntityType = EntityType.PACKAGE
    version: str | None = None
    source: str = "pypi"


class Environment(GraphEntity):
    type: EntityType = EntityType.ENVIRONMENT
    path: str


class PythonVersion(GraphEntity):
    type: EntityType = EntityType.PYTHON_VERSION
    version: str


class Module(GraphEntity):
    type: EntityType = EntityType.MODULE
    file_path: str


class Route(GraphEntity):
    type: EntityType = EntityType.ROUTE
    method: str
    path: str


class ExternalAPI(GraphEntity):
    type: EntityType = EntityType.EXTERNAL_API
    url: str
