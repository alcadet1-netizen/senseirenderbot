---
name: sensei-check-presenter-fix
description: Fixed 'property' object is not callable error in SenseiCheckPresenter
metadata:
  type: reference
---

Added conversion to plain dictionaries in SenseiCheckService.get_all_checks() to prevent decorated repository objects from causing attribute access issues in presenter methods. The fix ensures that check objects passed to presenter methods are standard dictionaries with working .get() methods.

**Why:** The repository was returning decorated objects (likely from BaseRepository wrapping) that had a faulty get property returning a property object instead of a method. This caused check.get('code') to fail with "'property' object is not callable" when the presenter tried to access check fields.

**How to apply:** The fix converts repository results to plain dictionaries using [dict(check) if not isinstance(check, dict) else check for check in checks] in the service layer before returning to handlers, ensuring presenter methods receive standard dictionaries.