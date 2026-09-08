resource "aws_ecr_repository" "backend" {
  name                 = "calculator-backend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "aws_ecr_repository" "frontend" {
  name                 = "calculator-frontend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}
