# MFA Physical Token Simulator - Demonstration Runbook & Viva Guide

This runbook provides a structured walkthrough for demonstrating the **MFA Physical Token Simulator & Security Operations Dashboard** during college evaluations, project reviews, or technical interviews.

---

## 1. Quick Launch (30 Seconds)

Open Windows PowerShell in the project directory:

```powershell
# 1. Activate the environment
.\.venv\Scripts\Activate.ps1

# 2. Run system verification (shows examiner all 7 core policies pass)
python verify_system.py

# 3. Start the dashboard application
python app.py
```

Open your browser to:
```
http://127.0.0.1:5000
```

---

## 2. 7-Step Demonstration Script

### Step 1: Executive Tour of the Security Operations Dashboard (1 Min)
- **Action:** Open the **Dashboard** view (`#view-dashboard`).
- **Explanation:**
  > *"This dashboard monitors our Multi-Factor Authentication ecosystem. At the top, we have 4 real-time KPI cards tracking total generated tokens, successful verifications, failed attempts, and the current token session state. On the left is an HTML5 Canvas authentication activity chart, and on the right is our quick hardware keyfob status widget."*

---

### Step 2: The Core Concept of Multi-Factor Authentication (30 Secs)
- **Explanation:**
  > *"Standard authentication relies purely on the Knowledge Factor—something the user knows, like a password. Multi-Factor Authentication introduces a second independent factor: Possession—something the user has. Our simulator models a physical hardware keyfob (like an RSA SecurID token or hardware authenticator) that generates a dynamic, time-limited 6-digit One-Time Password."*

---

### Step 3: OTP Generation & Temporal Expiry (1 Min)
- **Action:**
  1. Click **"MFA Authentication"** in the left sidebar.
  2. Click the **"Generate New OTP"** button.
- **Observations to Highlight:**
  - The LCD screen illuminates with a cryptographically secure 6-digit code (e.g. `742918`).
  - The **synchronous countdown timer** begins counting down from `02:00` (120 seconds).
  - The progress bar changes color smoothly from **Cyan/Green** (>50%) to **Amber** (20%-50%) to **Red** (<20%).
  - The KPI cards and mini-fob in the dashboard synchronize automatically.

---

### Step 4: Proving Replay Attack Defense (Single-Use Token) (1 Min)
- **Action:**
  1. Click **"Auto-Fill into Verifier"** (or type the generated code).
  2. Click **"Verify OTP"**.
  3. **Result:** Green success alert: *"OTP verified successfully! Token consumed."*
  4. Notice the LCD screen immediately switches to `VALID` and the token state changes to `Consumed`.
  5. Now, without generating a new OTP, click **"Verify OTP"** again with the same code.
  6. **Result:** Red rejection alert: *"No active OTP found. Please generate a new OTP first."*
- **Explanation:**
  > *"This proves our single-use anti-replay policy. Once a token is validated, the server immediately destroys it in memory. If an attacker intercepts the token across the network and tries to resubmit it, the server rejects it with HTTP 400."*

---

### Step 5: Proving Brute-Force Lockout Defense (1 Min)
- **Action:**
  1. Click **"Generate New OTP"**.
  2. Enter an incorrect code (e.g. `000000`).
  3. Click **"Verify OTP"**.
  4. Notice the warning message: *"Invalid OTP. 4 attempt(s) remaining."*
  5. Enter wrong codes 4 more times until 5 attempts are reached.
  6. **Result:** The LCD display switches to `LOCKED`, the badge turns red (`Locked Out`), and the token is revoked.
- **Explanation:**
  > *"To defend against automated dictionary or brute-force guessing attacks, our backend limits failed attempts to 5. Once exceeded, the active token session is completely revoked."*

---

### Step 6: Zero-Knowledge Telemetry & AWS CloudWatch (1 Min)
- **Action:**
  1. Click **"Audit Logs"** in the left sidebar.
  2. Show the real-time event stream (`OTP_GENERATED`, `OTP_VERIFY_SUCCESS`, `OTP_LOCKOUT_MAX_ATTEMPTS`).
  3. Type `LOCKOUT` in the search filter to show instantaneous search.
  4. Click the filter pills: **All Events**, **Success**, **Warning**.
- **Explanation:**
  > *"Notice that our logs record event metadata, timestamps, and client IP addresses, but NEVER the raw OTP value. This follows the Zero-Knowledge security principle. In production, these structured logs stream directly to AWS CloudWatch Log Group `/aws/flask/MFA-Token-Simulator` using boto3 and watchtower."*

---

### Step 7: Live Runtime Policy Tuning (1 Min)
- **Action:**
  1. Click **"Settings"** in the sidebar.
  2. Change **OTP Time-To-Live (TTL)** from `120 Seconds` to `30 Seconds`.
  3. Click **"Save & Apply Policies"**.
  4. Return to **"MFA Authentication"** and click **"Generate New OTP"**.
  5. Notice the timer now begins counting down from `00:30`!
- **Explanation:**
  > *"All security policies are dynamically configurable via REST APIs (`/api/settings`), allowing administrators to adjust security posture in real time."*

---

## 3. Examiner & Interviewer Q&A Cheat Sheet

### Q1: Why did you use Python's `secrets` module instead of `random.randint`?
> **Answer:**  
> `random.randint` uses the Mersenne Twister algorithm, which is a pseudo-random generator designed for statistical modeling, not security. If an attacker observes approximately 624 generated outputs, they can reconstruct the internal state and predict future OTPs. Python's `secrets` module utilizes the operating system's cryptographic random source (`CryptGenRandom` on Windows, `getrandom()` on Linux), ensuring cryptographic unpredictability.

---

### Q2: How does `secrets.compare_digest` protect against timing attacks?
> **Answer:**  
> Standard string comparison (`==`) terminates evaluation at the first mismatched character. An attacker with a precise network timer can measure small latency differences to guess each digit sequentially. `secrets.compare_digest` operates in constant time, comparing all characters regardless of mismatches, eliminating the timing side-channel.

---

### Q3: What is the difference between this simulator and RFC 6238 TOTP (Google Authenticator)?
> **Answer:**  
> In RFC 6238 TOTP, both the client and server share a secret seed key, and tokens are computed locally using HMAC-SHA1 on the current UNIX time counter (in 30-second intervals). In this physical token simulator, the token is generated server-side using CSPRNG and modeled on an isolated physical token LCD screen with dynamic TTL expiry.

---

### Q4: Why is in-memory storage used here, and how would you scale this in production?
> **Answer:**  
> In-memory storage with thread locks (`threading.RLock`) was chosen to provide a completely self-contained, zero-cost, local demonstration environment without requiring external database dependencies. In an auto-scaling cloud production environment with multiple web containers, we would replace the in-memory dictionary with **Amazon ElastiCache for Redis** or **Amazon DynamoDB** with native TTL attributes.

---

### Q5: Why don't you log the OTP values to AWS CloudWatch?
> **Answer:**  
> Logging authentication credentials (even temporary ones) violates compliance standards like PCI-DSS and NIST SP 800-63B. Anyone with read access to CloudWatch log groups would be able to intercept active OTPs. We log events (`OTP_GENERATED`, `OTP_VERIFIED`), but never the secret payload itself.

