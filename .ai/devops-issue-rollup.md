# DevOps Issue: npm Rollup Dependency Problem on Windows

## ✅ STATUS: RESOLVED (2025-12-18)

## Issue Description
npm is installing Linux platform-specific rollup binaries on Windows, causing test failures.

## Error Message
```
Error: Cannot find module @rollup/rollup-win32-x64-msvc
npm has a bug related to optional dependencies
(https://github.com/npm/cli/issues/4828)
```

## Original State
- Platform: Windows (win32)
- Node modules installed: `@rollup/rollup-linux-x64-gnu`, `@rollup/rollup-linux-x64-musl`
- Expected module: `@rollup/rollup-win32-x64-msvc`

## Impact
- ❌ Cannot run `npm test` commands
- ❌ Blocks test-driven development workflow
- ❌ Prevents validation of Story 11.8d test fixes

## Attempted Fixes (Before Resolution)
1. ✗ `npm install @rollup/rollup-win32-x64-msvc --save-optional` - No effect
2. ✗ `rm -rf node_modules package-lock.json && npm install` - Still installs Linux binaries
3. ✗ `npm install --force` - No effect

## Root Cause
Known npm bug with optional dependencies on Windows. npm is not correctly detecting the platform and installing wrong optional dependencies.

## Recommended Solutions (Priority Order)

### Solution 1: Manual Binary Installation
```bash
cd frontend
npm install --no-optional
npm install @rollup/rollup-win32-x64-msvc --save-optional --force
```

### Solution 2: Use Specific npm Version
```bash
# Upgrade to npm 10+ which may have the fix
npm install -g npm@latest
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Solution 3: Use Node 20+ LTS
```bash
# Install Node.js 20.x LTS
nvm install 20
nvm use 20
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Solution 4: Bypass Rollup (Temporary Workaround)
Edit `vite.config.ts` to use esbuild instead of rollup for tests:
```typescript
export default defineConfig({
  // ... existing config
  build: {
    rollupOptions: {
      // Disable for tests
    }
  },
  test: {
    // Use esbuild
  }
})
```

### Solution 5: Use WSL2 or Linux Environment
Run development and tests in WSL2 or Linux VM to avoid Windows-specific npm issues.

## Verification Steps
After applying fix:
```bash
cd frontend
ls node_modules/@rollup/
# Should show: rollup-win32-x64-msvc

npm test -- --run src/utils/sanitize.spec.ts
# Should execute tests successfully
```

## Related Links

- npm issue: <https://github.com/npm/cli/issues/4828>
- rollup optional dependencies: <https://github.com/rollup/rollup/issues>

## ✅ RESOLUTION (2025-12-18)

### Successful Solution: Manual Binary Download and Extraction

After attempting multiple npm-based solutions without success, the issue was resolved by manually downloading and extracting the Windows rollup binary:

```bash
# 1. Navigate to rollup directory
cd frontend/node_modules/@rollup

# 2. Download Windows binary from npm registry
curl -L https://registry.npmjs.org/@rollup/rollup-win32-x64-msvc/-/rollup-win32-x64-msvc-4.53.5.tgz -o rollup-win32.tgz

# 3. Extract and setup
tar -xzf rollup-win32.tgz
mv package rollup-win32-x64-msvc
rm rollup-win32.tgz
```

### Verification

```bash
# Tests now execute successfully
cd frontend
npm test -- --run src/utils/sanitize.spec.ts

# Result: 32/32 tests PASSING (100%)
```

### Root Cause Analysis

The npm bug (issue #4828) causes npm to ignore platform detection for optional dependencies on Windows, installing Linux binaries instead. The workaround bypasses npm's dependency resolution by manually placing the correct binary in node_modules.

### Impact Resolution

- ✅ Tests can now run successfully
- ✅ DOMPurify integration validated (32/32 tests passing)
- ✅ Story 11.8d test development unblocked
- ✅ Future test execution enabled

### Notes for Future Developers

1. **Temporary Workaround**: This manual installation may need to be repeated after `npm install` or `npm ci`
2. **Long-term Solution**: Monitor npm issue #4828 for official fix
3. **Alternative**: Consider using WSL2 or Linux environment for development to avoid Windows-specific npm bugs
4. **Automation**: Consider adding a post-install script to automate this workaround

## Timeline

- **Reported**: 2025-12-18
- **Resolved**: 2025-12-18
- **Resolution Time**: ~2 hours
- **Resolved By**: Alex (DevOps Infrastructure Specialist)

## Story Impact (RESOLVED)

Story 11.8d: Test Refinements & Security Enhancements

- ✅ DOMPurify integration tests validated (32/32 passing)
- ✅ Test execution infrastructure operational
- ✅ Ready to proceed with component test fixes (Tasks 1-7)
