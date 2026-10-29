# Deployment Guide: MFA Physical Token Simulator

This guide provides step-by-step instructions for deploying the **MFA Physical Token Simulator** to modern cloud hosting platforms when you are ready to deploy.

> **Important Security Notice:**  
> This application is configured to run locally without any external dependencies. Deploying to the cloud is **optional** and should be executed manually using your own cloud credentials.

---

## 1. Production Architecture Overview

```
                      [ Client Browser ]
                              │
                              ▼
                   [ Reverse Proxy / CDN ]
                   (Cloudflare / AWS ALB)
                              │  HTTPS (Port 443)
                              ▼
                [ Production WSGI Server ]
             Gunicorn (Workers: 2, Threads: 4)
                              │
                              ▼
                  [ Flask Application ]
                         (wsgi.py)
                   /                  \
                  ▼                    ▼
     [ Local / In-Memory State ]    [ AWS CloudWatch Logs ]
     - Active OTP Token             - Region: ap-southeast-2
     - Rate-limiting counters       - Log Group: /aws/flask/MFA-Token-Simulator
     - Audit event ring buffer      - Least-Privilege IAM Policy
```

---

## 2. Production Entry Point & Startup Command

- **WSGI Entry Point:** `wsgi:application` (located in `wsgi.py`)
- **Recommended WSGI Server:** [Gunicorn](https://gunicorn.org/) (for Linux/Unix environments)
- **Standard Startup Command:**
  ```bash
  gunicorn wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60
  ```
- **Included Configuration File:** `Procfile` is pre-configured with this command for platforms supporting Buildpacks (Heroku, Render, Railway, AWS Elastic Beanstalk).

---

## 3. Environment Variable Configuration

Configure the following environment variables in your hosting platform's dashboard:

| Variable | Recommended Production Value | Description |
| :--- | :--- | :--- |
| `FLASK_ENV` | `production` | Sets execution environment |
| `FLASK_DEBUG` | `0` | **Crucial:** Disables Flask interactive debugger |
| `PORT` | Set automatically by PaaS (or `8080` / `5000`) | Port to listen on |
| `SECRET_KEY` | *(Generate a 64-character random string)* | Used for cryptographic session signing |
| `OTP_TTL_SECONDS` | `120` | OTP validity window in seconds |
| `DEMO_SHOW_OTP` | `1` (for demo) or `0` (for strict mode) | Whether to return the OTP in API response |
| `RATE_LIMIT_GENERATE_SECONDS` | `5` | Anti-flooding cooldown between generation calls |
| `MAX_VERIFY_ATTEMPTS` | `5` | Brute-force lockout attempt limit |
| `CLOUDWATCH_ENABLED` | `0` (or `1` if AWS credentials provided) | Enable/disable AWS logging |
| `CLOUDWATCH_LOG_GROUP`| `/aws/flask/MFA-Token-Simulator` | AWS CloudWatch log group name |
| `AWS_DEFAULT_REGION` | `ap-southeast-2` | AWS region (Sydney) |

---

## 4. Platform Deployment Options

### Option A: Deploy to Render (Recommended for Students)

1. **Push your code to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit: MFA Token Simulator"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git push -u origin main
   ```
2. **Log into [Render.com](https://render.com) and click "New +" -> "Web Service".**
3. **Connect your GitHub repository.**
4. **Configure the Web Service Settings:**
   - **Name:** `mfa-token-simulator`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn wsgi:application`
5. **Configure Health Check Path:**
   - Set Health Check Path to: `/api/health`
6. **Add Environment Variables:**
   - Go to the **Environment** tab.
   - Add `FLASK_ENV=production`, `FLASK_DEBUG=0`, `DEMO_SHOW_OTP=1`, `OTP_TTL_SECONDS=120`.
   - If using AWS CloudWatch, add `CLOUDWATCH_ENABLED=1`, `AWS_DEFAULT_REGION=ap-southeast-2`, `AWS_ACCESS_KEY_ID=...`, and `AWS_SECRET_ACCESS_KEY=...`.
7. **Deploy:** Click **Create Web Service**.

---

### Option B: Deploy to AWS App Runner

1. In the AWS Console, navigate to **AWS App Runner**.
2. Click **Create an App Runner service**.
3. Under **Source code repository**, connect your GitHub account and choose this repository.
4. Set **Build settings**:
   - Runtime: `Python 3`
   - Build command: `pip install -r requirements.txt`
   - Start command: `python -m gunicorn wsgi:application --bind 0.0.0.0:8080`
   - Port: `8080`
5. Under **Security & Instance role**:
   - Attach an IAM role with the CloudWatch policy documented in Section 5.
   - App Runner automatically assumes this role via the instance metadata service (no static access keys needed!).
6. Under **Health check**:
   - Protocol: `HTTP`
   - Path: `/api/health`
   - Interval: 10s, Timeout: 5s, Healthy threshold: 1

---

### Option C: Deploy to AWS Elastic Beanstalk

1. Ensure `Procfile`, `wsgi.py`, and `requirements.txt` are at the repository root.
2. Initialize Elastic Beanstalk:
   ```bash
   eb init -p python-3.11 mfa-token-simulator --region ap-southeast-2
   ```
3. Create the environment:
   ```bash
   eb create mfa-simulator-prod --instance-types t3.micro
   ```
4. Set environment properties:
   ```bash
   eb setenv FLASK_ENV=production FLASK_DEBUG=0 DEMO_SHOW_OTP=1 CLOUDWATCH_ENABLED=1
   ```

---

## 5. AWS IAM Least-Privilege Policy for CloudWatch

To stream logs from the Flask backend to AWS CloudWatch Logs, attach the following least-privilege IAM policy to your IAM User or EC2/App Runner instance role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "MFACloudWatchLogsAccess",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams"
      ],
      "Resource": [
        "arn:aws:logs:ap-southeast-2:*:log-group:/aws/flask/MFA-Token-Simulator",
        "arn:aws:logs:ap-southeast-2:*:log-group:/aws/flask/MFA-Token-Simulator:*"
      ]
    }
  ]
}
```

### Verifying Logs in the AWS Management Console:
1. Open the [AWS Management Console](https://console.aws.amazon.com/).
2. Select the **ap-southeast-2 (Sydney)** region in the top navigation bar.
3. Open **CloudWatch** and select **Logs** > **Log groups** in the left sidebar.
4. Select the log group `/aws/flask/MFA-Token-Simulator`.
5. Click on the log stream `simulator-flask-stream`.
6. Inspect the live log events emitted whenever an OTP is generated or verified. Notice that **no OTP values** are ever exposed in CloudWatch.

---

## 6. Architectural Considerations & Distributed Scaling

### Current In-Memory State
- The simulator stores the active OTP and failed verification attempts in memory via `otp_service.py` with thread locks.
- **Single-instance scaling:** This works for single-process instances (e.g. 1 dyno, 1 container, or multi-threaded worker).
- **Multi-instance limitation:** If you scale your application to multiple web servers/containers behind a round-robin load balancer, a user generating an OTP on Instance A might have their verification request sent to Instance B, where the OTP does not exist in memory.

### Upgrade Path for Distributed Production
If upgrading to a multi-instance production deployment:
1. Replace in-memory dictionaries with **AWS ElastiCache for Redis** or **Amazon DynamoDB**.
2. Store OTP sessions with a DynamoDB `TTL` attribute matching `OTP_TTL_SECONDS`.
3. DynamoDB automatically expires and purges old tokens after the TTL window.

