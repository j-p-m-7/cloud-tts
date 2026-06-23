resource "aws_security_group" "worker_sg" {
  name        = "tts-worker-sg"
  description = "security group for ec2 workers"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
}

resource "aws_launch_template" "worker_template" {
  name_prefix   = "tts-worker-template-"
  image_id      = "ami-051f8a213d6ba0022"
  instance_type = var.instance_type

  iam_instance_profile {
    arn = aws_iam_instance_profile.worker_profile.arn
  }

  network_interfaces {
    associate_public_ip_address = true
    security_groups             = [aws_security_group.worker_sg.id]
  }

  user_data = base64encode(<<-EOF
              #!/bin/bash
              sudo dnf update -y
              sudo dnf install -y docker
              sudo systemctl start docker
              sudo systemctl enable docker

              # Initialize Kokoro Translation Engine Container
              sudo docker run -d \
                --name kokoro-api \
                --restart always \
                -p 8880:8880 \
                ghcr.io/remsky/kokoro-fastapi-cpu:latest

              # Initialize Primary Pipeline Processing Image
              sudo docker run -d \
                --name tts-worker \
                --restart always \
                --network="host" \
                -e SQS_QUEUE_URL="${aws_sqs_queue.tts_queue.url}" \
                ghcr.io/j-p-m-7/tts-worker:latest
              EOF
  )

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "worker_asg" {
  name_prefix         = "tts-asg-fleet-"
  vpc_zone_identifier = data.aws_subnets.default.ids
  min_size            = 0
  desired_capacity    = 1
  max_size            = var.max_worker_capacity

  launch_template {
    id      = aws_launch_template.worker_template.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "Distributed-TTS-Worker-Fleet"
    propagate_at_launch = true
  }
}
