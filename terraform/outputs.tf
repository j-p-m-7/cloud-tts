output "sqs_queue_url" {
  value       = aws_sqs_queue.tts_queue.url
  description = "target sqs endpoint url for ingestion scripts"
}

output "input_bucket_name" {
  value       = aws_s3_bucket.input_bucket.id
  description = "s3 input data bucket id"
}

output "output_bucket_name" {
  value       = aws_s3_bucket.output_bucket.id
  description = "s3 audio storage bucket id"
}
