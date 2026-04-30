# Terraform: ImageUiApp infrastructure

Provisions the EC2 host (Caddy + Streamlit native OIDC), its IAM role, its
security group, and an Elastic IP. Brings the existing family-photos S3
bucket under Terraform management without recreating it.

## Resources

| File | Resources |
|------|-----------|
| `versions.tf` | Terraform + AWS provider version constraints |
| `main.tf` | AWS provider, default tags, AMI lookup |
| `s3.tf` | `aws_s3_bucket` for the existing bucket (imported, `prevent_destroy`) |
| `iam.tf` | EC2 instance role + S3 inline policy + instance profile |
| `ec2.tf` | Security group, EC2 instance (t4g.micro AL2023 ARM, IMDSv2), Elastic IP |
| `variables.tf` | Inputs |
| `outputs.tf` | Public IP, instance ID, role ARN, etc. |

## Prerequisites

1. Existing S3 bucket (the family photos bucket). This Terraform never
   creates a bucket; it imports the existing one.
2. Existing EC2 key pair in the target region.
3. Admin AWS credentials. Daily IaC use should go through the
   `imageuiapp-admin` STS role — see `infrastructure/cloudformation/admin-role/`
   and `scripts/aws/assume_admin.sh`.
4. Backup of the bucket BEFORE first run, just in case (`scripts/aws/backup_s3.sh`).

## Usage

```bash
cd infrastructure/terraform/imageuiapp

cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set ssh_admin_cidr, ec2_ssh_key_name, etc.
# terraform.tfvars is gitignored.

terraform init

# IMPORTANT: pull the existing bucket into state before plan/apply,
# otherwise Terraform will try to CREATE it and fail (BucketAlreadyExists).
terraform import aws_s3_bucket.imageuiapp $(grep -E '^s3_bucket_name' terraform.tfvars | cut -d'"' -f2)

terraform plan
terraform apply
```

After apply, `terraform output public_ip` gives the EIP. Point your Route 53
record `app.<your-domain>` at that IP, then SSH in and run
`s3_image_croper_ui_app/install_as_aws_linux_caddy.sh`.

## Safety: prevent accidental bucket deletion

`aws_s3_bucket.imageuiapp` has `lifecycle.prevent_destroy = true`. Any plan
that would delete or replace the bucket aborts with a clear error.

To intentionally delete the bucket (you almost never want this):

1. Empty it (or it will fail with BucketNotEmpty)
2. Remove `prevent_destroy` from `s3.tf`
3. `terraform apply`

## State management

Backend is local (`terraform.tfstate`). For shared use, switch to an S3 +
DynamoDB remote backend in a follow-up. The state file is gitignored.

## Cost (eu-central-1, approx)

| Resource | $/mo |
|----------|------|
| EC2 t4g.micro on-demand | ~$6 |
| EBS 30 GB gp3 | ~$2.40 |
| Elastic IP (associated) | $0 |
| Security group / IAM | $0 |
| S3 (existing, ~30 MB family photos) | cents |
| **Total** | **~$7** |

Compared to the previous ALB-fronted setup (~$28-32/mo), this is ~75-80%
saving while keeping Entra ID OIDC auth strength.
