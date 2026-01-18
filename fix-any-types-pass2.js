#!/usr/bin/env node

/**
 * Second Pass: TypeScript `any` Type Cleanup Script
 *
 * Handles edge cases missed in first pass:
 * 1. catch (error: any) with different variable names
 * 2. wrapper: any = ref()
 * 3. Complex mock objects
 * 4. Vue component specific patterns
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const FRONTEND_DIR = path.join(__dirname, 'frontend');

// More aggressive pattern replacements
const replacements = [
  // Pattern 1: catch blocks with any variable name
  {
    pattern: /catch\s*\(\s*(\w+)\s*:\s*any\s*\)/g,
    replacement: 'catch ($1: unknown)',
    description: 'catch (error: any) → catch (error: unknown)'
  },

  // Pattern 2: ref/reactive with any
  {
    pattern: /=\s*ref<any>/g,
    replacement: '= ref<unknown>',
    description: '= ref<any> → = ref<unknown>'
  },

  // Pattern 3: const with explicit any type (missed before)
  {
    pattern: /\b(const|let|var)\s+(\w+):\s*any\s*=/g,
    replacement: '$1 $2: unknown =',
    description: 'const x: any = → const x: unknown ='
  },

  // Pattern 4: Type parameters
  {
    pattern: /<any>/g,
    replacement: '<unknown>',
    description: '<any> → <unknown>'
  },

  // Pattern 5: Specific to mock objects
  {
    pattern: /mockReturnValue\((\{[^}]*\})\s+as\s+unknown\)/g,
    replacement: 'mockReturnValue($1)',
    description: 'Clean up double type assertions from first pass'
  },
];

function getAllVueAndTsFiles(dir) {
  const files = [];

  function traverse(currentDir) {
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);

      if (entry.isDirectory() && !entry.name.includes('node_modules')) {
        traverse(fullPath);
      } else if (entry.isFile() && (entry.name.endsWith('.vue') || entry.name.endsWith('.ts'))) {
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
  console.log('🔍 TypeScript any Type Cleanup Script - PASS 2\n');
  console.log('Scanning all .ts and .vue files...\n');

  const srcDir = path.join(FRONTEND_DIR, 'src');
  const testsDir = path.join(FRONTEND_DIR, 'tests');

  const allFiles = [
    ...getAllVueAndTsFiles(srcDir),
    ...getAllVueAndTsFiles(testsDir)
  ];

  console.log(`Found ${allFiles.length} files\n`);

  let totalFiles = 0;
  let totalChanges = 0;
  const fileChanges = [];

  for (const filePath of allFiles) {
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
    for (const { file, changes } of fileChanges.slice(0, 20)) {
      console.log(`\n📄 ${file}`);
      changes.forEach(change => console.log(change));
    }

    if (fileChanges.length > 20) {
      console.log(`\n... and ${fileChanges.length - 20} more files`);
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
      console.log('\n💡 These require manual review for proper typing');
    } else {
      console.log('\n🎉 All any types have been eliminated!');
    }
  } catch (err) {
    console.log('✅ All violations fixed!');
  }
}

if (require.main === module) {
  main();
}
