# Railway Deployment Guide

## Prerequisites
- A [Railway](https://railway.app) account
- This repo connected to Railway

## Step 1: Create a New Project on Railway
1. Go to https://railway.app/dashboard
2. Click **New Project** → **Deploy from GitHub Repo**
3. Select `siyaida/leads-railway`

## Step 2: Add PostgreSQL
1. In the project canvas, click **New** → **Database** → **Add PostgreSQL**
2. Railway will auto-provision the database and inject `DATABASE_URL` into your service

## Step 3: Link the Database to the Service
1. Click on your service (the one deploying from this repo)
2. Go to **Variables**
3. Click **Add Reference** and select `DATABASE_URL` from the PostgreSQL plugin
   - This ensures your app uses the Railway-managed PostgreSQL connection string

## Step 4: Set Environment Variables
In the service's **Variables** tab, add the following:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | Auto-injected from PostgreSQL plugin (Step 3) |
| `SECRET_KEY` | Yes | A random secret for JWT signing (e.g., `openssl rand -hex 32`) |
| `CORS_ORIGINS` | Yes | Set to your Railway public domain, e.g. `https://leads-railway-production.up.railway.app` |
| `SERPER_API_KEY` | No | Serper.dev API key for web search |
| `APOLLO_API_KEY` | No | Apollo.io API key for lead enrichment |
| `OPENAI_API_KEY` | No | OpenAI API key for AI features |
| `OPENAI_MODEL` | No | OpenAI model to use (default: `gpt-4o-mini`) |

## Step 5: Deploy
Railway will automatically build from the Dockerfile and deploy. The app will be available at your Railway-provided domain.

## Step 6: Generate a Public Domain
1. Click on the service → **Settings** → **Networking**
2. Click **Generate Domain** to get a public URL

## How It Works
- The Dockerfile builds a Python 3.11 image with all dependencies
- FastAPI serves the API at `/api/*` and the React SPA at all other routes
- The `PORT` environment variable is set automatically by Railway
- Database tables are created automatically on startup

## Troubleshooting

### App crashes on startup
- Check that `DATABASE_URL` is properly linked from the PostgreSQL plugin
- Check the deploy logs in Railway for error details

### Frontend shows blank page
- Ensure the `static/` directory contains the built frontend (`index.html`, `assets/`)
- Check browser console for 404 errors on asset files

### CORS errors
- Set `CORS_ORIGINS` to your Railway domain (include `https://`)
