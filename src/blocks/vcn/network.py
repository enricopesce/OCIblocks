import pulumi
import pulumi_oci as oci
from core.helper import Helper
from typing import Optional, Dict, List
from dataclasses import dataclass

@dataclass
class SubnetConfig:
    cidr: str
    is_public: bool
    dns_label: str

class Vcn(pulumi.ComponentResource):
    vcn: oci.core.Vcn
    internet_gateway: oci.core.InternetGateway
    nat_gateway: oci.core.NatGateway
    service_gateway: oci.core.ServiceGateway
    id: pulumi.Output[str]
    
    # Route tables
    private_a_route_table: oci.core.RouteTable
    private_b_route_table: oci.core.RouteTable
    public_a_route_table: oci.core.RouteTable
    public_b_route_table: oci.core.RouteTable
    
    # Security lists
    private_a_security_list: oci.core.SecurityList
    private_b_security_list: oci.core.SecurityList
    public_a_security_list: oci.core.SecurityList
    public_b_security_list: oci.core.SecurityList
    
    # Subnets
    private_a_subnet: oci.core.Subnet
    private_b_subnet: oci.core.Subnet
    public_a_subnet: oci.core.Subnet
    public_b_subnet: oci.core.Subnet

    def __init__(
        self,
        name: str,
        compartment_id: pulumi.Input[str],
        display_name: pulumi.Input[str],
        opts: Optional[pulumi.ResourceOptions] = None,
        cidr_block: Optional[pulumi.Input[str]] = None,
    ):
        super().__init__("custom:network:Vcn", name, {}, opts)
        
        self.compartment_id = compartment_id
        self.display_name = display_name
        self.cidr_block = cidr_block or "10.0.0.0/16"
        
        h = Helper()
        subnets = h.calculate_subnets(self.cidr_block, 6)
        
        self._create_vcn(name)
        self._create_gateways(name)
        self._create_security_lists(name)
        self._create_route_tables(name)
        self._create_subnets(name, subnets)
        
        self.register_outputs({})

    def _create_vcn(self, name: str) -> None:
        self.vcn = oci.core.Vcn(
            f"{name}-vcn",
            compartment_id=self.compartment_id,
            cidr_blocks=[self.cidr_block],
            display_name=f"vcn-{self.display_name}",
            dns_label="vcn",
            opts=pulumi.ResourceOptions(parent=self)
        )
        self.id = self.vcn.id

    def _create_gateways(self, name: str) -> None:
        self.internet_gateway = oci.core.InternetGateway(
            f"{name}-igw",
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            display_name=f"igw-{self.display_name}",
            enabled=True,
            opts=pulumi.ResourceOptions(parent=self)
        )

        self.nat_gateway = oci.core.NatGateway(
            f"{name}-natgw",
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            display_name=f"natgw-{self.display_name}",
            opts=pulumi.ResourceOptions(parent=self)
        )

        self.service_gateway = oci.core.ServiceGateway(
            f"{name}-svcgw",
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            services=[
                oci.core.ServiceGatewayServiceArgs(
                    service_id=oci.core.get_services().services[0].id
                )
            ],
            display_name=f"svcgw-{self.display_name}",
            opts=pulumi.ResourceOptions(parent=self)
        )

    def _create_security_lists(self, name: str) -> None:
        security_lists = {
            "pub-a": "public-a",
            "pub-b": "public-b",
            "prv-a": "private-a",
            "prv-b": "private-b"
        }
        
        for short_name, full_name in security_lists.items():
            setattr(
                self,
                f"{full_name.replace('-', '_')}_security_list",
                oci.core.SecurityList(
                    f"{name}-sl-{short_name}",
                    compartment_id=self.compartment_id,
                    vcn_id=self.vcn.id,
                    display_name=f"sl-{short_name}-{self.display_name}",
                    ingress_security_rules=[],
                    egress_security_rules=[],
                    opts=pulumi.ResourceOptions(parent=self)
                )
            )

    def _create_route_tables(self, name: str) -> None:
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
            ("prv-a", "private-a"): private_route_rules,
            ("prv-b", "private-b"): private_route_rules,
            ("pub-a", "public-a"): public_route_rules,
            ("pub-b", "public-b"): public_route_rules,
        }
        
        for (short_name, full_name), rules in route_tables.items():
            setattr(
                self,
                f"{full_name.replace('-', '_')}_route_table",
                oci.core.RouteTable(
                    f"{name}-rt-{short_name}",
                    compartment_id=self.compartment_id,
                    vcn_id=self.vcn.id,
                    display_name=f"rt-{short_name}-{self.display_name}",
                    route_rules=rules,
                    opts=pulumi.ResourceOptions(parent=self)
                )
            )

    def _create_subnet(
        self,
        name: str,
        config: SubnetConfig,
        security_list: oci.core.SecurityList,
        route_table: oci.core.RouteTable,
    ) -> oci.core.Subnet:
        return oci.core.Subnet(
            name,
            compartment_id=self.compartment_id,
            security_list_ids=[security_list.id],
            vcn_id=self.vcn.id,
            cidr_block=config.cidr,
            display_name=f"{name}-{self.display_name}",
            dns_label=config.dns_label,
            prohibit_public_ip_on_vnic=not config.is_public,
            route_table_id=route_table.id,
            opts=pulumi.ResourceOptions(parent=self)
        )

    def _create_subnets(self, name: str, subnet_cidrs: tuple) -> None:
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
            
            setattr(
                self,
                f"{attr_name}_subnet",
                self._create_subnet(
                    f"{name}-sn-{short_name}",
                    config,
                    security_list,
                    route_table
                )
            )