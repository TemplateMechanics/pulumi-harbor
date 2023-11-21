import config
import dataclasses
from dataclasses import dataclass, field
from typing import Optional
from abc import ABC, abstractmethod
import re
from collections.abc import Iterable
import uuid
import secrets
import string
from automapper import mapper

import pulumi
import pulumiverse_harbor as harbor

pulumiConfig : pulumi.Config = pulumi.Config()

@dataclass
class BuildContext:
    team: str
    service: str
    environment: str
    location: str

    resource_cache: dict = field(init=False, repr=False, default_factory=dict)

    async def add_resource_to_cache(self, name: str, resource: pulumi.CustomResource):
        self.resource_cache[name] = resource

    async def get_resource_from_cache(self, name: str) -> pulumi.CustomResource:
        if name in self.resource_cache:
            return self.resource_cache[name]

        return None

    def get_default_resource_name(self, unique_identifier: str) -> str:
        return f"{self.team}-{self.service}-{self.environment}-{unique_identifier}"

    def get_default_resource_name_clean(self, unique_identifier: str) -> str:
        return self.get_default_resource_name(unique_identifier).replace("-", "")
    
    def generate_password(length=16):
        all_characters = string.ascii_letters + string.digits + string.punctuation
        password = ''.join(secrets.choice(all_characters) for _ in range(length))
        return password

# region Resources
class BaseResource(ABC):

    def __init__(self, name: str, context: BuildContext):
        self.name = name
        self.context = context

    @abstractmethod
    async def find(self, id: Optional[str] = None) -> pulumi.CustomResource:
        pass

    @abstractmethod
    async def create(self, args: any) -> pulumi.CustomResource:
        pass

    async def getResourceValue(self, baseResource : pulumi.CustomResource, outputChain : str) -> Optional[str]:
        outputs = outputChain.split("->")
                
        if baseResource is None:
            return None      
        
        # loop through nested output parameters until we get to the last resource
        for outputName in outputs[:-1]:
            baseResource = getattr(baseResource, outputName)
            if baseResource is None:
                return None
    
        return getattr(baseResource, outputs[-1] )

    async def replaceValue(self, args : any, propertyName : str, value : str | pulumi.Output[any]) -> str:
        newValue : str = value
        m = re.search(r"Resource (.+),\s?(.+)", value)
        if m is not None:
            resource = await self.context.get_resource_from_cache(m.group(1))
            newValue = await self.getResourceValue(resource, m.group(2)) or newValue            
        else:
            m = re.search(r"Secret (.+)", value)
            if m is not None:
                secret = pulumiConfig.require_secret(m.group(1))
                newValue = secret or value

        if value != newValue:
            setattr(args, propertyName, newValue)

    async def replaceInputArgs(self, args: any):
        properties = [a for a in dir(args) if not a.startswith('__') and not callable(getattr(args, a))]
        for property in properties:
            value = getattr(args, property)
            if value is not None:

                # loop iterables
                if (isinstance(value, Iterable)):
                    for item in value:
                        await self.replaceInputArgs(item)

                # deep replace on all child dataclasses
                if (dataclasses.is_dataclass(value)):
                    await self.replaceInputArgs(value)

                # only replace values for strings
                if isinstance(value, str):
                    await self.replaceValue(args, property, value)

    async def build(self, id: Optional[str] = None, args: Optional[any] = None) -> None:
        resource_group = None

        if id is not None:
            try:
                resource_group = await self.find(id)
            except Exception as e:
                pulumi.log.warn(f"Failed to find existing resource with id {id}: {e}")
                return

        if args is not None:
            await self.replaceInputArgs(args);
            resource_group = await self.create(args)

        if resource_group is not None:
            await self.context.add_resource_to_cache(self.name, resource_group)

class Projects(BaseResource):

    def __init__(self, name: str, context: BuildContext):
        super().__init__(name, context)
    
    async def find(self, id: Optional[str] = None) -> Optional[harbor.Project]:
        if not id:
            return None
        
        return harbor.Project.get(self.context.get_default_resource_name(self.name), id)
    
    async def create(self, args: harbor.ProjectArgs) -> harbor.Project:
        args.name = args.name or self.context.get_default_resource_name(self.name)
        project_args = mapper.to(harbor.ProjectArgs).map(args, use_deepcopy=False, skip_none_values=True)
        return harbor.Project(self.context.get_default_resource_name(self.name), project_args)
    
class Registries(BaseResource):
    
        def __init__(self, name: str, context: BuildContext):
            super().__init__(name, context)
        
        async def find(self, id: Optional[str] = None) -> Optional[harbor.Registry]:
            if not id:
                return None
            
            return harbor.Registry.get(self.context.get_default_resource_name(self.name), id)
        
        async def create(self, args: harbor.RegistryArgs) -> harbor.Registry:
            args.name = args.name or self.context.get_default_resource_name(self.name)
            registry_args = mapper.to(harbor.RegistryArgs).map(args, use_deepcopy=False, skip_none_values=True)
            return harbor.Registry(self.context.get_default_resource_name(self.name), registry_args)
#endregion

class ResourceBuilder:

    def __init__(self, context: BuildContext):
        self.context = context
        self.location = context.location
    
    async def build(self, config: config.Harbor):
        await self.build_projects(config.projects)
        await self.build_registries(config.registries)
    
    async def build_projects(self, configs: Optional[list[config.Projects]] = None):
        if configs is None:
            return

        for config in configs:
            builder = Projects(config.name, self.context)
            await builder.build(config.id, config.args)

    async def build_registries(self, configs: Optional[list[config.Registries]] = None):
        if configs is None:
            return

        for config in configs:
            builder = Registries(config.name, self.context)
            await builder.build(config.id, config.args)
