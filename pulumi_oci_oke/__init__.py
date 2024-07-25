import pulumi
import pulumi_oci as oci
import helper
import network
from typing import Optional

class Cluster(pulumi.ComponentResource):
    def __init__(self,
                 resource_name: str,
                 compartment_id: pulumi.Input[str],
                 # optional parameters
                 opts: Optional[pulumi.ResourceOptions] = None,
                 oke_image:  Optional[pulumi.Input[str]] = None,
                 cidr_block: Optional[pulumi.Input[str]] = None,
                 display_name: Optional[pulumi.Input[str]] = None):
        """
        This resource provides a complete OKE cluster infrastructure with all depending resources

        :param str resource_name: The name of the resource
        :param pulumi.ResourceOptions opts: Options for the resource.
        :param pulumi.Input[str] compartment_id: (Updatable) The [OCID](https://docs.cloud.oracle.com/iaas/Content/General/Concepts/identifiers.htm) of the compartment
        :param pulumi.Input[str] cidr_block: Default: `10.0.0.0/16`
        :param pulumi.Input[Mapping[str, Any]] defined_tags: (Updatable) Defined tags for this resource. Each key is predefined and scoped to a namespace. For more information, see [Resource Tags](https://docs.cloud.oracle.com/iaas/Content/General/Concepts/resourcetags.htm).  Example: `{"Operations.CostCenter": "42"}`
        :param pulumi.Input[str] oke_image: (Updatable) The [OCID](https://docs.cloud.oracle.com/iaas/Content/General/Concepts/identifiers.htm) of the image to use in the default cluster pool.
        :param pulumi.Input[str] display_name: (Updatable) A user-friendly name. Does not have to be unique, and it's changeable. Avoid entering confidential information.
        """
        super().__init__('OkeCluster', resource_name, None, opts)
        h = helper.Helper()

        if cidr_block is None:
            self.cidr_block = "10.0.0.0/16"
        else:
            self.cidr_block = cidr_block

        if display_name is None:
            self.display_name = h.get_random_word()
        else:
            self.display_name = display_name

        self.resource_name = resource_name
        self.compartment_id = compartment_id

