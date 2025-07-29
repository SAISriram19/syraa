# SYRAA Clinic AI Receptionist - Deployment Guide

## Deployment with Dokploy

This guide will help you deploy the SYRAA Clinic Voice AI Receptionist using Dokploy.

### Prerequisites

1. **Dokploy Server**: A server with Dokploy installed
2. **Domain**: A domain name for your API endpoint
3. **Environment Variables**: All the API keys and credentials

### Environment Variables Required

Create these environment variables in your Dokploy dashboard:

#### Google Calendar
```
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=your_google_redirect_uri
```

#### LiveKit (Voice)
```
LIVEKIT_URL=wss://your-livekit-instance.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
```

#### Plivo (Telephony)
```
PLIVO_AUTH_ID=your_plivo_auth_id
PLIVO_AUTH_TOKEN=your_plivo_auth_token
PLIVO_PHONE_NUMBER=your_clinic_phone_number
```

#### Supabase (Database)
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
```

#### AI Services
```
GOOGLE_API_KEY=your_google_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash
GEMINI_TEMPERATURE=0.7
DEEPGRAM_API_KEY=your_deepgram_api_key
ELEVEN_API_KEY=your_elevenlabs_api_key
OPENAI_API_KEY=your_openai_api_key
```

### Deployment Steps

#### Option 1: Using Dokploy Dashboard

1. **Create New Project**
   - Go to your Dokploy dashboard
   - Click "New Project"
   - Name: `syraa-clinic-ai`

2. **Add Git Repository**
   - Connect your Git repository
   - Select the branch to deploy

3. **Configure Environment Variables**
   - Go to "Environment Variables"
   - Add all the variables listed above

4. **Deploy Services**
   - Dokploy will automatically detect the `dokploy.yml` file
   - Click "Deploy"

#### Option 2: Using Docker Compose

If you prefer Docker Compose:

```bash
# Clone the repository
git clone <your-repo-url>
cd syraa_new

# Copy environment file
cp .env.example .env
# Edit .env with your actual values

# Deploy with Docker Compose
docker-compose up -d
```

### Service Architecture

The deployment includes two main services:

1. **MCP Server** (`syraa-mcp-server`)
   - Port: 8000
   - Handles API requests and database operations
   - Health check: `/health`

2. **Agent** (`syraa-agent`)
   - Runs the LiveKit voice agent
   - Connects to MCP server for backend operations

### Health Monitoring

- **MCP Server Health**: `https://your-domain.com/health`
- **API Documentation**: `https://your-domain.com/docs`

### Scaling Configuration

The deployment is configured with auto-scaling:

- **MCP Server**: 1-3 instances (scales at 70% CPU)
- **Agent**: 1-2 instances (scales at 80% CPU)

### SSL/TLS

SSL is automatically configured through Dokploy for the MCP server endpoint.

### Logs and Monitoring

Logs are available through:
- Dokploy dashboard logs viewer
- Docker logs: `docker logs syraa-mcp-server`

### Troubleshooting

#### Common Issues

1. **Environment Variables Not Set**
   - Check all required environment variables are configured
   - Restart services after adding variables

2. **Database Connection Issues**
   - Verify Supabase URL and key
   - Check network connectivity

3. **LiveKit Connection Issues**
   - Verify LiveKit URL and credentials
   - Check firewall settings

4. **Health Check Failures**
   - Check if port 8000 is accessible
   - Verify the `/health` endpoint responds

#### Checking Service Status

```bash
# Check running containers
docker ps

# Check MCP server logs
docker logs syraa-mcp-server

# Check agent logs
docker logs syraa-agent

# Test health endpoint
curl https://your-domain.com/health
```

### Production Considerations

1. **Security**
   - Use strong API keys
   - Enable firewall rules
   - Regular security updates

2. **Backup**
   - Regular database backups
   - Environment variable backups

3. **Monitoring**
   - Set up uptime monitoring
   - Configure alerts for service failures

4. **Performance**
   - Monitor resource usage
   - Adjust scaling parameters as needed

### Support

For deployment issues:
1. Check the logs first
2. Verify all environment variables
3. Test individual components
4. Contact support with specific error messages

## Quick Start Commands

```bash
# Test local deployment
docker-compose up -d

# Check services
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```