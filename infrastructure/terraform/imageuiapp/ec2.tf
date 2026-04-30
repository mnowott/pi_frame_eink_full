resource "aws_security_group" "imageuiapp" {
  name        = "${var.instance_name}-sg"
  description = "ImageUiApp: SSH from admin, 80/443 public for Caddy"

  ingress {
    description = "SSH from admin CIDR"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_admin_cidr]
  }

  ingress {
    description = "HTTP for Caddy LE HTTP-01 and HTTP-to-HTTPS redirect"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS via Caddy"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound (S3, package mirrors, Entra IdP, ACME)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.instance_name}-sg" })
}

resource "aws_instance" "imageuiapp" {
  ami                    = data.aws_ami.al2023_arm64.id
  instance_type          = var.instance_type
  key_name               = var.ec2_ssh_key_name
  vpc_security_group_ids = [aws_security_group.imageuiapp.id]
  iam_instance_profile   = aws_iam_instance_profile.imageuiapp.name

  root_block_device {
    volume_size = var.ebs_size_gb
    volume_type = "gp3"
    encrypted   = true
  }

  # Enforce IMDSv2 — token-required metadata access mitigates SSRF leaks.
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  tags = merge(var.tags, { Name = var.instance_name })

  lifecycle {
    # Avoid replacing the instance just because Amazon publishes a newer AMI.
    ignore_changes = [ami]
  }
}

resource "aws_eip" "imageuiapp" {
  instance = aws_instance.imageuiapp.id
  domain   = "vpc"
  tags     = merge(var.tags, { Name = var.instance_name })
}
