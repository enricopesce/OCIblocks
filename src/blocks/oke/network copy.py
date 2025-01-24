import pulumi
import pulumi_oci as oci
from core.helper import Helper
from typing import Optional


class Vcn(pulumi.ComponentResource):
    def __init__(
        self,
        resource_name: str,
        compartment_id: pulumi.Input[str],
        display_name: pulumi.Input[str],
        # optional parameters
        opts: Optional[pulumi.ResourceOptions] = None,
        cidr_block: Optional[pulumi.Input[str]] = None,
    ):
        """
        This resource provides a complete VCN infrastructure with all depending resources to runs an OKE cluster

        :param str resource_name: The name of the resource
        :param pulumi.ResourceOptions opts: Options for the resource.
        :param pulumi.Input[str] compartment_id: (Updatable) The [OCID](https://docs.cloud.oracle.com/iaas/Content/General/Concepts/identifiers.htm) of the compartment
        :param pulumi.Input[str] cidr_block: Default: `10.0.0.0/16`
        :param pulumi.Input[Mapping[str, Any]] defined_tags: (Updatable) Defined tags for this resource. Each key is predefined and scoped to a namespace. For more information, see [Resource Tags](https://docs.cloud.oracle.com/iaas/Content/General/Concepts/resourcetags.htm).  Example: `{"Operations.CostCenter": "42"}`
        :param pulumi.Input[str] display_name: (Updatable) A user-friendly name. Does not have to be unique, and it's changeable. Avoid entering confidential information.
        """
        super().__init__("oci:core:Vcn", resource_name, {}, opts)

        h = Helper()

        if cidr_block is None:
            self.cidr_block = "10.0.0.0/16"
        else:
            self.cidr_block = cidr_block

        self.display_name = display_name

        self.resource_name = resource_name
        self.compartment_id = compartment_id

        (
            self.loadbalancers_subnet_address,
            self.public_subnet_address,
            self.pods_subnet_address,
            self.workers_subnet_address,
            self.oke_pods_cidr,
            self.oke_services_cidr,
        ) = h.calculate_subnets(self.cidr_block, 6)

        # Create a VCN
        self.vcn = oci.core.Vcn(
            "vcn",
            compartment_id=self.compartment_id,
            cidr_blocks=[self.cidr_block],
            display_name=f"vcn-{self.display_name}",
            dns_label="vcn",
        )

        self.id = self.vcn.id

        # Create an Internet Gateway for the public subnet
        self.internet_gateway = oci.core.InternetGateway(
            "InternetGateway",
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            display_name=f"InternetGateway-{self.display_name}",
            enabled=True,
        )

        # Create a NAT Gateway for the private subnet
        self.nat_gateway = oci.core.NatGateway(
            "NatGateway",
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            display_name=f"NatGateway-{self.display_name}",
        )

        # Create a Service Gateway for access to OCI services
        self.service_gateway = oci.core.ServiceGateway(
            "ServiceGateway",
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            services=[
                oci.core.ServiceGatewayServiceArgs(
                    service_id=oci.core.get_services().services[0].id
                )
            ],
            display_name=f"ServiceGateway-{self.display_name}",
        )

        # Create a separate Security List for the Public Subnet
        self.public_security_list = oci.core.SecurityList(
            "PublicSecurityList",
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            display_name=f"PublicSecurityList-{self.display_name}",
            ingress_security_rules=[
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Kubernetes worker to Kubernetes API endpoint communication.",
                    protocol="6",
                    source=self.workers_subnet_address,
                    source_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListIngressSecurityRuleTcpOptionsArgs(
                        max=6443,
                        min=6443,
                    ),
                ),
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Kubernetes worker to Kubernetes API endpoint communication.",
                    protocol="6",
                    source=self.workers_subnet_address,
                    source_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListIngressSecurityRuleTcpOptionsArgs(
                        max=12250,
                        min=12250,
                    ),
                ),
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Path discovery",
                    icmp_options=oci.core.SecurityListIngressSecurityRuleIcmpOptionsArgs(
                        code=4,
                        type=3,
                    ),
                    protocol="1",
                    source=self.workers_subnet_address,
                    source_type="CIDR_BLOCK",
                ),
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Pod to Kubernetes API endpoint communication (when using VCN-native pod networking).",
                    protocol="6",
                    source=self.pods_subnet_address,
                    source_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListIngressSecurityRuleTcpOptionsArgs(
                        max=6443,
                        min=6443,
                    ),
                ),
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Pod to Kubernetes API endpoint communication (when using VCN-native pod networking).",
                    protocol="6",
                    source=self.pods_subnet_address,
                    source_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListIngressSecurityRuleTcpOptionsArgs(
                        max=12250,
                        min=12250,
                    ),
                ),
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="External access to Kubernetes API endpoint.",
                    protocol="6",
                    source="0.0.0.0/0",
                    source_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListIngressSecurityRuleTcpOptionsArgs(
                        max=6443,
                        min=6443,
                    ),
                ),
            ],
            egress_security_rules=[
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Allow Kubernetes API endpoint to communicate with OKE.",
                    protocol="6",
                    destination=oci.core.get_services().services[0].cidr_block,
                    destination_type="SERVICE_CIDR_BLOCK",
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Path discovery",
                    icmp_options=oci.core.SecurityListEgressSecurityRuleIcmpOptionsArgs(
                        code=4,
                        type=3,
                    ),
                    protocol="1",
                    destination=oci.core.get_services().services[0].cidr_block,
                    destination_type="SERVICE_CIDR_BLOCK",
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Allow Kubernetes API endpoint to communicate with worker nodes.",
                    protocol="6",
                    destination=self.workers_subnet_address,
                    destination_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListEgressSecurityRuleTcpOptionsArgs(
                        max=10250,
                        min=10250,
                    ),
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Path discovery",
                    icmp_options=oci.core.SecurityListEgressSecurityRuleIcmpOptionsArgs(
                        code=4,
                        type=3,
                    ),
                    protocol="1",
                    destination=self.workers_subnet_address,
                    destination_type="CIDR_BLOCK",
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Allow Kubernetes API endpoint to communicate with pods (when using VCN-native pod networking).",
                    protocol="all",
                    destination=self.pods_subnet_address,
                    destination_type="CIDR_BLOCK",
                ),
            ],
        )

        # Create a separate Security List for the Workers Subnet
        self.workers_security_list = oci.core.SecurityList(
            "WorkersSecurityList",
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            display_name=f"WorkersSecurityList-{self.display_name}",
            ingress_security_rules=[
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Allow Kubernetes API endpoint to communicate with worker nodes.",
                    protocol="6",
                    source=self.public_subnet_address,
                    source_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListIngressSecurityRuleTcpOptionsArgs(
                        min=10250,
                        max=10250,
                    ),
                ),
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Path discovery",
                    icmp_options=oci.core.SecurityListIngressSecurityRuleIcmpOptionsArgs(
                        code=4,
                        type=3,
                    ),
                    protocol="1",
                    source="0.0.0.0/0",
                    source_type="CIDR_BLOCK",
                ),
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Load balancer to worker nodes node ports.",
                    protocol="6",
                    source=self.loadbalancers_subnet_address,
                    source_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListIngressSecurityRuleTcpOptionsArgs(
                        min=30000,
                        max=32767,
                    ),
                ),
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Allow load balancer to communicate with kube-proxy on worker nodes.",
                    protocol="6",
                    source=self.loadbalancers_subnet_address,
                    source_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListIngressSecurityRuleTcpOptionsArgs(
                        min=10256,
                        max=12250,
                    ),
                ),
            ],
            egress_security_rules=[
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Allow worker nodes to access pods.",
                    protocol="6",
                    destination=self.pods_subnet_address,
                    destination_type="CIDR_BLOCK",
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Path discovery",
                    icmp_options=oci.core.SecurityListEgressSecurityRuleIcmpOptionsArgs(
                        code=4,
                        type=3,
                    ),
                    protocol="1",
                    destination="0.0.0.0/0",
                    destination_type="CIDR_BLOCK",
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Allow worker nodes to communicate with OKE.",
                    protocol="6",
                    destination=oci.core.get_services().services[0].cidr_block,
                    destination_type="SERVICE_CIDR_BLOCK",
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Kubernetes worker to Kubernetes API endpoint communication.",
                    protocol="6",
                    destination=self.public_subnet_address,
                    destination_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListEgressSecurityRuleTcpOptionsArgs(
                        max=6443,
                        min=6443,
                    ),
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Kubernetes worker to Kubernetes API endpoint communication.",
                    protocol="6",
                    destination=self.public_subnet_address,
                    destination_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListEgressSecurityRuleTcpOptionsArgs(
                        max=12250,
                        min=12250,
                    ),
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Access to external (ex Dokcer) container registry",
                    protocol="6",
                    destination="0.0.0.0/0",
                    destination_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListEgressSecurityRuleTcpOptionsArgs(
                        max=443,
                        min=443,
                    ),
                ),
            ],
        )

        # Create a separate Security List for the Pods Subnet
        self.pods_security_list = oci.core.SecurityList(
            "PodSecurityList",
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            display_name=f"PodSecurityList-{self.display_name}",
            ingress_security_rules=[
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Allow worker nodes to access pods.",
                    protocol="all",
                    source=self.workers_subnet_address,
                    source_type="CIDR_BLOCK",
                ),
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Allow Kubernetes API endpoint to communicate with pods.",
                    protocol="all",
                    source=self.public_subnet_address,
                    source_type="CIDR_BLOCK",
                ),
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Allow pods to communicate with other pods.",
                    protocol="all",
                    source=self.pods_subnet_address,
                    source_type="CIDR_BLOCK",
                ),
            ],
            egress_security_rules=[
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Allow pods to communicate with other pods.",
                    protocol="all",
                    destination=self.pods_subnet_address,
                    destination_type="CIDR_BLOCK",
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Path discovery",
                    icmp_options=oci.core.SecurityListEgressSecurityRuleIcmpOptionsArgs(
                        code=4,
                        type=3,
                    ),
                    protocol="1",
                    destination=oci.core.get_services().services[0].cidr_block,
                    destination_type="SERVICE_CIDR_BLOCK",
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Allow pods to communicate with OCI services.",
                    protocol="6",
                    destination=oci.core.get_services().services[0].cidr_block,
                    destination_type="SERVICE_CIDR_BLOCK",
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="(optional) Allow pods to communicate with internet.",
                    protocol="6",
                    destination="0.0.0.0/0",
                    destination_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListEgressSecurityRuleTcpOptionsArgs(
                        max=443,
                        min=443,
                    ),
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Pod to Kubernetes API endpoint communication (when using VCN-native pod networking).",
                    protocol="6",
                    destination=self.public_subnet_address,
                    destination_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListEgressSecurityRuleTcpOptionsArgs(
                        max=6443,
                        min=6443,
                    ),
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Pod to Kubernetes API endpoint communication (when using VCN-native pod networking).",
                    protocol="6",
                    destination=self.public_subnet_address,
                    destination_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListEgressSecurityRuleTcpOptionsArgs(
                        max=12250,
                        min=12250,
                    ),
                ),
            ],
        )

        # Create a separate Security List for the Public Subnet
        self.loadbalancers_security_list = oci.core.SecurityList(
            "LoadBalancersSecurityList",
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            display_name=f"LoadBalancersSecurityList-{self.display_name}",
            ingress_security_rules=[
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Load balancer listener protocol and port. Customize as required.",
                    protocol="6",
                    source=self.pods_subnet_address,
                    source_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListIngressSecurityRuleTcpOptionsArgs(
                        max=443,
                        min=443,
                    ),
                ),
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Load balancer listener protocol and port. Customize as required.",
                    protocol="6",
                    source=self.pods_subnet_address,
                    source_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListIngressSecurityRuleTcpOptionsArgs(
                        max=80,
                        min=80,
                    ),
                ),
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Load balancer listener protocol and port. Customize as required.",
                    protocol="6",
                    source="0.0.0.0/0",
                    source_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListIngressSecurityRuleTcpOptionsArgs(
                        max=443,
                        min=443,
                    ),
                ),
                oci.core.SecurityListIngressSecurityRuleArgs(
                    description="Load balancer listener protocol and port. Customize as required.",
                    protocol="6",
                    source="0.0.0.0/0",
                    source_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListIngressSecurityRuleTcpOptionsArgs(
                        max=80,
                        min=80,
                    ),
                ),
            ],
            egress_security_rules=[
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Load balancer to worker nodes node ports.",
                    protocol="6",
                    destination=self.workers_subnet_address,
                    destination_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListEgressSecurityRuleTcpOptionsArgs(
                        min=30000,
                        max=32767,
                    ),
                ),
                oci.core.SecurityListEgressSecurityRuleArgs(
                    description="Allow load balancer to communicate with kube-proxy on worker nodes.",
                    protocol="6",
                    destination=self.workers_subnet_address,
                    destination_type="CIDR_BLOCK",
                    tcp_options=oci.core.SecurityListEgressSecurityRuleTcpOptionsArgs(
                        max=10256,
                        min=10256,
                    ),
                ),
            ],
        )

        # Create a Route Table for the private subnet with a route via the NAT Gateway
        self.workers_route_table = oci.core.RouteTable(
            "WorkersRouteTable",
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            display_name=f"WorkersRouteTable-{self.display_name}",
            route_rules=[
                oci.core.RouteTableRouteRuleArgs(
                    destination="0.0.0.0/0",
                    network_entity_id=self.nat_gateway.id,
                ),
                oci.core.RouteTableRouteRuleArgs(
                    destination=oci.core.get_services().services[0].cidr_block,
                    destination_type="SERVICE_CIDR_BLOCK",
                    network_entity_id=self.service_gateway.id,
                ),
            ],
        )

        # Create a Route Table for the public subnet with a route via the Internet Gateway
        self.public_route_table = oci.core.RouteTable(
            "PublicRouteTable",
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            display_name=f"PublicRouteTable-{self.display_name}",
            route_rules=[
                oci.core.RouteTableRouteRuleArgs(
                    destination="0.0.0.0/0",
                    network_entity_id=self.internet_gateway.id,
                ),
            ],
        )

        # Create a Route Table for the loadbalancers subnet with a route via the Internet Gateway
        self.loadbalancers_route_table = oci.core.RouteTable(
            "LoadBalancersRouteTable",
            compartment_id=self.compartment_id,
            vcn_id=self.vcn.id,
            display_name=f"LoadBalancersRouteTable-{self.display_name}",
            route_rules=[
                oci.core.RouteTableRouteRuleArgs(
                    destination="0.0.0.0/0",
                    network_entity_id=self.internet_gateway.id,
                ),
            ],
        )

        # Create a Public Subnet within the VCN
        self.public_subnet = oci.core.Subnet(
            "PublicSubnet",
            compartment_id=self.compartment_id,
            security_list_ids=[self.public_security_list.id],
            vcn_id=self.vcn.id,
            cidr_block=self.public_subnet_address,
            display_name=f"PublicSubnet-{self.display_name}",
            dns_label="public",
            prohibit_public_ip_on_vnic=False,
            route_table_id=self.public_route_table.id,
        )

        # Create a Private Subnet within the VCN
        self.workers_subnet = oci.core.Subnet(
            "WorkersSubnet",
            compartment_id=self.compartment_id,
            security_list_ids=[self.workers_security_list.id],
            vcn_id=self.vcn.id,
            cidr_block=self.workers_subnet_address,
            display_name=f"WorkersSubnet-{self.display_name}",
            dns_label="workers",
            prohibit_public_ip_on_vnic=True,
            route_table_id=self.workers_route_table.id,
        )

        # Create a Pods Subnet within the VCN
        self.pods_subnet = oci.core.Subnet(
            "PodsSubnet",
            compartment_id=self.compartment_id,
            security_list_ids=[self.pods_security_list.id],
            vcn_id=self.vcn.id,
            cidr_block=self.pods_subnet_address,
            display_name=f"PodsSubnet-{self.display_name}",
            dns_label="pods",
            prohibit_public_ip_on_vnic=True,
            route_table_id=self.workers_route_table.id,
        )

        # Create a LoadBalancers Subnet within the VCN
        self.loadbalancers_subnet = oci.core.Subnet(
            "LoadBalancersSubnet",
            compartment_id=self.compartment_id,
            security_list_ids=[self.loadbalancers_security_list.id],
            vcn_id=self.vcn.id,
            cidr_block=self.loadbalancers_subnet_address,
            display_name=f"LoadBalancersSubnet-{self.display_name}",
            dns_label="loadbalancers",
            prohibit_public_ip_on_vnic=False,
            route_table_id=self.loadbalancers_route_table.id,
        )

        self.register_outputs({})
