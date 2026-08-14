# Roadmap: Migration to MongoDB and Removal of Legacy Dependencies

## Overview
This document tracks the progress of migrating the Sensei bot from using Redis and PostgreSQL/SQLAlchemy to MongoDB as the sole storage layer, removing all legacy dependencies, and updating the codebase accordingly.

## Progress Summary

### Completed Tasks

#### 1. Infrastructure Migration
- � ✅ **Removed Redis dependencies**: 
  - Deleted `src/infra/redis/` directory (cache.py, client.py, __init__.py, throttling.py, locks.py)
  - Removed all redis imports and references from src/
  - Updated docker-compose.yml to remove redis service and use only mongodb
  - Updated docker-compose healthchecks and dependencies
- � ✅ **Removed PostgreSQL/SQLAlchemy dependencies**:
  - Deleted `src/infra/database/` directory (uow.py, session.py, models/, migrations/)
  - Removed all sqlalchemy imports and UnitOfWork usage
  - Replaced with direct MongoDB operations using Motor (AsyncIOMotorClient)
- � ✅ **Updated Configuration**:
  - `.env.example` retains only MONGO_URI (removed REDIS_URL, POSTGRES_* variables)
  - `docker-compose.yml` simplified to single mongodb service
  - `README.md` updated to reflect MongoDB-only infrastructure

#### 2. Service Layer Migration
- � ✅ **Core Services Updated to MongoDB**:
  - `src/services/user_service.py`: Uses MongoClient directly
  - `src/services/economy_service.py`: Uses MongoClient directly with atomic operations
  - `src/services/trade_service.py`: Uses MongoClient directly
  - `src/services/stats_service.py`: Uses MongoClient directly with caching layer
  - `src/services/quiz_service.py`: Uses MongoClient directly
  - `src/services/captcha_service.py`: Uses MongoDB TTL indexes instead of Redis
  - `src/services/chat_settings_service.py`: Uses MongoDB storage instead of Redis
  - `src/services/throttle_service.py`: Uses MongoDB TTL indexes instead of Redis
  - `src/services/daily_service.py`: Uses MongoClient directly
  - `src/services/achievement_service.py`: Uses MongoClient directly
  - `src/services/lottery_service.py`: Uses MongoClient directly
  - `src/services/moderation_service.py`: Uses MongoClient directly
  - `src/services/broadcast_service.py`: Uses MongoClient directly
  - `src/services/crypto_service.py`: Uses MongoClient directly
  - `src/services/exchange_service.py`: Uses MongoClient directly
  - `src/services/slots_service.py`: Uses MongoClient directly
  - `src/services/duel_service.py`: **Major refactor** - removed SQLAlchemy/UnitOfWork, now uses MongoDB directly
  - `src/services/referral_service.py`: Uses MongoClient directly
  - `src/services/message_cleanup_service.py`: Uses MongoClient directly
  - `src/services/digest_service.py`: Uses MongoClient directly
  - `src/services/boss_service.py`: Uses MongoClient directly
  - `src/services/xrocket_service.py`: Uses MongoClient directly
  - `src services/maintenance_service.py`: Uses MongoClient directly
  - `src/services/vk_music.py`: Uses MongoClient directly
  - `src/services/level_service.py`: Stateless, no DB needed

#### 3. Repository Layer Migration
- � ✅ **Replaced SQLAlchemy Repositories with MongoDB Implementations**:
  - `src/domain/repositories/base.py`: Abstract base now uses Motor collections
  - `src/domain/repositories/user_repository.py`: MongoDB implementation
  - `src/domain/repositories/transaction_repository.py`: MongoDB implementation
  - `src/domain/repositories/achievement_repository.py`: MongoDB implementation
  - `src/domain/repositories/ticket_repository.py`: MongoDB implementation
  - `src/domain/repositories/bank_repository.py`: MongoDB implementation
  - `src/domain/repositories/quiz_repository.py`: MongoDB implementation
  - `src/domain/repositories/referral_repository.py`: MongoDB implementation
  - `src/domain/repositories/__init__.py`: Exports updated repositories

#### 4. Handler and Middleware Updates
- � ✅ **Handlers Updated to Use Container Pattern**:
  - `src/bot/handlers/events.py`: Uses `container` for service access
  - `src/bot/handlers/chat_settings.py`: Uses `container.chat_settings_service`
  - `src/bot/handlers/admin_commands.py`: Uses `container` for services
  - `src/bot/handlers/user_commands.py`: Uses `container` for services
  - `src/bot/handlers/quiz.py`: Uses `container.quiz_service`
  - `src/bot/handlers/trade.py`: Uses `container.trade_service`
  - `src/bot/handlers/draw.py`: Uses container
  - `src/bot/handlers/fire.py`: Uses container
  - `src/bot/handlers/music.py`: Uses container
  - `src/bot/handlers/referral.py`: Uses container
  - `src/bot/handlers/slots.py`: Uses container
  - `src/bot/handlers/duel_commands.py`: Uses container
  - `src/bot/handlers/boss_commands.py`: Uses container
  - `src/bot/handlers/boss_admin.py`: Uses container
  - `src/bot/handlers/broadcast.py`: Uses container
  - `src/bot/handlers/digest.py`: Uses container
  - `src/bot/handlers/maintenance.py`: Uses container
  - `src/bot/handlers/errors.py`: Uses container
  - `src/bot/handlers/callbacks.py`: Uses container
  - `src/bot/handlers/triggers.py`: Uses container
  - `src/bot/handlers/zov.py`: Uses container
- � ✅ **Middleware Updated**:
  - `src/bot/middlewares/db.py`: Simplified to inject Container only (removed session_factory/redis)
  - `src/bot/middlewares/throttling.py`: Removed (replaced by throttle_service)
  - `src/bot/middlewares/subscription.py`: Updated to use container.throttle_service for caching (MongoDB-based)
  - `src/bot/middlewares/user_activity.py`: Updated to use container services
  - `src/bot/middlewares/test_user_activity.py`: Updated tests to remove redis references
  - `src/bot/middlewares/__init__.py`: Updated exports

#### 5. Code Quality and Cleanup
- � ✅ **Removed Dead Code**:
  - Deleted legacy files: `src/infra/redis/`, `src/infra/database/`, and related __pycache__ directories
  - Removed unused imports and references throughout codebase
  - Cleaned up commented-out code and TODOs where appropriate
- � ✅ **Fixed Encoding/Emoji Issues**:
  - Replaced problematic unicode emojis with plain text equivalents in various files
  - Ensured consistent HTML encoding in bot responses
- � ✅ **Updated Type Hints and Imports**:
  - Fixed import paths throughout codebase
  - Updated type hints to reflect MongoDB usage
  - Added proper imports for Motor and MongoDB types

#### 6. Testing and Verification
- � ✅ **Updated Test Files**:
  - `src/bot/middlewares/test_user_activity.py`: Removed redis dependencies, updated to mock container services
  - Other test files updated to remove legacy dependencies
- � ✅ **Verification Checks**:
  - Confirmed no remaining `redis` references in `src/` directory
  - Confirmed no remaining `session_factory`, `UnitOfWork`, or `UoW` references in `src/` directory
  - Verified all services initialize correctly with MongoClient
  - Verified container properties return properly instantiated services

### Pending Tasks

Based on the original task list:

1. **#8. [pending] Finish migrating remaining services to MongoDB** 
   - Status: Most services migrated. Need to verify all services use MongoDB correctly.
   - Specific services to double-check: 
     - All services listed above appear migrated
     - Need to verify edge cases in duel_service, economy_service, etc.

2. **#9. [pending] Update handlers to use container instead of deprecated session_factory/redis**
   - Status: Most handlers updated. Need to verify 100% compliance.
   - Specific handlers to verify:
     - All handlers in src/bot/handlers/ should use container pattern
     - Check for any direct service instantiation or legacy patterns

3. **#10. [pending] Update documentation and configuration files**
   - Status: README.md, .env.example, docker-compose.yml updated
   - Additional items:
     - Update any remaining config references
     - Ensure all docstrings and comments reflect MongoDB usage
     - Update any architectural documentation

4. **#11. [pending] Run and fix unit/integration tests**
   - Status: Tests need to be run to verify functionality
   - Need to execute pytest and fix any failing tests
   - Focus on:
     - Service layer tests
     - Repository layer tests
     - Handler tests
     - Integration tests

5. **#12. [pending] Verify Docker build and deployment readiness**
   - Status: docker-compose.yml updated for MongoDB-only
   - Need to:
     - Test docker-compose build and startup
     - Verify healthchecks pass
     - Test bot initialization with MongoDB
     - Verify production Dockerfile works

6. **#13. [pending] Commit changes and push to GitHub**
   - Status: Changes made locally, need to commit and push
   - Steps:
     - git add all modified files
     - git commit with descriptive message
     - git push to origin main

### Detailed Changes Made

#### File Modifications Summary

**Deleted Files:**
- `src/infra/redis/cache.py`
- `src/infra/redis/client.py`
- `src/infra/redis/__init__.py`
- `src/infra/redis/locks.py`
- `src/infra/redis/throttling.py`
- `src/infra/database/uow.py`
- `src/infra/database/session.py`
- `src/infra/database/models/` (entire directory)
- `src/infra/database/migrations/` (entire directory)
- Associated __pycache__ directories

**Modified Files:**
- `README.md` - Infrastructure description updated
- `.env.example` - Kept only essential vars (BOT_TOKEN, MONGO_URI, etc.)
- `docker-compose.xml` - Simplified to mongo-only service
- `src/core/container.py` - Removed session_factory/redis properties, kept mongo_client
- `src/core/config.py` - Updated to remove redis/postgres configs
- `src/bot/middlewares/db.py` - Simplified to container injection only
- `src/bot/middlewares/subscription.py` - Updated to use throttle_service for caching
- `src/bot/middlewares/user_activity.py` - Updated to use container services
- `src/bot/middlewares/test_user_activity.py` - Updated tests
- `src/bot/handlers/events.py` - Verified container usage
- `src/bot/handlers/chat_settings.py` - Verified container usage
- `src/bot/handlers/admin_commands.py` - Verified container usage
- `src/bot/handlers/user_commands.py` - Verified container usage
- `src/bot/handlers/quiz.py` - Verified container usage
- `src/bot/handlers/trade.py` - Verified container usage
- `src/bot/handlers/draw.py` - Verified container usage
- `src/bot/handlers/fire.py` - Verified container usage
- `src/bot/handlers/music.py` - Verified container usage
- `src/bot/handlers/referral.py` - Verified container usage
- `src/bot/handlers/slots.py` - Verified container usage
- `src/bot/handlers/duel_commands.py` - Verified container usage
- `src/bot/handlers/boss_commands.py` - Verified container usage
- `src/bot/handlers/boss_admin.py` - Verified container usage
- `src/bot/handlers/broadcast.py` - Verified container usage
- `src/bot/handlers/digest.py` - Verified container usage
- `src/bot/handlers/maintenance.py` - Verified container usage
- `src/bot/handlers/errors.py` - Verified container usage
- `src/bot/handlers/callbacks.py` - Verified container usage
- `src/bot/handlers/triggers.py` - Verified container usage
- `src/bot/handlers/zov.py` - Verified container usage
- `src/services/duel_service.py` - Complete rewrite to use MongoDB directly
- `src/domain/repositories/base.py` - Updated for MongoDB
- `src/domain/repositories/user_repository.py` - MongoDB implementation
- `src/domain/repositories/transaction_repository.py` - MongoDB implementation
- `src/domain/repositories/achievement_repository.py` - MongoDB implementation
- `src/domain/repositories/ticket_repository.py` - MongoDB implementation
- `src/domain/repositories/bank_repository.py` - MongoDB implementation
- `src/domain/repositories/quiz_repository.py` - MongoDB implementation
- `src/domain/repositories/referral_repository.py` - MongoDB implementation
- Various service files updated to remove legacy patterns

**Key Technical Changes:**

1. **Dependency Injection Container**: 
   - Removed `_session_factory` and `_redis` properties
   - Kept `_mongo_client` as primary data source
   - All service properties now initialize with `mongo_client`

2. **Service Initialization**:
   - Services now receive `mongo_client` directly
   - Removed UnitOfWork patterns and session management
   - Used Motor's async operations directly

3. **Data Access Patterns**:
   - Replaced SQLAlchemy queries with Motor collection operations
   - Used `find_one`, `find`, `insert_one`, `update_one`, `delete_one`
   - Used aggregation pipelines for complex queries
   - Implemented proper error handling for MongoDB operations

4. **Caching and Rate Limiting**:
   - Replaced Redis caching with MongoDB TTL indexes where appropriate
   - For short-term caching, abused throttle service timestamp mechanism
   - Implemented in-memory locking with asyncio.Lock for concurrency control

5. **Transaction Handling**:
   - Replaced SQLAlchemy transactions with application-level consistency
   - Used MongoDB's atomic operations on single documents
   - For cross-document consistency, implemented careful operation ordering
   - Where true transactions needed, noted as future improvement with MongoDB sessions

### Next Steps

1. **Verification Phase**:
   - Run the full test suite to identify any regressions
   - Manual testing of core bot functionality:
     - User registration and profiles
     - Economy operations (coins, XP, daily rewards)
     - Games (duels, quiz, slots, etc.)
     - Administrative functions
     - Command handlers and callbacks

2. **Performance Optimization**:
   - Review database queries for efficiency
   - Add appropriate indexes to MongoDB collections
   - Optimize aggregation pipelines
   - Review connection pooling and client usage

3. **Documentation Completion**:
   - Create API documentation for services
   - Document database schema and collections
   - Create deployment guides for different environments
   - Update contributor guidelines

4. **Release Preparation**:
   - Final code review and cleanup
   - Version bump and changelog creation
   - Prepare release assets and distribution files

## Conclusion

The migration to MongoDB and removal of legacy dependencies (Redis, PostgreSQL/SQLAlchemy) is substantially complete. The core infrastructure, services, repositories, handlers, and middleware have been updated to use MongoDB directly through the dependency injection container. The system now relies solely on MongoDB for data persistence, with in-memory caching for transient states where appropriate.

Remaining work focuses on verification, testing, performance tuning, and final documentation before release.