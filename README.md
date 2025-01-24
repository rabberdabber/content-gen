# Content Gen

A modern backend application template using FastAPI with PostgreSQL, Redis, and MinIO for content management.

## Features

### Backend (FastAPI)

- 🚀 Modern Python web framework using FastAPI
- 🔐 JWT authentication with password hashing
- 📨 Email verification and password recovery
- 🗄️ SQLModel (SQLAlchemy core) for database operations
- 📝 Automatic API documentation with Swagger UI
- 🔄 Redis for caching and rate limiting
- 📦 MinIO S3-compatible object storage
- 🏷️ Tag-based content organization
- 🤖 AI-powered content generation and moderation
- ✨ CORS, Static Files, Dependencies, and more

### DevOps

- 🐳 Docker Compose setup for development
- 🚀 Deployment ready for Coolify
- 🔄 CI/CD with GitHub Actions

## Quick Start

### Local Development

1. Clone the repository:

```bash
git clone <repository-url> my-project
cd my-project
```

2. Copy `.env.example` to `.env` and update the values:

```bash
cp .env.example .env
```

3. Start the development environment:

```bash
docker compose watch
```

4. Access the services:

- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- MinIO Console: http://localhost:9001

### Deployment with Coolify

1. Fork or clone this repository to your GitHub account
2. In your Coolify dashboard:

   - Create a new service
   - Select "Docker Compose"
   - Connect your repository
   - Configure environment variables
   - Deploy
3. Required environment variables for deployment:

   ```
   DOMAIN=your-domain.com
   ENVIRONMENT=production
   SECRET_KEY=your-secret-key
   FIRST_SUPERUSER=admin@example.com
   FIRST_SUPERUSER_PASSWORD=your-secure-password
   POSTGRES_PASSWORD=your-db-password
   MINIO_ROOT_USER=your-minio-user
   MINIO_ROOT_PASSWORD=your-minio-password
   ```

## API Endpoints

### Authentication

- `POST /api/v1/login/access-token` - OAuth2 compatible token login
- `POST /api/v1/login/test-token` - Test token validation
- `POST /api/v1/password-recovery/{email}` - Password recovery
- `POST /api/v1/reset-password/` - Reset password

### Posts

- `GET /api/v1/posts/` - List all published posts (with pagination and tag filtering)
- `POST /api/v1/posts/` - Create new post (superuser only)
- `GET /api/v1/posts/me` - Get current user's posts
- `GET /api/v1/posts/{post_id}` - Get specific post
- `PUT /api/v1/posts/{post_id}` - Update post (superuser only)
- `DELETE /api/v1/posts/{post_id}` - Delete post (superuser only)

### Drafts

- `GET /api/v1/drafts/` - List user's draft posts
- `GET /api/v1/drafts/{draft_id}` - Get specific draft

### Tags

- `POST /api/v1/posts/tags` - Create new tag (superuser only)
- `GET /api/v1/posts/tags` - List all tags with post counts

### AI Generation
#### Public Routes (Rate Limited)
- `POST /api/v1/ai/public/generate-image` - Generate images with AI
- `POST /api/v1/ai/public/generate-draft-content` - Generate draft content
- `POST /api/v1/ai/public/moderate-content` - Content moderation

#### Private Routes (Authenticated, Higher Rate Limits)
- `POST /api/v1/ai/private/generate-image` - Generate images with AI
- `POST /api/v1/ai/private/generate-draft-content` - Generate draft content
- `POST /api/v1/ai/private/moderate-content` - Content moderation

Features:
- Multiple content tones: article, tutorial, academic, casual
- Rate limiting for both public and authenticated users
- Content moderation capabilities
- AI-powered image generation

### Media Storage

- File upload and management through MinIO S3-compatible storage
- Supports metadata, content types, and presigned URLs
- Automatic bucket creation and management
- File listing with pagination and filtering

## Services

### PostgreSQL

- Primary database for storing application data
- Stores posts, users, and tags
- Runs on port 5432

### Redis

- Used for caching and rate limiting
- Runs on port 6379

### MinIO

- S3-compatible object storage for media files
- Supports metadata, content types, and presigned URLs
- API runs on port 9000
- Console runs on port 9001
- Features:
  - Automatic bucket creation
  - File deduplication with UUID-based naming
  - Metadata support for media types and attributes
  - Presigned URL generation for secure access
  - Pagination and filtering for file listings

## Development

Before deploying, make sure to update the following in your `.env` file:

- `SECRET_KEY` - Generate using: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `FIRST_SUPERUSER_PASSWORD`
- `POSTGRES_PASSWORD`
- `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`
- Other sensitive credentials

For detailed setup instructions, refer to:

- [Development Guide](./development.md)
- [Deployment Guide](./deployment.md)

## Documentation

- [Backend Documentation](./backend/README.md)
- [Deployment Guide](./deployment.md)
- [Development Guide](./development.md)

## License

This project is licensed under the terms of the MIT license.
