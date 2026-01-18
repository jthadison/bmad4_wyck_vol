#!/usr/bin/env node

/**
 * Third Pass: TypeScript `any` Type Cleanup Script - Test File Specifics
 *
 * Handles test-specific patterns:
 * 1. let pinia: any
 * 2. let wrapper: any
 * 3. let store: any
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const FRONTEND_DIR = path.join(__dirname, 'frontend');

// Test-specific replacements
const replacements = [
  {
    pattern: /let pinia:\s*any/g,
    replacement: 'let pinia: ReturnType<typeof createPinia>',
    needsImport: "import { createPinia } from 'pinia'",
    description: 'let pinia: any → let pinia: ReturnType<typeof createPinia>'
  },
  {
    pattern: /let wrapper:\s*any/g,
    replacement: 'let wrapper: ReturnType<typeof mount>',
    description: 'let wrapper: any → let wrapper: ReturnType<typeof mount>'
  },
  {
    pattern: /let store:\s*any/g,
    replacement: 'let store: unknown',
    description: 'let store: any → let store: unknown'
  },
  {
    pattern: /const wrapper:\s*any/g,
    replacement: 'const wrapper: ReturnType<typeof mount>',
    description: 'const wrapper: any → const wrapper: ReturnType<typeof mount>'
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

  for (const { pattern, replacement, needsImport, description } of replacements) {
    const matches = modified.match(pattern);
    if (matches && matches.length > 0) {
      modified = modified.replace(pattern, replacement);

      // Add import if needed and not present
      if (needsImport && !modified.includes(needsImport)) {
        // Find the import section and add it
        const importMatch = modified.match(/^import\s+/m);
        if (importMatch) {
          const insertPos = modified.indexOf(importMatch[0]);
          modified = modified.slice(0, insertPos) + needsImport + '\n' + modified.slice(insertPos);
        }
      }

      changesMade.push(`  - ${description} (${matches.length} occurrences)`);
    }
  }

  return { modified, changesMade };
}

function main() {
  console.log('🔍 TypeScript any Type Cleanup Script - PASS 3 (Test Files)\n');
  console.log('Scanning test files...\n');

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

    if (remaining === 0) {
      console.log('\n🎉 All any types have been eliminated!');
    }
  } catch (err) {
    console.log('✅ All violations fixed!');
  }
}

if (require.main === module) {
  main();
}
