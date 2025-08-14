Setup automation for VAST SE Labs.

Limitations:

- does not deploy kafka (coming soon)

Expectations:

- setup is for default tenant only.

Steps:

1. cp terraform.tfvars-examples terraform.tfvars
2. edit terraform.tfvars
3. ./tf_cmd.sh init
4. ./tf_cmd.sh plan
5. ./tf_cmd.sh apply
