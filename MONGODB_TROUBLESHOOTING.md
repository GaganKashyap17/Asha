# MongoDB Connection Troubleshooting Guide

## Current Issue: ServerSelectionTimeoutError

This error means the application cannot reach your MongoDB Atlas server. Here are the solutions:

## Solution 1: Whitelist Your IP Address (Most Common Fix)

1. **Go to MongoDB Atlas**: https://cloud.mongodb.com/
2. **Login** with your credentials
3. **Navigate to your cluster** (hasha.nmfl0a1)
4. Click **"Network Access"** in the left sidebar
5. Click **"Add IP Address"**
6. Choose one of:
   - **Add Current IP Address** (for your current location)
   - **Allow Access from Anywhere** (0.0.0.0/0) - easier for development

**Important**: If you're on a dynamic IP or move locations, you'll need to update this.

## Solution 2: Check Your Firewall

### Windows Firewall
1. Open **Windows Security** → **Firewall & network protection**
2. Click **"Allow an app through firewall"**
3. Ensure **Python** is allowed for both Private and Public networks

### Antivirus Software
- Check if your antivirus is blocking outbound connections to MongoDB
- Temporarily disable to test

## Solution 3: Verify Credentials

Your current connection string:
```
mongodb+srv://727724eucs185_db_user:nxD7DwBKpL8KgG9H@hasha.nmfl0a1.mongodb.net/Hasha
```

1. **Check MongoDB Atlas**:
   - Database Access → Users
   - Verify user `727724eucs185_db_user` exists
   - Verify it has read/write permissions

2. **Check Database Name**:
   - Browse Collections → Verify database `Hasha` exists
   - If different, update `MONGODB_DB_NAME` in `.env`

## Solution 4: Test DNS Resolution

MongoDB Atlas uses SRV records. Ensure `dnspython` is installed:

```bash
cd backend
venv\Scripts\pip install dnspython==2.7.0
```

## Solution 5: Test Connection Manually

Run this test script:

```bash
cd backend
venv\Scripts\python quick_mongo_test.py
```

## Solution 6: Check MongoDB Atlas Cluster Status

1. Go to MongoDB Atlas dashboard
2. Check if your cluster is **Active** and not **Paused**
3. If paused, click **Resume** button

## Solution 7: Network Connectivity

Test basic connectivity:

```bash
ping hasha.nmfl0a1.mongodb.net
```

If this fails, you have a network/DNS issue.

## Solution 8: Use Different Connection String Format

If SRV record fails, try standard connection string:

1. In MongoDB Atlas, click **Connect**
2. Choose **"Connect your application"**
3. Copy the **standard connection string** (not SRV)
4. Update `.env` file

## Testing the Fix

After making changes:

1. Restart the backend server
2. Check `backend/asha_voice.log` for:
   - `✓ MongoDB Atlas connected successfully` (SUCCESS)
   - `ServerSelectionTimeoutError` (STILL FAILING)

## Fallback: Use Demo Mode

If you cannot fix the connection and want to continue development:

In `.env`, change:
```env
MONGODB_URI=mongodb+srv://username:password@demo.mongodb.net/asha_voice
```

This will use in-memory storage (data lost on restart).

## Quick Checklist

- [ ] IP Address whitelisted in MongoDB Atlas (0.0.0.0/0)
- [ ] MongoDB Atlas cluster is Active (not Paused)
- [ ] Windows Firewall allows Python
- [ ] dnspython installed (`pip list | findstr dnspython`)
- [ ] Credentials are correct in MongoDB Atlas
- [ ] Database name "Hasha" exists
- [ ] Internet connection is working

## Most Likely Solution

**95% of cases**: Your IP address is not whitelisted in MongoDB Atlas.

→ Go to Network Access → Add IP Address → Allow Access from Anywhere (0.0.0.0/0)
