import pulumi
import pulumi_oci as oci
from core.helper import Helper
from typing import Optional
from dataclasses import dataclass

@dataclass
class SubnetConfig:
    cidr: str
    is_public: bool
    dns_label: str

class Vcn(pulumi.ComponentResource):
    def __init__(
        self,
        name: str,
        compartment_id: pulumi.Input[str],
        stack_name: str,
        opts: Optional[pulumi.ResourceOptions] = None,
        cidr_block: Optional[pulumi.Input[str]] = None,
    ):
        super().__init__("custom:network:Vcn", f"{stack_name}-{name}", {}, opts)
        
        self.compartment_id = compartment_id
        self.display_name = f"{stack_name}-{name}"
        self.cidr_block = cidr_block or "10.0.0.0/16"
        self.stack_name = stack_name
        self.name = name
        
        h = Helper()
        subnets = h.calculate_subnets(self.cidr_block, 6)
        
        self._create_vcn()
        self._create_gateways()
        self._create_security_lists()
        self._create_route_tables()
        self._create_subnets(subnets)
        
        self.register_outputs({})

    def _create_vcn(self) -> None:
        resource_name = f"{self.stack_name}-{self.name}-vcn"
        self.vcn = oci.core.Vcn(
            resource_name,
            compartment_id=self.compartment_id,
            cidr_blocks=[self.cidr_block],
            display_name=resource_name,
            dns_label=f"vcn{self.stack_name}",
            freeform_tags={
                "Name": resource_name,
                "ResourceType": "vcn",
                "NetworkTier": "core",
                "Environment": self.stack_name,
                "CreatedBy": f"{self.stack_name}-{self.name}"
            },
            opts=pulumi.ResourceOptions(parent=self)
        )
        self.id = self.vcn.id

    def _create_gateways(self) -> None:
        # Internet Gateway
        igw_name = f"{self.stack_name}-{self.name}-igw"
        self.internet_gateway = oci.core.InternetGateway(
            igw_name,
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            display_name=igw_name,
            enabled=True,
            freeform_tags={
                "Name": igw_name,
                "ResourceType": "gateway",
                "GatewayType": "internet",
                "Environment": self.stack_name,
                "CreatedBy": f"{self.stack_name}-{self.name}"
            },
            opts=pulumi.ResourceOptions(parent=self)
        )

        # NAT Gateway
        natgw_name = f"{self.stack_name}-{self.name}-natgw"
        self.nat_gateway = oci.core.NatGateway(
            natgw_name,
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            display_name=natgw_name,
            freeform_tags={
                "Name": natgw_name,
                "ResourceType": "gateway",
                "GatewayType": "nat",
                "Environment": self.stack_name,
                "CreatedBy": f"{self.stack_name}-{self.name}"
            },
            opts=pulumi.ResourceOptions(parent=self)
        )

        # Service Gateway
        svcgw_name = f"{self.stack_name}-{self.name}-svcgw"
        self.service_gateway = oci.core.ServiceGateway(
            svcgw_name,
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            services=[
                oci.core.ServiceGatewayServiceArgs(
                    service_id=oci.core.get_services().services[0].id
                )
            ],
            display_name=svcgw_name,
            freeform_tags={
                "Name": svcgw_name,
                "ResourceType": "gateway",
                "GatewayType": "service",
                "Environment": self.stack_name,
                "CreatedBy": f"{self.stack_name}-{self.name}"
            },
            opts=pulumi.ResourceOptions(parent=self)
        )

    def _create_security_lists(self) -> None:
        security_lists = {
            "pub-a": ("public-a", "public"),
            "pub-b": ("public-b", "public"),
            "prv-a": ("private-a", "private"),
            "prv-b": ("private-b", "private")
        }
        
        for short_name, (full_name, network_type) in security_lists.items():
            resource_name = f"{self.stack_name}-{self.name}-sl-{short_name}"
            setattr(
                self,
                f"{full_name.replace('-', '_')}_security_list",
                oci.core.SecurityList(
                    resource_name,
                    compartment_id=self.compartment_id,
                    vcn_id=self.vcn.id,
                    display_name=resource_name,
                    ingress_security_rules=[],
                    egress_security_rules=[],
                    freeform_tags={
                        "Name": resource_name,
                        "ResourceType": "security-list",
                        "NetworkType": network_type,
                        "SubnetGroup": full_name,
                        "Environment": self.stack_name,
                        "CreatedBy": f"{self.stack_name}-{self.name}"
                    },
                    opts=pulumi.ResourceOptions(parent=self)
                )
            )

    def _create_route_tables(self) -> None:
        private_route_rules = [
            oci.core.RouteTableRouteRuleArgs(
                destination="0.0.0.0/0",
                network_entity_id=self.nat_gateway.id,
            ),
            oci.core.RouteTableRouteRuleArgs(
                destination=oci.core.get_services().services[0].cidr_block,
                destination_type="SERVICE_CIDR_BLOCK",
                network_entity_id=self.service_gateway.id,
            ),
        ]
        
        public_route_rules = [
            oci.core.RouteTableRouteRuleArgs(
                destination="0.0.0.0/0",
                network_entity_id=self.internet_gateway.id,
            ),
        ]
        
        route_tables = {
            ("prv-a", "private-a"): (private_route_rules, "private"),
            ("prv-b", "private-b"): (private_route_rules, "private"),
            ("pub-a", "public-a"): (public_route_rules, "public"),
            ("pub-b", "public-b"): (public_route_rules, "public"),
        }
        
        for (short_name, full_name), (rules, network_type) in route_tables.items():
            resource_name = f"{self.stack_name}-{self.name}-rt-{short_name}"
            setattr(
                self,
                f"{full_name.replace('-', '_')}_route_table",
                oci.core.RouteTable(
                    resource_name,
                    compartment_id=self.compartment_id,
                    vcn_id=self.vcn.id,
                    display_name=resource_name,
                    route_rules=rules,
                    freeform_tags={
                        "Name": resource_name,
                        "ResourceType": "route-table",
                        "NetworkType": network_type,
                        "SubnetGroup": full_name,
                        "Environment": self.stack_name,
                        "CreatedBy": f"{self.stack_name}-{self.name}"
                    },
                    opts=pulumi.ResourceOptions(parent=self)
                )
            )

    def _create_subnet(
        self,
        subnet_name: str,
        config: SubnetConfig,
        security_list: oci.core.SecurityList,
        route_table: oci.core.RouteTable,
    ) -> oci.core.Subnet:
        network_type = "public" if config.is_public else "private"
        subnet_group = f"{network_type}-{'a' if 'a' in config.dns_label else 'b'}"
        
        return oci.core.Subnet(
            subnet_name,
            compartment_id=self.compartment_id,
            security_list_ids=[security_list.id],
            vcn_id=self.vcn.id,
            cidr_block=config.cidr,
            display_name=subnet_name,
            dns_label=f"{config.dns_label}{self.stack_name}",
            prohibit_public_ip_on_vnic=not config.is_public,
            route_table_id=route_table.id,
            freeform_tags={
                "Name": subnet_name,
                "ResourceType": "subnet",
                "NetworkType": network_type,
                "SubnetGroup": subnet_group,
                "CidrRange": config.cidr,
                "Environment": self.stack_name,
                "CreatedBy": f"{self.stack_name}-{self.name}"
            },
            opts=pulumi.ResourceOptions(parent=self)
        )

    def _create_subnets(self, subnet_cidrs: tuple) -> None:
        lb_subnet, pub_subnet, pods_subnet, workers_subnet, _, _ = subnet_cidrs
        
        subnet_configs = {
            ("pub-a", "public_a"): SubnetConfig(pub_subnet, True, "puba"),
            ("pub-b", "public_b"): SubnetConfig(lb_subnet, True, "pubb"),
            ("prv-a", "private_a"): SubnetConfig(workers_subnet, False, "prva"),
            ("prv-b", "private_b"): SubnetConfig(pods_subnet, False, "prvb"),
        }
        
        for (short_name, attr_name), config in subnet_configs.items():
            security_list = getattr(self, f"{attr_name}_security_list")
            route_table = getattr(self, f"{attr_name}_route_table")
            
            subnet_name = f"{self.stack_name}-{self.name}-sn-{short_name}"
            setattr(
                self,
                f"{attr_name}_subnet",
                self._create_subnet(
                    subnet_name,
                    config,
                    security_list,
                    route_table
                )
            )

def get_resources_by_tag(vcn_instance, tag_key: str, tag_value: str):
    resources = []
    for attr_name in dir(vcn_instance):
        if hasattr(getattr(vcn_instance, attr_name), 'freeform_tags'):
            resource = getattr(vcn_instance, attr_name)
            if resource.freeform_tags.get(tag_key) == tag_value:
                resources.append(resource)
    return resources