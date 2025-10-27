# Shop Assistant AI

An AI-powered sales and consulting agent that enhances customer engagement and support through real-time intelligent conversations.

## 🚀 Features

### Core Capabilities
- **24/7 AI Customer Support**: Intelligent virtual assistant powered by OpenRouter and OpenAI GPT-4
- **Natural Conversation Management**: LLM-driven dialogue with context awareness
- **E-commerce Integration**: Seamless Shopify integration for product information and orders
- **CRM Integration**: Customer data management with HubSpot/Salesforce
- **Real-time Communication**: WebSocket support for live interactions

### AI & Intelligence
- **LLM-First Architecture**: Leverages OpenRouter for access to multiple AI models
- **RAG System**: Advanced retrieval-augmented generation with Cohere embeddings
- **Dynamic Response Generation**: Context-aware, personalized responses
- **Intelligent Escalation**: AI-powered human agent handoff decisions
- **Sentiment Analysis**: Emotional intelligence and frustration detection

### API & Integration
- **Comprehensive REST API**: Full-featured API for frontend integration
- **Real-time WebSockets**: Live chat and notifications
- **Webhook Support**: Event-driven integrations
- **Security First**: JWT authentication, rate limiting, and audit logging

## 🛠️ Technology Stack

### Backend Framework
- **FastAPI** - Modern, high-performance web framework
- **Uvicorn** - ASGI server for production deployment
- **Pydantic** - Data validation and serialization

### Database & Storage
- **PostgreSQL** - Primary database for persistent data
- **Redis** - Session management and caching
- **Alembic** - Database migration management

### AI & NLP
- **OpenRouter** - Access to OpenAI GPT-4 and Anthropic Claude models
- **Cohere** - Advanced embedding models for semantic search
- **LangChain** - LLM orchestration framework
- **Vector Databases** - Pinecone/Weaviate for RAG implementation

### Security & Monitoring
- **JWT Authentication** - Secure token-based authentication
- **Rate Limiting** - DDoS protection and abuse prevention
- **Audit Logging** - Comprehensive security event tracking
- **Prometheus** - Metrics and monitoring

## 📋 Prerequisites

- **Python 3.9+**
- **Docker & Docker Compose**
- **PostgreSQL 15+** (if not using Docker)
- **Redis 7+** (if not using Docker)
- **OpenRouter API Key**
- **Cohere API Key**

## 🚀 Quick Start

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd shop-assistant-ai
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

3. **Start the development environment**
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

4. **Access the application**
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - PostgreSQL Admin: http://localhost:5050 (optional)
   - Redis Commander: http://localhost:8081 (optional)

### Local Development

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Set up pre-commit hooks**
   ```bash
   pre-commit install
   ```

4. **Start databases with Docker**
   ```bash
   docker-compose up db redis -d
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start the application**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## 📁 Project Structure

```
shop-assistant-ai/
├── app/
│   ├── api/                 # API endpoints
│   │   └── v1/             # API version 1
│   ├── core/               # Core configuration
│   ├── db/                 # Database configuration
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic schemas
│   ├── services/           # Business logic
│   ├── utils/              # Utility functions
│   ├── middleware/         # Custom middleware
│   ├── tests/              # Test suite
│   └── main.py            # Application entry point
├── migrations/             # Alembic migrations
├── docker-compose.yml      # Production Docker setup
├── docker-compose.dev.yml  # Development Docker setup
├── requirements.txt        # Production dependencies
├── requirements-dev.txt    # Development dependencies
└── .env.example           # Environment variables template
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Application
SECRET_KEY=your-secret-key
DEBUG=true

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/shop_assistant

# Redis
REDIS_URL=redis://localhost:6379/0

# AI Services
OPENROUTER_API_KEY=your-openrouter-api-key
COHERE_API_KEY=your-cohere-api-key

# Security
ACCESS_TOKEN_EXPIRE_MINUTES=30
RATE_LIMIT_PER_MINUTE=60
```

### Database Setup

1. **Initialize database**
   ```bash
   alembic init alembic
   ```

2. **Create migration**
   ```bash
   alembic revision --autogenerate -m "Initial migration"
   ```

3. **Apply migration**
   ```bash
   alembic upgrade head
   ```

## 🧪 Testing

### Run Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m "not slow"    # Skip slow tests
```

### Code Quality
```bash
# Format code
black app/
isort app/

# Lint code
flake8 app/
mypy app/

# Security check
bandit -r app/

# Run pre-commit hooks manually
pre-commit run --all-files
```

## 📚 API Documentation

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Main Endpoints

#### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh token
- `POST /api/v1/auth/logout` - User logout

#### Chat & Conversation
- `POST /api/v1/chat/message` - Send message
- `GET /api/v1/chat/history/{conversation_id}` - Get conversation history
- `WebSocket /api/v1/chat/ws/{conversation_id}` - Real-time chat

#### AI & Intelligence
- `POST /api/v1/ai/intent` - Classify user intent
- `POST /api/v1/ai/entities` - Extract entities
- `POST /api/v1/ai/sentiment` - Analyze sentiment

#### E-commerce
- `GET /api/v1/products/search` - Search products
- `GET /api/v1/products/{product_id}` - Get product details
- `GET /api/v1/orders/{order_id}` - Get order status

## 🔒 Security

### Authentication
- JWT-based authentication with refresh tokens
- Secure session management
- API key rotation support

### Data Protection
- Input validation and sanitization
- SQL injection prevention
- Rate limiting and DDoS protection
- Audit logging for security events

### Best Practices
- Environment-based configuration
- Regular security updates
- Dependency vulnerability scanning
- Secure password hashing

## 📊 Monitoring & Logging

### Application Logs
```bash
# View logs
docker-compose logs -f app

# Filter by service
docker-compose logs -f db
docker-compose logs -f redis
```

### Health Checks
- Application health: http://localhost:8000/health
- Database health check
- Redis health check

### Metrics
- Prometheus metrics endpoint
- Custom business metrics
- Performance monitoring

## 🚀 Deployment

### Production Deployment
```bash
# Build production image
docker build -t shop-assistant-ai .

# Run production containers
docker-compose up -d

# Or use production profile
docker-compose --profile production up -d
```

### Environment-Specific Configurations
- Development: `docker-compose.dev.yml`
- Staging: `docker-compose.staging.yml`
- Production: `docker-compose.yml`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guidelines
- Write tests for new features
- Update documentation
- Run pre-commit hooks before pushing

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the `/docs` endpoint
- **Issues**: Create an issue on GitHub
- **Discussions**: Join our GitHub Discussions

## 🗺️ Roadmap

### Phase 1: Foundation ✅
- [x] Project infrastructure
- [x] Core backend framework
- [x] Database architecture
- [x] Security foundation
- [x] LLM integration
- [x] API development

### Phase 2: Integration & Advanced AI (In Progress)
- [ ] Shopify integration
- [ ] Order management
- [ ] RAG system
- [ ] CRM integration
- [ ] Analytics & logging
- [ ] Workflow automation

### Phase 3: API Development & Agent Integration
- [ ] Advanced API features
- [ ] Agent management
- [ ] Analytics & reporting
- [ ] Human agent handoff
- [ ] LLM-powered escalation

### Phase 4: Testing & Deployment
- [ ] Comprehensive testing
- [ ] Production deployment
- [ ] Performance optimization
- [ ] Documentation completion

---

**Built with ❤️ by the Shop Assistant AI Team**