output "public_ip" {
  description = "Elastic IP. Point your Route 53 A record `app.<your-domain>` here."
  value       = aws_eip.imageuiapp.public_ip
}

output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.imageuiapp.id
}

output "iam_role_arn" {
  description = "ARN of the EC2 instance role used by ImageUiApp for S3 access."
  value       = aws_iam_role.imageuiapp.arn
}

output "security_group_id" {
  description = "Security group attached to the instance."
  value       = aws_security_group.imageuiapp.id
}

output "ami_id" {
  description = "AMI used for the instance."
  value       = data.aws_ami.al2023_arm64.id
}

output "ssh_command" {
  description = "Convenience SSH command (replace key path)."
  value       = "ssh -i <your-keyfile.pem> ec2-user@${aws_eip.imageuiapp.public_ip}"
}
