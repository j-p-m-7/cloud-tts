variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "aws region"
}

variable "environment" {
  type        = string
  default     = "production"
  description = "development or production"
}

variable "instance_type" {
  type        = string
  default     = "c8g.xlarge"
  description = "arm64 instance"
}

variable "max_worker_capacity" {
  type        = number
  default     = 10
  description = "max number of ec2 worker instances"
}
