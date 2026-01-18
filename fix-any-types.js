#!/usr/bin/env node

/**
 * Automated TypeScript `any` Type Cleanup Script
 *
 * Fixes common `any` type violations in test files:
 * 1. catch (err: any) → catch (err: unknown)
 * 2. const obj: any = {} → const obj: Record<string, unknown> = {}
 * 3. function(param: any) → function(param: unknown)
 * 4. as any → as unknown
 * 5. Mock object properties
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const FRONTEND_DIR = path.join(__dirname, 'frontend');

// Pattern replacements
const replacements = [
  // Pattern 1: catch blocks
  {
    pattern: /catch\s*\(\s*(\w+)\s*:\s*any\s*\)/g,
    replacement: 'catch ($1: unknown)',
    description: 'catch (err: any) → catch (err: unknown)'
  },

  // Pattern 2: const/let/var with any object
  {
    pattern: /\b(const|let|var)\s+(\w+)\s*:\s*any\s*=\s*\{/g,
    replacement: '$1 $2: Record<string, unknown> = {',
    description: 'const obj: any = {} → const obj: Record<string, unknown> = {}'
  },

  // Pattern 3: as any (standalone)
  {
    pattern: /\bas\s+any\b/g,
    replacement: 'as unknown',
    description: 'as any → as unknown'
  },

  // Pattern 4: function parameters (simple cases)
  {
    pattern: /\((\w+)\s*:\s*any\s*\)/g,
    replacement: '($1: unknown)',
    description: '(param: any) → (param: unknown)'
  },

  // Pattern 5: arrow function parameters
  {
    pattern: /\(\s*(\w+)\s*:\s*any\s*\)\s*=>/g,
    replacement: '($1: unknown) =>',
    description: '(param: any) => → (param: unknown) =>'
  },

  // Pattern 6: type annotations in declarations
  {
    pattern: /:\s*any\[\]/g,
    replacement: ': unknown[]',
    description: ': any[] → : unknown[]'
  },

  // Pattern 7: Mock function properties (common in tests)
  {
    pattern: /(\w+)\s*:\s*\(\s*\.\.\.\s*args\s*:\s*any\[\]\s*\)\s*=>/g,
    replacement: '$1: (...args: unknown[]) =>',
    description: 'mockFn: (...args: any[]) => → mockFn: (...args: unknown[]) =>'
  },
];

function getAllTestFiles(dir) {
  const files = [];

  function traverse(currentDir) {
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);

      if (entry.isDirectory()) {
        traverse(fullPath);
      } else if (entry.isFile() && (entry.name.endsWith('.spec.ts') || entry.name.endsWith('.test.ts'))) {
        files.push(fullPath);
      }
    }
  }

  traverse(dir);
  return files;
}

function applyReplacements(content, filePath) {
  let modified = content;
  let changesMade = [];

  for (const { pattern, replacement, description } of replacements) {
    const matches = modified.match(pattern);
    if (matches && matches.length > 0) {
      modified = modified.replace(pattern, replacement);
      changesMade.push(`  - ${description} (${matches.length} occurrences)`);
    }
  }

  return { modified, changesMade };
}

function main() {
  console.log('🔍 TypeScript any Type Cleanup Script\n');
  console.log('Scanning test files in frontend/tests...\n');

  const testsDir = path.join(FRONTEND_DIR, 'tests');
  const testFiles = getAllTestFiles(testsDir);

  console.log(`Found ${testFiles.length} test files\n`);

  let totalFiles = 0;
  let totalChanges = 0;
  const fileChanges = [];

  for (const filePath of testFiles) {
    const content = fs.readFileSync(filePath, 'utf8');
    const { modified, changesMade } = applyReplacements(content, filePath);

    if (modified !== content) {
      fs.writeFileSync(filePath, modified, 'utf8');
      totalFiles++;
      totalChanges += changesMade.length;

      const relativePath = path.relative(FRONTEND_DIR, filePath);
      fileChanges.push({
        file: relativePath,
        changes: changesMade
      });
    }
  }

  console.log('✅ Cleanup Complete!\n');
  console.log(`Modified ${totalFiles} files`);
  console.log(`Applied ${totalChanges} pattern replacements\n`);

  if (fileChanges.length > 0) {
    console.log('Changes by file:');
    for (const { file, changes } of fileChanges) {
      console.log(`\n📄 ${file}`);
      changes.forEach(change => console.log(change));
    }
  }

  // Run linter to check remaining violations
  console.log('\n🔍 Checking remaining violations...\n');
  try {
    const result = execSync('npm run lint 2>&1 | grep -c "no-explicit-any"', {
      cwd: FRONTEND_DIR,
      encoding: 'utf8'
    });
    const remaining = parseInt(result.trim()) || 0;
    console.log(`Remaining any violations: ${remaining}`);

    if (remaining > 0) {
      console.log('\n💡 Tip: Run the script multiple times or manually fix remaining cases');
    } else {
      console.log('\n🎉 All any types have been eliminated!');
    }
  } catch (err) {
    console.log('⚠️  Could not count remaining violations (this is normal if all are fixed)');
  }
}

if (require.main === module) {
  main();
}
