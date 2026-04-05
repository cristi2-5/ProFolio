# Cron Job Setup — Auto-Apply Job Scanner

This document provides instructions for setting up automated daily job scanning using cron on Linux/macOS systems.

## Overview

The job scanner runs daily to discover new job postings for all users with configured preferences. It integrates with the Adzuna API and creates user-job associations with compatibility scores.

## Prerequisites

1. **Production Environment Setup**:
   ```bash
   # Ensure application is deployed and database is accessible
   cd /path/to/autoapply/backend
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Environment Variables** (in production `.env`):
   ```env
   DATABASE_URL=postgresql+asyncpg://autoapply:password@localhost:5432/autoapply_db
   ADZUNA_APP_ID=your_adzuna_app_id
   ADZUNA_APP_KEY=your_adzuna_app_key
   OPENAI_API_KEY=sk-your-openai-key
   ```

3. **Log Directory**:
   ```bash
   sudo mkdir -p /var/log/autoapply
   sudo chown www-data:www-data /var/log/autoapply
   sudo chmod 755 /var/log/autoapply
   ```

## Cron Configuration

### 1. Edit Crontab

```bash
# Edit crontab for the application user (e.g., www-data)
sudo crontab -u www-data -e
```

### 2. Add Daily Job Scanner

```cron
# Auto-Apply Job Scanner — Runs daily at 6:00 AM UTC
0 6 * * * /path/to/autoapply/backend/venv/bin/python -m app.scripts.daily_job_scan >> /var/log/autoapply/cron.log 2>&1

# Alternative: Run every 12 hours (6 AM and 6 PM UTC)
0 6,18 * * * /path/to/autoapply/backend/venv/bin/python -m app.scripts.daily_job_scan >> /var/log/autoapply/cron.log 2>&1

# Development/Testing: Run every hour (remove in production)
0 * * * * /path/to/autoapply/backend/venv/bin/python -m app.scripts.daily_job_scan >> /var/log/autoapply/cron.log 2>&1
```

### 3. Verify Cron Setup

```bash
# List current cron jobs
sudo crontab -u www-data -l

# Check cron service status
sudo systemctl status cron

# Monitor real-time logs
tail -f /var/log/autoapply/cron.log
tail -f /var/log/autoapply/job_scanner.log
```

## Manual Testing

### Test Single User Scan

```bash
cd /path/to/autoapply/backend
source venv/bin/activate

# Scan specific user (replace with actual UUID)
python -m app.scripts.daily_job_scan --user 12345678-1234-1234-1234-123456789abc --verbose
```

### Test Full Daily Scan

```bash
# Run complete scan (all users)
python -m app.scripts.daily_job_scan --verbose
```

### Expected Output

```
2024-01-15 06:00:01,123 - INFO - Starting daily job scan...
2024-01-15 06:00:02,456 - INFO - Starting job scan for all users
2024-01-15 06:00:03,789 - INFO - Found 25 jobs from Adzuna for user 12345...
2024-01-15 06:00:04,012 - INFO - Created 8 job matches for user 12345...
2024-01-15 06:00:15,345 - INFO - Scan complete: 47 total jobs, 5 successful, 0 failed
2024-01-15 06:00:15,567 - INFO - Daily job scan completed successfully: 47 jobs in 14.44s
Scan result: {'status': 'success', 'total_jobs_discovered': 47, 'duration_seconds': 14.44, ...}
```

## Monitoring & Maintenance

### 1. Log Rotation

Create `/etc/logrotate.d/autoapply`:

```
/var/log/autoapply/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload rsyslog > /dev/null 2>&1 || true
    endscript
}
```

### 2. Health Checks

```bash
# Check if cron jobs are running
ps aux | grep daily_job_scan

# Verify recent scan activity (last 24 hours)
find /var/log/autoapply -name "*.log" -mtime -1 -exec grep -l "Daily job scan completed" {} \;

# Check Adzuna API status
python -c "
from app.clients.adzuna import adzuna_client
import asyncio
result = asyncio.run(adzuna_client.health_check())
print('Adzuna API:', 'OK' if result else 'FAILED')
"
```

### 3. Error Handling

Common issues and solutions:

```bash
# Permission issues
sudo chown -R www-data:www-data /path/to/autoapply
sudo chmod +x /path/to/autoapply/backend/venv/bin/python

# Database connection issues
sudo -u www-data psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"

# API rate limiting
grep -i "rate limit" /var/log/autoapply/job_scanner.log
```

## Performance Tuning

### 1. Adzuna API Limits

- **Free Tier**: 5,000 requests/month
- **Rate Limit**: ~1 request/second
- **Optimization**: Limit to 50 jobs per user per scan

### 2. Database Performance

```sql
-- Monitor job scanner database activity
SELECT COUNT(*) as total_jobs FROM scraped_jobs WHERE scraped_at > NOW() - INTERVAL '7 days';
SELECT COUNT(*) as total_matches FROM user_jobs WHERE created_at > NOW() - INTERVAL '7 days';

-- Clean up old jobs (monthly maintenance)
DELETE FROM scraped_jobs WHERE scraped_at < NOW() - INTERVAL '90 days';
```

### 3. Scaling Considerations

- **Multiple Servers**: Use distributed locking to prevent duplicate scans
- **Large User Base**: Implement batch processing with user pagination
- **API Quotas**: Add circuit breakers and exponential backoff

## Security Notes

1. **API Keys**: Store in environment variables, never in cron commands
2. **File Permissions**: Ensure log files are not world-readable
3. **Database Access**: Use dedicated scanner user with minimal privileges
4. **Monitoring**: Set up alerts for scan failures or API quota exhaustion

## Troubleshooting

### Common Exit Codes

- `0`: Success (jobs found or no jobs available)
- `1`: Scan failed (check logs for details)
- `2`: Invalid command-line arguments

### Debug Commands

```bash
# Enable verbose logging
python -m app.scripts.daily_job_scan --verbose

# Check environment variables
env | grep -E "(DATABASE_URL|ADZUNA_|OPENAI_)"

# Test database connectivity
python -c "from app.database import get_async_session; print('DB OK')"

# Test Adzuna API
python -c "from app.clients.adzuna import adzuna_client; import asyncio; print(asyncio.run(adzuna_client.health_check()))"
```

### Log Analysis

```bash
# Count successful scans in last 7 days
grep -c "Daily job scan completed successfully" /var/log/autoapply/job_scanner.log

# Find API errors
grep -i "error\|fail" /var/log/autoapply/job_scanner.log | tail -10

# Monitor job discovery trends
grep "jobs discovered" /var/log/autoapply/job_scanner.log | tail -20
```