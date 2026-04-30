variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-central-1"
}

variable "s3_bucket_name" {
  description = <<-EOT
    Name of the EXISTING S3 bucket holding family photos. Must already exist
    in AWS. Bring it under Terraform management with:
        terraform import aws_s3_bucket.imageuiapp <bucket-name>
    The bucket has `lifecycle.prevent_destroy = true` to prevent accidents.
  EOT
  type        = string
}

variable "instance_name" {
  description = "Name tag and prefix for EC2/IAM/SG resources."
  type        = string
  default     = "imageuiapp"
}

variable "instance_type" {
  description = "EC2 instance type. t4g.micro is the cost-optimised default."
  type        = string
  default     = "t4g.micro"
}

variable "ssh_admin_cidr" {
  description = "CIDR allowed to SSH to the instance, e.g. 1.2.3.4/32. Set to a single IP, not 0.0.0.0/0."
  type        = string

  validation {
    condition     = can(regex("^[0-9.]+/[0-9]+$", var.ssh_admin_cidr))
    error_message = "ssh_admin_cidr must look like A.B.C.D/NN."
  }
}

variable "ec2_ssh_key_name" {
  description = "Name of an existing EC2 key pair (in this region) for SSH access."
  type        = string
}

variable "ebs_size_gb" {
  description = "Root EBS volume size in GiB."
  type        = number
  default     = 8
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default = {
    Project = "pi-epaper-photo-frame"
    App     = "imageuiapp"
    ManagedBy = "terraform"
  }
}
