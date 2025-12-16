#!/usr/bin/env python3
"""Update story status to Done for epics 0-11"""

import os
import re
from pathlib import Path

def update_story_status(file_path):
    """Update Status field to Done in a story file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    updated = False
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for "## Status" heading
        if re.match(r'^##\s+Status\s*$', line.strip()):
            new_lines.append(line)
            # Next line should be the status value
            if i + 1 < len(lines):
                i += 1
                current_status = lines[i].strip()
                # Replace with "Done" if not already
                if current_status != 'Done':
                    new_lines.append('Done\n')
                    updated = True
                else:
                    new_lines.append(lines[i])
            i += 1
            continue

        # Also handle inline "Status: <value>" format
        if re.match(r'^Status:\s*', line):
            new_status = re.sub(r'^Status:.*$', 'Status: Done', line.rstrip())
            new_lines.append(new_status + '\n')
            if line.rstrip() != new_status:
                updated = True
            i += 1
            continue

        new_lines.append(line)
        i += 1

    if updated:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        return True
    return False

def main():
    stories_dir = Path('docs/stories')
    updated_count = 0
    already_done_count = 0

    # Process epics 0-11
    for epic_num in list(range(10)) + [10, 11]:
        epic_dir = stories_dir / f'epic-{epic_num}'
        if not epic_dir.exists():
            continue

        # Find all story files (numbered files like X.Y.*.md)
        for story_file in epic_dir.glob('*.md'):
            # Only process files that start with a number
            if re.match(r'^\d+\.', story_file.name):
                if update_story_status(story_file):
                    print(f"Updated: {story_file}")
                    updated_count += 1
                else:
                    already_done_count += 1

    print(f"\nTotal files updated: {updated_count}")
    print(f"Files already 'Done': {already_done_count}")
    print(f"Total files processed: {updated_count + already_done_count}")

if __name__ == '__main__':
    main()
