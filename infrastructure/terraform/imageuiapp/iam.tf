# Instance role used by the ImageUiApp EC2. Replaces the long-lived
# AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY pair previously written into
# /home/ec2-user/.bashrc — the EC2 picks credentials up from the IMDS.

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "imageuiapp" {
  name               = "${var.instance_name}-ec2"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
  tags               = var.tags
}

data "aws_iam_policy_document" "imageuiapp_s3" {
  statement {
    sid    = "BucketLevelAccess"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [aws_s3_bucket.imageuiapp.arn]
  }

  statement {
    sid    = "ObjectLevelAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.imageuiapp.arn}/*"]
  }
}

resource "aws_iam_role_policy" "imageuiapp_s3" {
  name   = "${var.instance_name}-s3"
  role   = aws_iam_role.imageuiapp.id
  policy = data.aws_iam_policy_document.imageuiapp_s3.json
}

resource "aws_iam_instance_profile" "imageuiapp" {
  name = "${var.instance_name}-ec2"
  role = aws_iam_role.imageuiapp.name
  tags = var.tags
}
