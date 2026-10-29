/**
 * MFA Sentinel - Security Operations & Token Simulator Dashboard
 * Complete client-side application logic: view routing, real-time KPI telemetry,
 * activity canvas chart, interactive hardware token simulator, audit filtering, and settings.
 */

document.addEventListener("DOMContentLoaded", () => {
    // =========================================================================
    // DOM Elements Cache
    // =========================================================================

    // Navigation & Layout
    const navItems = document.querySelectorAll(".nav-item");
    const viewPanels = document.querySelectorAll(".view-panel");
    const currentViewTitle = document.getElementById("currentViewTitle");
    const currentViewSubtitle = document.getElementById("currentViewSubtitle");
    const mobileMenuBtn = document.getElementById("mobileMenuBtn");
    const sidebar = document.getElementById("sidebar");
    const sidebarBackdrop = document.getElementById("sidebarBackdrop");
    const liveClock = document.getElementById("liveClock");

    // Top Bar Quick Actions
    const quickGenerateTopBtn = document.getElementById("quickGenerateTopBtn");
    const cwStatusPill = document.getElementById("cwStatusPill");
    const cwStatusDot = document.getElementById("cwStatusDot");
    const cwStatusLabel = document.getElementById("cwStatusLabel");

    // Dashboard View (KPIs & Mini Fob)
    const kpiTotalGenerated = document.getElementById("kpiTotalGenerated");
    const kpiTotalVerified = document.getElementById("kpiTotalVerified");
    const kpiTotalFailed = document.getElementById("kpiTotalFailed");
    const kpiSuccessRate = document.getElementById("kpiSuccessRate");
    const kpiRateLimitedBadge = document.getElementById("kpiRateLimitedBadge");
    const kpiTokenState = document.getElementById("kpiTokenState");
    const kpiCountdownText = document.getElementById("kpiCountdownText");
    const kpiTtlSub = document.getElementById("kpiTtlSub");
    const miniFobBadge = document.getElementById("miniFobBadge");
    const miniLcdOtp = document.getElementById("miniLcdOtp");
    const miniLcdSub = document.getElementById("miniLcdSub");
    const miniSerial = document.getElementById("miniSerial");
    const miniBattery = document.getElementById("miniBattery");
    const miniDrift = document.getElementById("miniDrift");
    const recentAttemptsTableBody = document.getElementById("recentAttemptsTableBody");
    const refreshStatsBtn = document.getElementById("refreshStatsBtn");
    const activityChartCanvas = document.getElementById("activityChartCanvas");

    // Token Management View
    const resyncTokenBtn = document.getElementById("resyncTokenBtn");
    const specSerial = document.getElementById("specSerial");
    const specFirmware = document.getElementById("specFirmware");
    const specDrift = document.getElementById("specDrift");
    const specBattery = document.getElementById("specBattery");
    const specLastSynced = document.getElementById("specLastSynced");

    // MFA Authentication View (Simulator)
    const generateBtn = document.getElementById("generateBtn");
    const generateBtnText = document.getElementById("generateBtnText");
    const verifyBtn = document.getElementById("verifyBtn");
    const verifyBtnText = document.getElementById("verifyBtnText");
    const verifyForm = document.getElementById("verifyForm");
    const quickFillBtn = document.getElementById("quickFillBtn");
    const resetBtn = document.getElementById("resetBtn");
    const otpDisplay = document.getElementById("otpDisplay");
    const lcdCaption = document.getElementById("lcdCaption");
    const otpInput = document.getElementById("otpInput");
    const inputCounter = document.getElementById("inputCounter");
    const timerSection = document.getElementById("timerSection");
    const timerCountdown = document.getElementById("timerCountdown");
    const progressBar = document.getElementById("progressBar");
    const tokenStateBadge = document.getElementById("tokenStateBadge");
    const verifyStateBadge = document.getElementById("verifyStateBadge");
    const navTokenBadge = document.getElementById("navTokenBadge");
    const resultCard = document.getElementById("resultCard");
    const resultIcon = document.getElementById("resultIcon");
    const resultTitle = document.getElementById("resultTitle");
    const resultMessage = document.getElementById("resultMessage");
    const resultSubtext = document.getElementById("resultSubtext");
    const specTtl = document.getElementById("specTtl");

    // Audit Logs View
    const fullLogStream = document.getElementById("fullLogStream");
    const logSearchInput = document.getElementById("logSearchInput");
    const logFilterPills = document.querySelectorAll(".filter-pill");
    const refreshAuditBtn = document.getElementById("refreshAuditBtn");
    const clearAuditLogsBtn = document.getElementById("clearAuditLogsBtn");
    const cwLogGroupDisplay = document.getElementById("cwLogGroupDisplay");

    // Settings View
    const settingsForm = document.getElementById("settingsForm");
    const settingTtl = document.getElementById("settingTtl");
    const settingRateLimit = document.getElementById("settingRateLimit");
    const settingMaxAttempts = document.getElementById("settingMaxAttempts");
    const settingDemoShowOtp = document.getElementById("settingDemoShowOtp");
    const settingsSaveStatus = document.getElementById("settingsSaveStatus");
    const settingsCwBadge = document.getElementById("settingsCwBadge");
    const settingsCwRegion = document.getElementById("settingsCwRegion");
    const settingsCwGroup = document.getElementById("settingsCwGroup");

    // Sidebar footer mini status
    const sideFlaskDot = document.getElementById("sideFlaskDot");
    const sideCwDot = document.getElementById("sideCwDot");
    const sideCwText = document.getElementById("sideCwText");

    // =========================================================================
    // Application State
    // =========================================================================

    let currentActiveView = "dashboard";
    let countdownInterval = null;
    let activeOtpValue = null;
    let totalTtlSeconds = 120;
    let expiresAtEpoch = 0;
    let cachedAuditEvents = [];
    let currentLogFilter = "ALL";

    const viewMetadata = {
        dashboard: {
            title: "Security Operations Dashboard",
            subtitle: "Real-time MFA possession-token telemetry and authentication metrics"
        },
        tokens: {
            title: "Hardware Token Inventory",
            subtitle: "Physical security key lifecycle, hardware calibration, and drift management"
        },
        auth: {
            title: "MFA Token Simulator Laboratory",
            subtitle: "Interactive possession factor verification, dynamic expiry, and anti-replay testing"
        },
        logs: {
            title: "Security Audit Telemetry",
            subtitle: "Zero-knowledge immutable event stream and CloudWatch synchronization"
        },
        settings: {
            title: "Simulator Operational Settings",
            subtitle: "Runtime policy tuning, TTL configuration, and AWS CloudWatch integration"
        }
    };

    // =========================================================================
    // View Routing / Switching
    // =========================================================================

    function switchView(viewName) {
        if (!viewMetadata[viewName]) return;
        currentActiveView = viewName;

        // Update nav items active state
        navItems.forEach(item => {
            if (item.getAttribute("data-view") === viewName) {
                item.classList.add("active");
            } else {
                item.classList.remove("active");
            }
        });

        // Update view panels
        viewPanels.forEach(panel => {
            if (panel.id === `view-${viewName}`) {
                panel.classList.add("active");
            } else {
                panel.classList.remove("active");
            }
        });

        // Update headers
        currentViewTitle.textContent = viewMetadata[viewName].title;
        currentViewSubtitle.textContent = viewMetadata[viewName].subtitle;

        // Close mobile drawer if open
        closeMobileSidebar();

        // Refresh view-specific data
        if (viewName === "dashboard") {
            fetchDashboardStats();
        } else if (viewName === "logs") {
            fetchAuditEvents();
        } else if (viewName === "settings") {
            fetchSettings();
        }
    }

    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetView = item.getAttribute("data-view");
            switchView(targetView);
        });
    });

    // Handle any buttons with data-nav-target
    document.querySelectorAll("[data-nav-target]").forEach(btn => {
        btn.addEventListener("click", () => {
            const target = btn.getAttribute("data-nav-target");
            switchView(target);
        });
    });

    // Mobile Sidebar Drawer
    function openMobileSidebar() {
        sidebar.classList.add("open");
        sidebarBackdrop.classList.add("open");
    }

    function closeMobileSidebar() {
        sidebar.classList.remove("open");
        sidebarBackdrop.classList.remove("open");
    }

    if (mobileMenuBtn) mobileMenuBtn.addEventListener("click", openMobileSidebar);
    if (sidebarBackdrop) sidebarBackdrop.addEventListener("click", closeMobileSidebar);

    // Live UTC Clock
    function updateClock() {
        if (!liveClock) return;
        const now = new Date();
        const utcStr = now.toISOString().substring(11, 19) + " UTC";
        liveClock.textContent = utcStr;
    }
    setInterval(updateClock, 1000);
    updateClock();

    // =========================================================================
    // Top Bar Quick Actions
    // =========================================================================

    if (quickGenerateTopBtn) {
        quickGenerateTopBtn.addEventListener("click", () => {
            switchView("auth");
            generateBtn.click();
        });
    }

    // =========================================================================
    // Health Check & CloudWatch Status
    // =========================================================================

    async function fetchSystemHealth() {
        try {
            const response = await fetch("/api/health");
            if (!response.ok) throw new Error("Health check unreachable");
            const data = await response.json();

            // CloudWatch Status
            const cw = data.cloudwatch || {};
            if (cw.enabled && cw.status === "connected") {
                cwStatusLabel.textContent = "Active";
                cwStatusDot.className = "status-dot dot-green";
                sideCwText.textContent = "CloudWatch: Active";
                sideCwDot.className = "status-dot dot-green";
                if (settingsCwBadge) {
                    settingsCwBadge.textContent = "Active (Connected)";
                    settingsCwBadge.className = "badge badge-success";
                }
            } else if (cw.status === "failed") {
                cwStatusLabel.textContent = "Error";
                cwStatusDot.className = "status-dot dot-amber";
                sideCwText.textContent = "CloudWatch: Error";
                sideCwDot.className = "status-dot dot-amber";
                if (settingsCwBadge) {
                    settingsCwBadge.textContent = "Connection Error";
                    settingsCwBadge.className = "badge badge-danger";
                }
            } else {
                cwStatusLabel.textContent = "Local";
                cwStatusDot.className = "status-dot dot-gray";
                sideCwText.textContent = "CloudWatch: Local";
                sideCwDot.className = "status-dot dot-gray";
                if (settingsCwBadge) {
                    settingsCwBadge.textContent = "Disabled (Local Logs)";
                    settingsCwBadge.className = "badge badge-neutral";
                }
            }

            // Sync configured TTL
            if (data.otp_ttl_seconds) {
                totalTtlSeconds = data.otp_ttl_seconds;
                if (specTtl) specTtl.textContent = `${totalTtlSeconds} Seconds`;
                if (kpiTtlSub) kpiTtlSub.textContent = `Configured TTL: ${totalTtlSeconds}s`;
            }

            if (sideFlaskDot) sideFlaskDot.className = "status-dot dot-green";
        } catch (err) {
            cwStatusLabel.textContent = "Offline";
            cwStatusDot.className = "status-dot dot-red";
            if (sideFlaskDot) sideFlaskDot.className = "status-dot dot-red";
        }
    }

    // =========================================================================
    // Dashboard Stats Telemetry & Chart
    // =========================================================================

    async function fetchDashboardStats() {
        try {
            const response = await fetch("/api/stats");
            if (!response.ok) return;
            const resData = await response.json();
            const data = resData.data || {};

            const metrics = data.metrics || {};
            const session = data.session_status || {};
            const token = data.token_info || {};
            const recent = data.recent_attempts || [];

            // Update KPI numbers
            if (kpiTotalGenerated) kpiTotalGenerated.textContent = metrics.total_generated || 0;
            if (kpiTotalVerified) kpiTotalVerified.textContent = metrics.total_verified || 0;
            if (kpiTotalFailed) kpiTotalFailed.textContent = metrics.total_failed || 0;
            if (kpiSuccessRate) kpiSuccessRate.textContent = `${metrics.success_rate_pct || 100}% Rate`;
            if (kpiRateLimitedBadge) {
                kpiRateLimitedBadge.textContent = `${metrics.total_rate_limited || 0} Rate-Limited`;
            }

            // Token Session State
            if (session.has_active_otp) {
                if (kpiTokenState) {
                    kpiTokenState.textContent = "Active";
                    kpiTokenState.style.color = "var(--accent-emerald)";
                }
                if (miniFobBadge) {
                    miniFobBadge.textContent = "Active";
                    miniFobBadge.className = "badge badge-success";
                }
                if (navTokenBadge) {
                    navTokenBadge.textContent = "Active";
                    navTokenBadge.style.background = "rgba(16, 185, 129, 0.2)";
                    navTokenBadge.style.color = "var(--accent-emerald)";
                }
            } else {
                if (kpiTokenState) {
                    kpiTokenState.textContent = "Standby";
                    kpiTokenState.style.color = "#ffffff";
                }
                if (miniFobBadge) {
                    miniFobBadge.textContent = "Standby";
                    miniFobBadge.className = "badge badge-neutral";
                }
                if (navTokenBadge) {
                    navTokenBadge.textContent = "Ready";
                    navTokenBadge.style.background = "rgba(100, 116, 139, 0.2)";
                    navTokenBadge.style.color = "var(--text-secondary)";
                }
            }

            // Token Info in Management View & Mini Fob
            if (token.serial_number) {
                if (miniSerial) miniSerial.textContent = token.serial_number;
                if (specSerial) specSerial.textContent = token.serial_number;
            }
            if (token.firmware && specFirmware) specFirmware.textContent = token.firmware;
            if (token.sync_drift) {
                if (miniDrift) miniDrift.textContent = token.sync_drift;
                if (specDrift) specDrift.textContent = token.sync_drift;
            }
            if (token.last_synced && specLastSynced) {
                specLastSynced.textContent = formatTimestamp(token.last_synced);
            }

            // Render Recent Attempts Table
            renderRecentAttempts(recent);

            // Render Activity Telemetry Chart Canvas
            renderActivityChart(metrics);
        } catch (err) {
            console.warn("Failed to load dashboard stats:", err);
        }
    }

    function renderRecentAttempts(attempts) {
        if (!recentAttemptsTableBody) return;
        if (!attempts || attempts.length === 0) {
            recentAttemptsTableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="table-empty">No authentication attempts recorded yet. Generate and verify an OTP to populate telemetry.</td>
                </tr>
            `;
            return;
        }

        recentAttemptsTableBody.innerHTML = "";
        attempts.forEach(item => {
            const tr = document.createElement("tr");

            let badgeClass = "badge-neutral";
            if (item.status === "SUCCESS") badgeClass = "badge-success";
            else if (item.status === "FAILED" || item.status === "LOCKOUT") badgeClass = "badge-danger";
            else if (item.status === "BLOCKED" || item.status === "EXPIRED" || item.status === "INCORRECT") badgeClass = "badge-warning";

            tr.innerHTML = `
                <td><code>${formatTimestamp(item.timestamp)}</code></td>
                <td>${escapeHtml(item.client_ip || "127.0.0.1")}</td>
                <td><strong>${escapeHtml(item.action)}</strong></td>
                <td><span class="badge ${badgeClass}">${escapeHtml(item.status)}</span></td>
                <td>${escapeHtml(item.details || "")}</td>
            `;
            recentAttemptsTableBody.appendChild(tr);
        });
    }

    // =========================================================================
    // HTML5 Canvas Activity Chart Engine (Zero CDN Dependency)
    // =========================================================================

    function renderActivityChart(metrics) {
        if (!activityChartCanvas) return;
        const ctx = activityChartCanvas.getContext("2d");
        const width = activityChartCanvas.width;
        const height = activityChartCanvas.height;

        // Clear canvas
        ctx.clearRect(0, 0, width, height);

        // Data buckets
        const verified = metrics.total_verified || 0;
        const failed = metrics.total_failed || 0;
        const expired = metrics.total_expired || 0;
        const rateLimited = metrics.total_rate_limited || 0;
        const total = Math.max(1, verified + failed + expired + rateLimited);

        // Chart dimensions
        const padding = { top: 25, bottom: 40, left: 50, right: 30 };
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;

        // Draw horizontal grid lines
        ctx.strokeStyle = "#1a253d";
        ctx.lineWidth = 1;
        ctx.font = "10px monospace";
        ctx.fillStyle = "#64748b";
        ctx.textAlign = "right";

        const gridLines = 4;
        const maxVal = Math.max(10, Math.ceil(Math.max(verified, failed, expired, rateLimited) * 1.3));

        for (let i = 0; i <= gridLines; i++) {
            const y = padding.top + (chartHeight / gridLines) * i;
            const val = Math.round(maxVal - (maxVal / gridLines) * i);

            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(width - padding.right, y);
            ctx.stroke();

            ctx.fillText(val, padding.left - 8, y + 3);
        }

        // Draw Bars
        const categories = [
            { label: "Verified", value: verified, color: "#10b981", glow: "rgba(16, 185, 129, 0.4)" },
            { label: "Incorrect", value: failed, color: "#f43f5e", glow: "rgba(244, 63, 94, 0.4)" },
            { label: "Expired", value: expired, color: "#f59e0b", glow: "rgba(245, 158, 11, 0.4)" },
            { label: "Rate-Limited", value: rateLimited, color: "#8b5cf6", glow: "rgba(139, 92, 246, 0.4)" }
        ];

        const barWidth = 46;
        const spacing = chartWidth / categories.length;

        categories.forEach((cat, idx) => {
            const x = padding.left + spacing * idx + (spacing - barWidth) / 2;
            const barH = (cat.value / maxVal) * chartHeight;
            const y = padding.top + chartHeight - barH;

            // Bar background slot
            ctx.fillStyle = "rgba(255, 255, 255, 0.02)";
            ctx.fillRect(x, padding.top, barWidth, chartHeight);

            // Bar fill
            ctx.shadowColor = cat.glow;
            ctx.shadowBlur = 8;
            ctx.fillStyle = cat.color;
            ctx.fillRect(x, y, barWidth, Math.max(2, barH));
            ctx.shadowBlur = 0; // reset shadow

            // Value label on top of bar
            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 11px monospace";
            ctx.textAlign = "center";
            ctx.fillText(cat.value, x + barWidth / 2, y - 6);

            // Category label below
            ctx.fillStyle = "#94a3b8";
            ctx.font = "10px -apple-system, sans-serif";
            ctx.fillText(cat.label, x + barWidth / 2, height - padding.bottom + 18);
        });
    }

    if (refreshStatsBtn) {
        refreshStatsBtn.addEventListener("click", fetchDashboardStats);
    }

    // =========================================================================
    // Token Management Controls
    // =========================================================================

    if (resyncTokenBtn) {
        resyncTokenBtn.addEventListener("click", async () => {
            resyncTokenBtn.disabled = true;
            try {
                const res = await fetch("/api/token/resync", { method: "POST" });
                const data = await res.json();
                if (data.success) {
                    if (specDrift) specDrift.textContent = "+0.004s (Calibrated)";
                    if (miniDrift) miniDrift.textContent = "+0.004s (Calibrated)";
                    if (specLastSynced) specLastSynced.textContent = formatTimestamp(data.last_synced);
                    fetchDashboardStats();
                }
            } catch (err) {
                // Ignore network error
            } finally {
                resyncTokenBtn.disabled = false;
            }
        });
    }

    // =========================================================================
    // Interactive MFA Token Simulator Engine
    // =========================================================================

    function startTimer(expiresAt) {
        clearInterval(countdownInterval);
        expiresAtEpoch = expiresAt;
        if (timerSection) timerSection.style.display = "block";

        updateTimerDisplay();
        countdownInterval = setInterval(updateTimerDisplay, 500);
    }

    function updateTimerDisplay() {
        const nowEpoch = Date.now() / 1000;
        const remaining = Math.max(0, Math.floor(expiresAtEpoch - nowEpoch));

        const minutes = Math.floor(remaining / 60);
        const seconds = remaining % 60;
        const timeFormatted = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;

        if (timerCountdown) timerCountdown.textContent = timeFormatted;
        if (kpiCountdownText) kpiCountdownText.textContent = timeFormatted;

        const percentage = Math.max(0, Math.min(100, (remaining / totalTtlSeconds) * 100));
        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
            if (percentage > 50) {
                progressBar.style.background = "linear-gradient(90deg, #06b6d4, #10b981)";
                timerCountdown.style.color = "#10b981";
            } else if (percentage > 20) {
                progressBar.style.background = "linear-gradient(90deg, #f59e0b, #d97706)";
                timerCountdown.style.color = "#f59e0b";
            } else {
                progressBar.style.background = "linear-gradient(90deg, #f43f5e, #be123c)";
                timerCountdown.style.color = "#f43f5e";
            }
        }

        if (remaining <= 0) {
            handleOtpExpired();
        }
    }

    function stopTimer() {
        clearInterval(countdownInterval);
        countdownInterval = null;
        if (timerSection) timerSection.style.display = "none";
        if (kpiCountdownText) kpiCountdownText.textContent = "--:--";
    }

    function handleOtpExpired() {
        clearInterval(countdownInterval);
        countdownInterval = null;

        if (otpDisplay) {
            otpDisplay.textContent = "EXPIRED";
            otpDisplay.style.color = "#f43f5e";
            otpDisplay.style.textShadow = "0 0 12px rgba(244, 63, 94, 0.6)";
            lcdCaption.textContent = "Token Lifetime Ended";
        }

        if (miniLcdOtp) {
            miniLcdOtp.textContent = "EXPRD";
            miniLcdOtp.style.color = "#f43f5e";
            miniLcdSub.textContent = "Expired";
        }

        if (tokenStateBadge) {
            tokenStateBadge.textContent = "Expired";
            tokenStateBadge.className = "badge badge-danger";
        }
        if (miniFobBadge) {
            miniFobBadge.textContent = "Expired";
            miniFobBadge.className = "badge badge-danger";
        }
        if (kpiTokenState) {
            kpiTokenState.textContent = "Expired";
            kpiTokenState.style.color = "var(--accent-rose)";
        }

        if (quickFillBtn) quickFillBtn.style.display = "none";
        activeOtpValue = null;

        showResult(
            "warning",
            "OTP Expired",
            "The One-Time Password has exceeded its validity window and has been invalidated by the security policy.",
            "Generate a new OTP to continue authentication."
        );

        fetchDashboardStats();
    }

    // Generate Button Click
    if (generateBtn) {
        generateBtn.addEventListener("click", async () => {
            generateBtn.disabled = true;
            generateBtnText.textContent = "Generating...";

            try {
                const response = await fetch("/api/generate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" }
                });

                const data = await response.json();

                if (response.status === 429) {
                    showResult(
                        "warning",
                        "Rate Limit Cooldown Active",
                        data.message || "Please wait before generating another OTP.",
                        "Anti-flooding protection policy."
                    );
                    fetchDashboardStats();
                    return;
                }

                if (!response.ok || !data.success) {
                    throw new Error(data.message || "Failed to generate OTP.");
                }

                activeOtpValue = data.otp;
                totalTtlSeconds = data.ttl_seconds || 120;

                if (data.otp) {
                    otpDisplay.textContent = data.otp;
                    otpDisplay.style.color = "var(--lcd-text)";
                    otpDisplay.style.textShadow = "0 0 12px var(--lcd-text), 0 0 25px rgba(0, 240, 255, 0.5)";
                    lcdCaption.textContent = "Active Security Token";

                    if (miniLcdOtp) {
                        miniLcdOtp.textContent = data.otp;
                        miniLcdOtp.style.color = "var(--lcd-text)";
                        miniLcdSub.textContent = "Active Token";
                    }

                    if (quickFillBtn) quickFillBtn.style.display = "inline-flex";
                } else {
                    otpDisplay.textContent = "● ● ● ● ● ●";
                    lcdCaption.textContent = "OTP Dispatched Out-of-Band";
                    if (miniLcdOtp) miniLcdOtp.textContent = "● ● ● ● ● ●";
                    if (quickFillBtn) quickFillBtn.style.display = "none";
                }

                tokenStateBadge.textContent = "Active";
                tokenStateBadge.className = "badge badge-success";
                verifyStateBadge.textContent = "Awaiting Verification";
                verifyStateBadge.className = "badge badge-blue";

                startTimer(data.expires_at);
                hideResult();
                otpInput.value = "";
                updateInputCounter();
                otpInput.focus();

                fetchDashboardStats();
            } catch (err) {
                showResult(
                    "error",
                    "Generation Error",
                    err.message || "Failed to communicate with backend.",
                    "Verify Flask backend is running on port 5000."
                );
            } finally {
                generateBtn.disabled = false;
                generateBtnText.textContent = "Generate New OTP";
            }
        });
    }

    // Quick Fill helper
    if (quickFillBtn) {
        quickFillBtn.addEventListener("click", () => {
            if (activeOtpValue) {
                otpInput.value = activeOtpValue;
                updateInputCounter();
                otpInput.focus();
            }
        });
    }

    // Input validation
    if (otpInput) {
        otpInput.addEventListener("input", () => {
            otpInput.value = otpInput.value.replace(/\D/g, "").slice(0, 6);
            updateInputCounter();
        });
    }

    function updateInputCounter() {
        if (!otpInput || !inputCounter) return;
        const len = otpInput.value.length;
        inputCounter.textContent = `${len} / 6`;
        if (verifyBtn) verifyBtn.disabled = len !== 6;
    }

    // Form submit / verify
    if (verifyForm) {
        verifyForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const enteredOtp = otpInput.value.trim();
            if (enteredOtp.length !== 6) return;

            verifyBtn.disabled = true;
            verifyBtnText.textContent = "Verifying...";

            try {
                const response = await fetch("/api/verify", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ otp: enteredOtp })
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    stopTimer();

                    otpDisplay.textContent = "VALID";
                    otpDisplay.style.color = "#10b981";
                    otpDisplay.style.textShadow = "0 0 15px rgba(16, 185, 129, 0.7)";
                    lcdCaption.textContent = "Token Consumed (Single-Use)";

                    if (miniLcdOtp) {
                        miniLcdOtp.textContent = "VALID";
                        miniLcdOtp.style.color = "#10b981";
                        miniLcdSub.textContent = "Consumed";
                    }

                    tokenStateBadge.textContent = "Consumed";
                    tokenStateBadge.className = "badge badge-neutral";
                    verifyStateBadge.textContent = "Authenticated";
                    verifyStateBadge.className = "badge badge-success";

                    if (quickFillBtn) quickFillBtn.style.display = "none";
                    activeOtpValue = null;

                    showResult(
                        "success",
                        "Authentication Successful!",
                        data.message || "OTP verified successfully. The token has been invalidated to prevent replay attacks.",
                        "Single-Use Security Policy: Resubmitting this same OTP will be rejected."
                    );

                    otpInput.value = "";
                    updateInputCounter();
                } else {
                    verifyStateBadge.textContent = "Rejected";
                    verifyStateBadge.className = "badge badge-danger";

                    showResult(
                        "error",
                        "Verification Rejected",
                        data.message || "The submitted OTP is invalid.",
                        "Security audit log recorded on server."
                    );

                    if (data.error === "OTP_EXPIRED") {
                        handleOtpExpired();
                    } else if (data.error === "MAX_ATTEMPTS_EXCEEDED") {
                        stopTimer();
                        otpDisplay.textContent = "LOCKED";
                        otpDisplay.style.color = "#f43f5e";
                        tokenStateBadge.textContent = "Locked Out";
                        tokenStateBadge.className = "badge badge-danger";
                        if (quickFillBtn) quickFillBtn.style.display = "none";
                    }
                }

                fetchDashboardStats();
            } catch (err) {
                showResult(
                    "error",
                    "Connection Error",
                    "Failed to communicate with authentication server.",
                    "Check server logs."
                );
            } finally {
                verifyBtnText.textContent = "Verify OTP";
                updateInputCounter();
            }
        });
    }

    // Reset button
    if (resetBtn) {
        resetBtn.addEventListener("click", async () => {
            try {
                await fetch("/api/reset", { method: "POST" });
            } catch (e) {}

            stopTimer();
            activeOtpValue = null;

            otpDisplay.textContent = "------";
            otpDisplay.style.color = "var(--lcd-text)";
            otpDisplay.style.textShadow = "0 0 12px var(--lcd-text), 0 0 25px rgba(0, 240, 255, 0.5)";
            lcdCaption.textContent = "Press 'Generate OTP'";

            if (miniLcdOtp) {
                miniLcdOtp.textContent = "------";
                miniLcdOtp.style.color = "var(--lcd-text)";
                miniLcdSub.textContent = "Awaiting generation";
            }

            tokenStateBadge.textContent = "Standby";
            tokenStateBadge.className = "badge badge-neutral";
            verifyStateBadge.textContent = "Awaiting Input";
            verifyStateBadge.className = "badge badge-neutral";

            if (quickFillBtn) quickFillBtn.style.display = "none";
            otpInput.value = "";
            updateInputCounter();
            hideResult();

            fetchDashboardStats();
        });
    }

    function showResult(type, title, message, subtext = "") {
        if (!resultCard) return;
        resultCard.style.display = "flex";
        resultCard.className = `result-card result-card-${type}`;

        if (type === "success") resultIcon.textContent = "✓";
        else if (type === "error") resultIcon.textContent = "✕";
        else resultIcon.textContent = "⚠";

        resultTitle.textContent = title;
        resultMessage.textContent = message;
        resultSubtext.textContent = subtext;
    }

    function hideResult() {
        if (resultCard) resultCard.style.display = "none";
    }

    // =========================================================================
    // Audit Telemetry View & Filtering
    // =========================================================================

    async function fetchAuditEvents() {
        try {
            const response = await fetch("/api/events?limit=50");
            if (!response.ok) return;
            const data = await response.json();
            cachedAuditEvents = data.events || [];
            renderFilteredAuditLogs();
        } catch (err) {
            console.warn("Failed to fetch audit events:", err);
        }
    }

    function renderFilteredAuditLogs() {
        if (!fullLogStream) return;
        const searchTerm = (logSearchInput ? logSearchInput.value : "").toLowerCase().trim();

        const filtered = cachedAuditEvents.filter(ev => {
            // Severity filter
            if (currentLogFilter !== "ALL") {
                const evStatus = (ev.status || "").toUpperCase();
                if (currentLogFilter === "SUCCESS" && evStatus !== "SUCCESS") return false;
                if (currentLogFilter === "WARNING" && evStatus !== "WARNING") return false;
                if (currentLogFilter === "INFO" && evStatus !== "INFO") return false;
            }

            // Keyword search
            if (searchTerm) {
                const combined = `${ev.event_type} ${ev.message} ${ev.client_ip}`.toLowerCase();
                if (!combined.includes(searchTerm)) return false;
            }

            return true;
        });

        if (filtered.length === 0) {
            fullLogStream.innerHTML = `
                <div class="log-entry log-entry-info">
                    <span class="log-time">[Filter]</span>
                    <span class="log-tag tag-info">EMPTY</span>
                    <span class="log-msg">No log events match the current filter criteria.</span>
                </div>
            `;
            return;
        }

        fullLogStream.innerHTML = "";
        filtered.forEach(ev => {
            const entry = document.createElement("div");
            entry.className = "log-entry";
            const tagClass = getTagClass(ev.status, ev.event_type);
            const timeStr = formatTimestamp(ev.timestamp);

            entry.innerHTML = `
                <span class="log-time">[${timeStr}]</span>
                <span class="log-tag ${tagClass}">${escapeHtml(ev.event_type)}</span>
                <span class="log-msg">${escapeHtml(ev.message)}</span>
            `;
            fullLogStream.appendChild(entry);
        });
    }

    // Filter pills
    logFilterPills.forEach(pill => {
        pill.addEventListener("click", () => {
            logFilterPills.forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            currentLogFilter = pill.getAttribute("data-filter") || "ALL";
            renderFilteredAuditLogs();
        });
    });

    if (logSearchInput) {
        logSearchInput.addEventListener("input", renderFilteredAuditLogs);
    }

    if (refreshAuditBtn) {
        refreshAuditBtn.addEventListener("click", fetchAuditEvents);
    }

    if (clearAuditLogsBtn) {
        clearAuditLogsBtn.addEventListener("click", async () => {
            try {
                await fetch("/api/logs/clear", { method: "POST" });
                fetchAuditEvents();
                fetchDashboardStats();
            } catch (err) {}
        });
    }

    // =========================================================================
    // Settings Management
    // =========================================================================

    async function fetchSettings() {
        try {
            const res = await fetch("/api/settings");
            if (!res.ok) return;
            const data = await res.json();
            const s = data.settings || {};

            if (settingTtl && s.otp_ttl_seconds) settingTtl.value = s.otp_ttl_seconds;
            if (settingRateLimit && s.rate_limit_seconds !== undefined) settingRateLimit.value = s.rate_limit_seconds;
            if (settingMaxAttempts && s.max_attempts) settingMaxAttempts.value = s.max_attempts;
            if (settingDemoShowOtp && s.demo_show_otp !== undefined) settingDemoShowOtp.checked = s.demo_show_otp;

            if (settingsCwGroup && s.cloudwatch_log_group) settingsCwGroup.textContent = s.cloudwatch_log_group;
            if (settingsCwRegion && s.aws_default_region) settingsCwRegion.textContent = s.aws_default_region;
        } catch (err) {
            console.warn("Failed to load settings:", err);
        }
    }

    if (settingsForm) {
        settingsForm.addEventListener("submit", async () => {
            const payload = {
                otp_ttl_seconds: parseInt(settingTtl.value, 10),
                rate_limit_seconds: parseInt(settingRateLimit.value, 10),
                max_attempts: parseInt(settingMaxAttempts.value, 10),
                demo_show_otp: settingDemoShowOtp.checked
            };

            try {
                const res = await fetch("/api/settings", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                if (data.success) {
                    settingsSaveStatus.textContent = "✓ Policies applied successfully.";
                    settingsSaveStatus.style.color = "var(--accent-emerald)";
                    totalTtlSeconds = payload.otp_ttl_seconds;
                    if (specTtl) specTtl.textContent = `${totalTtlSeconds} Seconds`;
                    setTimeout(() => { settingsSaveStatus.textContent = ""; }, 3000);
                    fetchDashboardStats();
                }
            } catch (err) {
                settingsSaveStatus.textContent = "✕ Failed to save settings.";
                settingsSaveStatus.style.color = "var(--accent-rose)";
            }
        });
    }

    // =========================================================================
    // Utilities
    // =========================================================================

    function getTagClass(status, eventType) {
        if (status === "SUCCESS" || eventType === "OTP_VERIFY_SUCCESS") return "tag-success";
        if (status === "WARNING" || eventType.includes("FAILED") || eventType.includes("EXPIRED") || eventType.includes("RATE")) return "tag-warning";
        if (status === "ERROR") return "tag-error";
        return "tag-info";
    }

    function formatTimestamp(isoStr) {
        if (!isoStr) return "--:--:--";
        try {
            const d = new Date(isoStr);
            return d.toTimeString().split(" ")[0];
        } catch {
            return isoStr.substring(11, 19);
        }
    }

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    // =========================================================================
    // Initial Load & Polling Intervals
    // =========================================================================

    fetchSystemHealth();
    fetchDashboardStats();
    fetchAuditEvents();

    // Telemetry polling: every 8 seconds
    setInterval(() => {
        if (currentActiveView === "dashboard") {
            fetchDashboardStats();
        } else if (currentActiveView === "logs") {
            fetchAuditEvents();
        }
    }, 8000);

    // Health check polling: every 30 seconds
    setInterval(fetchSystemHealth, 30000);
});
