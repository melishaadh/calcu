variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name used to prefix/tag all resources"
  type        = string
  default     = "calculator"
}

variable "instance_type" {
  description = "EC2 instance type for the app server"
  type        = string
  default     = "t3.micro"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_password" {
  description = "Master password for the RDS PostgreSQL instance"
  type        = string
  sensitive   = true
}

variable "key_name" {
  description = "Name of an existing EC2 key pair, used for SSH access"
  type        = string
}

variable "domain_name" {
  description = "Domain name (must already have a Route 53 hosted zone) that will point to the EC2 instance"
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH into the EC2 instance"
  type        = string
  default     = "0.0.0.0/0"
}
