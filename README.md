
# test-mycurrency-backbase
# MyCurrency API

REST API for managing currency exchange rates with support for multiple providers, automatic fallback, and historical data backfilling.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (fast Python package installer and resolver)
- **Redis** (Required for Celery tasks)

  **Installing and Running Redis:**
  
  *   **Docker (Recommended):**
      ```bash
      docker run -d -p 6379:6379 redis
      ```
  *   **Linux (Ubuntu/Debian):**
      ```bash
      sudo apt-get install redis-server
      sudo service redis-server start
      ```
  *   **Mac (Homebrew):**
      ```bash
      brew install redis
      brew services start redis
      ```

### Installation

1. **Install uv**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Setup Environment and Install Dependencies**
   The project uses `uv` for dependency management.
   ```bash
   make install
   ```
   This command runs `uv sync`, which creates the virtual environment and installs all dependencies.

3. **Initialize Database**
   Run migrations and load initial currency data:
   ```bash
   make init
   ```

4. **Create Admin User**
   ```bash
   make superuser
   ```

## 🏃‍♂️ Running the Project

### Development Server
Start the Django development server:
```bash
make run
```
The API will be available at `http://localhost:8000/api/`.

### Background Worker (Celery)
To handle asynchronous tasks (like backfilling historical rates), run the worker in a separate terminal:
```bash
make worker
```

### Scheduler (Celery Beat)
To schedule periodic tasks (like fetching daily rates at 7 AM), run the beat scheduler in a separate terminal.
The schedule is stored in the database and initialized via `make init`.
```bash
make beat
```

## 🛠️ How It Works

### Data Flow
The system follows a **"Database First"** approach with an **Adapter Pattern** for external providers.

1. **Request**: User requests an exchange rate (e.g., `GET /api/rates/timeseries/?source=EUR&target=USD`).
2. **Service Layer**: `ExchangeRateService` handles the business logic.
3. **Database Check**:
   - The system checks the database for existing rates.
   - It intelligently handles direct (`EUR->USD`) and inverse (`USD->EUR`) pairs.
4. **External Provider (Fallback)**:
   - If data is missing, the `ProviderManager` is invoked.
   - It iterates through active providers (e.g., CurrencyBeacon, Mock) based on priority.
   - The `Adapter` converts the external response to a standardized format.
5. **Storage**: The fetched rate is saved to the database for future use.
6. **Response**: The data is returned to the user.

### Async Backfilling
For large date ranges where data is missing, the system triggers a background task (`backfill_exchange_rates`) to fetch and store historical data without blocking the API response.

## 🔐 Admin Panel

The project includes the Django Admin interface for management and configuration.

**Access:** `http://localhost:8000/admin/`
**Login:** Use the credentials created via `make superuser`.

### Key Features:

1.  **Currency Management**:
    *   Add/Edit supported currencies.
    *   **Currency Converter Tool**: A built-in tool to test conversions directly from the admin panel.

2.  **Provider Configuration (Runtime)**:
    *   **Priority System**: Reorder providers by changing their "Priority" value. The system always tries the lowest number first.
    *   **Live Updates**: Update API keys, URLs, or timeouts without restarting the server.
    *   **Toggle Providers**: Enable/Disable providers instantly if one goes down.

3.  **Exchange Rates**:
    *   View all stored historical rates.
    *   Filter by date, provider, or currency pair.

## 📚 Key Commands (Makefile)

| Command | Description |
|---------|-------------|
| `make install` | Install project dependencies |
| `make init` | Run migrations and initialize currencies |
| `make run` | Start Django development server |
| `make worker` | Start Celery worker |
| `make beat` | Start Celery beat scheduler |
| `make test` | Run unit tests |
| `make lint` | Check code style (Ruff & Black) |
| `make shell` | Open Django shell |

## 🏗️ Project Structure

- `currencies/`: Main application logic.
  - `api/`: DRF Views and Serializers.
  - `services/`: Business logic (ExchangeRateService).
  - `managers.py`: Custom QuerySet logic (Smart lookup).
- `external/`: External API integrations.
  - `api_clients/adapters/`: Adapters for different providers.
- `mycurrency/`: Project configuration.

## 🔮 Future Improvements

### ⚡ Performance & Scalability
- **Caching Layer**: Implement Redis caching for the `timeseries` endpoint to reduce database load for popular queries.
- **Database Partitioning**: As the `CurrencyExchangeRate` table grows, partition it by `valuation_date` (e.g., yearly) to maintain query speed.
- **Circuit Breaker Pattern**: Implement a robust circuit breaker for external providers to "fail fast" when a provider is down, preventing cascading timeouts.
- **Database**: Migrate to a more robust database such as Postgres.

### 🛡️ Security & Reliability
- **API Rate Limiting**: Add throttling (e.g., `UserRateThrottle`) to protect against abuse and ensure fair usage.
- **Authentication**: Implement JWT or API Key authentication for clients.
- **Secret Management**: Use a dedicated secret manager (like HashiCorp Vault or AWS Secrets Manager) instead of `.env` files in production.


### 📦 DevOps
- **Docker Compose**: Create a `docker-compose.yml` for one-command setup of Django, Redis, and Celery.
- **CI/CD**: Set up GitHub Actions for automated linting, testing, and deployment.
