terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Environment = var.environment
      Pipeline    = "Distributed-TTS-Engine"
    }
  }
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_s3_bucket" "input_bucket" {
  bucket        = "tts-pipeline-input-${var.environment}"
  force_destroy = true
}

resource "aws_s3_bucket" "output_bucket" {
  bucket        = "tts-pipeline-output-${var.environment}"
  force_destroy = true
}

resource "aws_sqs_queue" "tts_dlq" {
  name                      = "tts-pipeline-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "tts_queue" {
  name                      = "tts-queue"
  delay_seconds             = 0
  max_message_size          = 262144
  message_retention_seconds = 86400
  receive_wait_time_seconds = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.tts_dlq.arn
    maxReceiveCount     = 3
  })
}
