FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev openssh-client sshpass \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (includes ansible-runner + ansible-core)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Ansible Galaxy collections at build time
COPY ansible/requirements.yml ansible/requirements.yml
RUN ansible-galaxy collection install -r ansible/requirements.yml

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
