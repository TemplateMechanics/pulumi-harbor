from dataclass_wizard import YAMLWizard, asdict
from typing import Dict, Any, Sequence ,Optional, List
from dataclasses import dataclass, field
@dataclass
class RegistryArgs:
    access_id: Optional[str] = None
    access_secret: Optional[str] = None
    description: Optional[str] = None
    endpoint_url: Optional[str] = None
    insecure: Optional[bool] = None
    name: Optional[str] = None
    provider_name: Optional[str] = None
@dataclass
class Registries:
    name: str
    id: Optional[str] = None
    args: Optional[RegistryArgs] = None
### https://www.pulumi.com/registry/packages/harbor/api-docs/registry/ ###
@dataclass
class ProjectArgs:
    deployment_security: Optional[str] = None
    enable_content_trust: Optional[bool] = None
    enable_content_trust_cosign: Optional[bool] = None
    force_destroy: Optional[bool] = None
    name: Optional[str] = None
    public: Optional[str] = None
    registry_id: Optional[int] = None
    storage_quota: Optional[int] = None
    vulnerability_scanning: Optional[bool] = None
@dataclass
class Projects:
    name: str
    id: Optional[str] = None
    args: Optional[ProjectArgs] = None
### https://www.pulumi.com/registry/packages/harbor/api-docs/project/ ###
@dataclass
class Harbor:
    projects: Optional[List[Projects]] = None
    registries: Optional[List[Registries]] = None
### https://www.pulumi.com/registry/packages/harbor/ ###
@dataclass
class Environment:
    name: str
    location: Optional[str] = None
    harbor: Optional[Harbor] = None
@dataclass
class Service:
    name: str
    environments: List[Environment]
@dataclass
class Team:
    name: str
    services: List[Service]
@dataclass
class Config(YAMLWizard):
    teams: List[Team]
### Base Config ###