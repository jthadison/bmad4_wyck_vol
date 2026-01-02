"""Quick script to fix all test functions to use async_client fixture."""
import re

file_path = r"backend\tests\integration\test_backtest_integration.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern 1: Function signatures - add async_client parameter
content = re.sub(
    r'(@pytest\.mark\.asyncio\nasync def test_\w+)\(\):',
    r'\1(async_client: AsyncClient):',
    content
)

# Pattern 2: Remove manual AsyncClient creation blocks
content = re.sub(
    r'    transport = ASGITransport\(app=app\)\n    async with AsyncClient\(transport=transport, base_url="http://test"\) as client:\n',
    '',
    content
)

# Pattern 3: Replace 'client.' with 'async_client.'
content = re.sub(r'\bclient\.', 'async_client.', content)

# Pattern 4: Fix indentation - lines that were inside 'async with' block
lines = content.split('\n')
fixed_lines = []
in_test_function = False
needs_dedent = False

for i, line in enumerate(lines):
    if line.strip().startswith('async def test_'):
        in_test_function = True
        needs_dedent = False
        fixed_lines.append(line)
    elif in_test_function and (line.strip().startswith('"""') and line.count('"""') == 2):
        # Docstring on same line
        fixed_lines.append(line)
    elif in_test_function and line.strip().startswith('"""'):
        # Start of multiline docstring
        fixed_lines.append(line)
    elif in_test_function and '"""' in line and not line.strip().startswith('"""'):
        # End of multiline docstring
        fixed_lines.append(line)
        needs_dedent = True
    elif needs_dedent and line.startswith('        ') and not line.strip().startswith('#'):
        # Remove 4 spaces of indentation
        fixed_lines.append(line[4:])
    else:
        fixed_lines.append(line)
        if line.strip() == '' or line.strip().startswith('@'):
            in_test_function = False
            needs_dedent = False

print(f"Writing fixed content to {file_path}")
with open(file_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(fixed_lines))

print("Done!")
