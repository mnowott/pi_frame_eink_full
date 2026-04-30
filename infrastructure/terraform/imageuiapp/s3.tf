# Existing S3 bucket holding the family photos. The bucket is NOT created by
# this Terraform run; it must already exist and be imported:
#
#     terraform import aws_s3_bucket.imageuiapp <bucket-name>
#
# `prevent_destroy` makes `terraform destroy` and any plan that would remove
# the bucket fail loudly. Remove that lifecycle block only if you really mean
# to delete the bucket (and its photos).

resource "aws_s3_bucket" "imageuiapp" {
  bucket = var.s3_bucket_name

  lifecycle {
    prevent_destroy = true
  }

  tags = var.tags
}
