# GitHub API Rate Limit Handling Guide

## Problem
GitHub API has strict rate limits that can prevent fetching repositories:
- **Without token**: 60 requests/hour
- **With token**: 5000 requests/hour
- **Enterprise**: Higher limits available

## Current Status

Your `.env` file already contains a `GITHUB_TOKEN`. The token is being used and should provide you with 5000 requests/hour.

### How to Check Rate Limit Status
The Constructor page now displays your current GitHub API rate limit in the sidebar:
- ✅ Green = You're good (>10 requests remaining)
- ⚠️ Yellow = Running low (<10 requests remaining)

## Solutions if You Hit Rate Limit

### Solution 1: Generate a New GitHub Token (Recommended)
GitHub tokens can expire or have scope restrictions. Generate a fresh one:

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a name: `research-paper-assistant`
4. Select scopes:
   - ✅ `repo` (full control of private repositories)
   - ✅ `public_repo` (access public repositories)
5. Click "Generate token"
6. Copy the token (shown only once!)
7. Update `.env`:
   ```
   GITHUB_TOKEN=github_pat_YOUR_NEW_TOKEN_HERE
   ```
8. Restart the Streamlit app

### Solution 2: Reduce API Calls
Modify the Constructor to fetch fewer files:

**Current:** `max_files=40`
**Suggested:** `max_files=20` or `max_files=10`

File: `pages/Constructor.py` - Change this line:
```python
repo_data = fetch_repo(owner, repo, max_files=20)  # Reduced from 40
```

### Solution 3: Wait for Rate Limit Reset
If you hit the limit:
- Without token: Reset in 1 hour
- With token: Reset in 1 hour
- The app now shows the exact reset time!

### Solution 4: Use GitHub GraphQL API
More efficient than REST API:
- Fewer requests needed
- Better for bulk operations
- Would require code refactoring

## Monitoring

### Check Rate Limit Status Manually
```bash
# Without token (60 req/hour)
curl -i https://api.github.com/rate_limit

# With token
curl -i -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit
```

### In the App
- The sidebar now shows: `✅ API Remaining: 4950/5000`
- If low, it shows: `⚠️ API Low: 5/5000` and reset time

## Error Messages & Solutions

### "GitHub API rate limit exceeded"
**Cause:** All 5000 (or 60) requests used
**Fix:** Wait for reset time OR generate new token with higher limits

### "GitHub API request timed out"
**Cause:** GitHub servers slow/network issue
**Fix:** Try again in a few moments

### "Repository not found"
**Cause:** Wrong owner/repo name or private repo without access
**Fix:** Check URL format and repository privacy settings

### "Repository branch 'main' not found"
**Cause:** Default branch is not 'main' (could be 'master', 'develop', etc.)
**Fix:** App will try the repo's actual default branch (already handles this)

## Rate Limit Optimization in Code

### What Changed:
1. **Better error handling** - Distinguishes between rate limit and other errors
2. **Pre-flight check** - Checks rate limit BEFORE starting processing
3. **Graceful degradation** - Skips individual files if they timeout
4. **Clear messaging** - Shows exact reset time to users

### Code Implementation:
```python
# Check rate limit before starting
rate_limit = _check_rate_limit(headers)
if rate_limit and rate_limit["status"] == "low":
    raise RuntimeError(f"Rate limit low, resets at {rate_limit['reset_time']}")

# Handle 403 errors more intelligently
if r.status_code == 403:
    if r.headers.get("X-RateLimit-Remaining") == "0":
        raise RuntimeError("Rate limit exceeded")
```

## Quick Fix Checklist

- [ ] Check token in `.env` - `GITHUB_TOKEN=github_pat_...`
- [ ] Token not expired - Go to https://github.com/settings/tokens
- [ ] Token has `repo` scope
- [ ] Not using token for 100+ repos in one session
- [ ] Restart Streamlit app after changing `.env`

## Recommended Token Settings

When creating a new GitHub Personal Access Token:
```
Name: research-paper-assistant
Expiration: 90 days (recommended for security)
Scopes: 
  ✅ repo (includes public_repo)
  ✅ read:user
  ✅ read:org
```

## For Production Use

If deploying this app publicly:

1. **Use GitHub OAuth** instead of personal tokens
2. **Implement token rotation** every 90 days
3. **Cache repository data** - Don't re-fetch same repo
4. **Use GitHub GraphQL** - More efficient queries
5. **Set up rate limit queue** - Queue requests if close to limit
6. **Monitor usage** - Log API calls for analytics

## Testing Rate Limit Handling

To test the error messages without hitting real limit:
```python
# In github_loader.py, temporarily change:
def _check_rate_limit(headers):
    return {
        "status": "low",
        "remaining": 3,
        "limit": 5000,
        "reset_time": "2026-02-03 15:30:00"
    }
```

---

**Last Updated:** February 3, 2026
**API Improvements:** Enhanced error handling, rate limit checking, graceful degradation
