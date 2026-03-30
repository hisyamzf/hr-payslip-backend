#!/bin/bash
# AWS EC2 Setup Script for HR Payslip Backend

# Update and install Docker
sudo apt-get update -y
sudo apt-get install -y docker.io docker-compose

# Add current user to docker group
sudo usermod -aG docker $USER

# Install WeasyPrint system dependencies
sudo apt-get install -y \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    libimagequant0 \
    libraqm-0.10-0 \
    libjpeg62-turbo \
    libdeflate0 \
    libopenjp2-7 \
    libwebp7

# Start Docker
sudo systemctl start docker
sudo systemctl enable docker

echo "✅ Setup complete!"
echo "Next steps:"
echo "1. Upload backend folder to server"
echo "2. Run: cd backend && docker-compose up -d"
