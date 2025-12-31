# Local Development Setup for Certificate Generation

## Quick Fix: Use Local File Storage

To test certificate generation locally without S3/AWS setup, you need to ensure local file storage is enabled.

### Step 1: Check Your .env File

Create or update your `.env` file in the project root and make sure it has:

```env
USE_REMOTE_MEDIA=False
```

**OR** simply don't set `USE_REMOTE_MEDIA` at all (it defaults to `False`).

### Step 2: Restart Your Django Server

After updating the `.env` file, restart your Django development server:

```bash
# Stop the server (Ctrl+C) and restart it
python manage.py runserver
```

### Step 3: Verify Media Directory Exists

The certificates will be saved to:
```
media/certificates/
```

Make sure this directory exists (it will be created automatically when you issue a certificate).

### Step 4: Test Certificate Generation

1. Go to your superadmin dashboard
2. Navigate to a learner registration
3. Click "Issue Certificate"
4. The certificate should now be generated and saved locally
5. You can download it from the same page

## How It Works

- **When `USE_REMOTE_MEDIA=False`**: Certificates are saved to your local `media/certificates/` folder
- **When `USE_REMOTE_MEDIA=True`**: Certificates are saved to AWS S3 (requires AWS credentials)

## Troubleshooting

### Error: "AWS S3 storage configuration is incomplete"

**Solution**: Make sure `USE_REMOTE_MEDIA=False` in your `.env` file and restart the server.

### Certificates Not Downloading

**Solution**: Make sure `DEBUG=True` in your settings (which it should be for local development). The media files are served automatically in DEBUG mode.

### Can't Find Generated Certificates

**Location**: Check `media/certificates/` folder in your project root directory.

## For Production Deployment

When you're ready to deploy, you can:
1. Set up AWS S3 (or DigitalOcean Spaces)
2. Add AWS credentials to your `.env` file
3. Set `USE_REMOTE_MEDIA=True`
4. The certificates will automatically be saved to cloud storage

---

**Note**: The storage backend automatically switches between local and S3 storage based on the `USE_REMOTE_MEDIA` setting. No code changes needed!

