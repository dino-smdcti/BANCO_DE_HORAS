# Test Results and Identified Errors

## Summary
- **Total Tests Collected**: 42 (40 executed, 2 ignored due to collection errors)
- **Passed**: 40
- **Failed**: 0 (after fix)
- **Warnings**: 7

---

## Identified Errors

### 1. Collection Errors (Missing Dependencies)
Two test files failed to load because the `webdriver_manager` library is not installed in the environment.

- **Files affected**:
  - `tests/test_role_localization.py`
  - `tests/test_selenium_routes.py`
- **Error message**:
  ```
  ModuleNotFoundError: No module named 'webdriver_manager'
  ```
- **Recommended Action**: Install `webdriver_manager` using `pip install webdriver-manager` or add it to `requirements.txt`.

### 2. Logic Bug in `register_user` (Fixed)
The test `tests/integration/test_services.py::test_cannot_register_duplicate_user` was failing because the service was returning `False` instead of raising a `ValueError` when a duplicate email was encountered.

- **Error message**:
  ```
  E       Failed: DID NOT RAISE <class 'ValueError'>
  ```
- **Fix**: Updated `src/service_layer/services.py` to raise `ValueError("Email already exists.")` instead of returning `False`.

---

## Warnings
Multiple tests reported a `DeprecationWarning` regarding `datetime.datetime.utcnow()`.

- **Message**:
  ```
  DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
  ```
- **Location**: `src/service_layer/services.py:164`
- **Recommended Action**: Update the code to use `datetime.now(datetime.UTC)`.
