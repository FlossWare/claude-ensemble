# Quick Dashboard Import Guide

## 📊 **Import Document Ingestion API Dashboard**

### **Step-by-Step (5 minutes):**

1. **Open Grafana in browser:**
   ```
   http://aio-01:3000
   ```

2. **Login**
   - Username: `admin`
   - Password: (try `admin`, or ask for the actual password)

3. **Import Dashboard:**
   - Look for **"+"** icon on the left sidebar
   - Click **"+"** → **"Import"**
   - Click **"Upload JSON file"** button
   - Navigate to:
     ```
     ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/grafana/document-ingestion-dashboard.json
     ```
   - Click **"Open"**
   - Click **"Load"**
   - Click **"Import"**

4. **Dashboard should now appear!**

---

## 🔧 **Alternative: Create Data Source First**

If import fails saying "data source not found":

1. **Add Prometheus data source:**
   - Click **gear icon** (⚙️) → **"Data sources"**
   - Click **"Add data source"**
   - Select **"Prometheus"**
   - Set URL: `http://aio-01:8010/metrics`
   - Click **"Save & test"**

2. **Then try import again**

---

## 🎯 **What You'll See:**

Once imported, the dashboard shows:

- **API Request Rate** - Live QPS (14.3 currently)
- **Response Time** - P50/P95/P99 latency (246ms P99)
- **Error Rate** - 0.0%
- **Uptime** - 4+ days
- **Database Connections** - Pool health
- **Memory Usage** - Resource tracking
- **Total Requests** - Volume metrics
- **Current QPS** - Real-time gauge
- **Endpoint Performance** - Per-endpoint breakdown

All panels refresh every 5 seconds!

---

## ⚠️ **Troubleshooting:**

### **Can't login?**
Try resetting password:
```bash
ssh aio-01 'sudo grafana-cli admin reset-admin-password admin'
```

### **Dashboard shows "No data"?**
The Document Ingestion API needs to be exposing Prometheus metrics:
```bash
curl http://aio-01:8010/metrics | head -20
```

Should show metrics like:
- `http_requests_total`
- `http_request_duration_seconds`
- `process_resident_memory_bytes`

### **Dashboard JSON file not found?**
Full path:
```bash
ls -lh ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/grafana/document-ingestion-dashboard.json
```

---

## 📁 **File Location:**

Dashboard JSON file is here:
```
~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/grafana/document-ingestion-dashboard.json
```

Or copy it to your desktop for easier access:
```bash
cp ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/grafana/document-ingestion-dashboard.json ~/Desktop/
```

---

## ✅ **Quick Test:**

After import, you should see the dashboard in:
- **Dashboards** → **Browse** → **"Document Ingestion API - Boss Demo"**

Or search for it:
- Click **search icon** (🔍)
- Type: "Document Ingestion"
- Click the dashboard

---

**Need help? The dashboard JSON is a valid Grafana dashboard definition ready to import!** 📊
