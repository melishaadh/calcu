output "ecr_backend_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_repository_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "ec2_public_ip" {
  value = aws_instance.app_server.public_ip
}

output "rds_endpoint" {
  value = aws_db_instance.postgres.address
}

output "s3_bucket_name" {
  value = aws_s3_bucket.app_bucket.bucket
}

output "app_domain" {
  value = aws_route53_record.app.fqdn
}
