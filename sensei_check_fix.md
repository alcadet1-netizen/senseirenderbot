# Fixed SenseiCheck service MongoRedis initialization error

## Problem
The bot was encountering an error: `'MongoRedis' object has no attribute 'initialized'` when trying to list checks or perform other operations that required the SenseiCheck service. This occurred because the `SenseiCheckRepository` was not being properly initialized, and the `initialized` flag was not being set.

## Root Cause
1. The `SenseiCheckRepository` constructor expected a collection but was being passed a database in the container.
2. The repository had an `init` method that was supposed to set up the collections and set the `initialized` flag, but it was not being called correctly.
3. The `SenseiCheckService` had an `_ensure_repo` method that checked the `initialized` flag and called `init`, but due to the mismatched constructor arguments, the repository was not set up correctly.

## Solution
1. **Modified `SenseiCheckRepository`**:
   - Changed the constructor to accept an `AsyncIOMotorDatabase` instead of a collection.
   - Set up both the checks and activations collections in the constructor.
   - Removed the `init` method and set `self.initialized = True` in the constructor.

2. **Updated the container (`src/core/container.py`)**:
   - Modified the `sensei_check_service` property to pass the database to the repository constructor.
   - Added the `redis` as a fourth argument to the `SenseiCheckService` constructor.

3. **Updated `SenseiCheckService` (`src/services/sensei_check_service.py`)**:
   - Removed the `_ensure_repo` method since the repository is now always initialized.
   - Updated the `__init__` method to accept a `redis` parameter and store it.
   - Changed the caching methods (`_cache_set`, `_cache_get`, `_cache_delete`) to use the `redis` object instead of the mongo client's cache methods.
   - Updated the `activate_check` method to match the signature expected by the user handlers (adding `bot`, `referrer_id`, and `captcha_solved` parameters) and adjusted the logic accordingly.
   - Fixed the `burn_check` method to use the `Visuals` import for logging.

4. **Updated imports**:
   - Added `from src.core.visuals import Visuals` to the service file.
   - Ensured the repository imports `AsyncIOMotorDatabase`.

## Changes Summary
- `src/domain/repositories/sensei_check_repository.py`: Constructor changed, init removed.
- `src/core/container.py`: Updated `sensei_check_service` property to pass database and redis.
- `src/services/sensei_check_service.py`: Updated constructor, removed `_ensure_repo`, updated caching, updated `activate_check` signature and logic, added Visuals import.

## Verification
After these changes, the bot should no longer encounter the `'MongoRedis' object has no attribute 'initialized'` error. The repository is properly initialized upon creation, and the service uses the redis instance for caching as intended.

## Why This Fix Works
The repository is now guaranteed to be initialized when the service is instantiated because the constructor sets up the collections and the flag. The service no longer needs to check an initialization flag or call an init method. The dependency injection in the container ensures that the correct instances are passed to the service.