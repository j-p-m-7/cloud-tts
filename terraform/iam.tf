resource "aws_iam_instance_profile" "worker_profile" {
  name = "tts-worker-instance-profile-${var.environment}"
  role = aws_iam_role.worker_role.name
}

resource "aws_iam_role" "worker_role" {
  name = "tts-worker-system-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
      }
    ]
  })
}

resource "aws_iam_policy" "worker_policy" {
  name        = "tts-worker-pipeline-permissions"
  description = "policy for pipeline workers"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # read access from input bucket
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.input_bucket.arn,
          "${aws_s3_bucket.input_bucket.arn}/*"
        ]
      },
      # write access to logging buckets
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:PutObjectAcl"]
        Resource = [
          "${aws_s3_bucket.output_bucket.arn}/*"
        ]
      },
      # sqs queue access
      {
        Effect   = "Allow"
        Action   = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.tts_queue.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_worker_policy" {
  role       = aws_iam_role.worker_role.name
  policy_arn = aws_iam_policy.worker_policy.arn
}
