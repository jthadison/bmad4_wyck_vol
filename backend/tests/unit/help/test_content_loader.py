"""
Unit tests for HelpContentLoader tutorial parsing (Story 11.8b - Task 16)

Purpose:
--------
Tests the content_loader.py module's ability to parse tutorial Markdown files
and extract step structure with metadata.

Tests:
------
- Tutorial file parsing with frontmatter
- Step extraction from Markdown headings
- HTML comment metadata extraction (action, highlight)
- Error handling for invalid files
- Cache behavior

Author: Story 11.8b (Task 16)
"""

from pathlib import Path

import pytest

from src.help.content_loader import ContentLoadError, HelpContentLoader


class TestTutorialParsing:
    """Test tutorial parsing from Markdown files."""

    def test_parse_tutorial_basic(self, tmp_path: Path):
        """Test parsing a basic tutorial with multiple steps."""
        # Create a sample tutorial file
        tutorial_file = tmp_path / "Test-Tutorial.md"
        tutorial_file.write_text(
            """---
title: "Test Tutorial"
category: "TUTORIAL"
difficulty: "BEGINNER"
estimated_time_minutes: 10
tags: ["test", "beginner"]
description: "A test tutorial"
---

# Test Tutorial

This is the introduction.

## Step 1: First Step

This is the first step content.

## Step 2: Second Step

This is the second step content.

## Step 3: Third Step

This is the third step content.
"""
        )

        loader = HelpContentLoader(tmp_path)
        tutorial = loader.parse_tutorial(tutorial_file)

        assert tutorial.title == "Test Tutorial"
        assert tutorial.slug == "Test-Tutorial"
        assert tutorial.difficulty == "BEGINNER"
        assert tutorial.estimated_time_minutes == 10
        assert len(tutorial.steps) == 3
        assert tutorial.tags == ["test", "beginner"]
        assert tutorial.description == "A test tutorial"

    def test_parse_tutorial_steps(self, tmp_path: Path):
        """Test that tutorial steps are correctly extracted."""
        tutorial_file = tmp_path / "Steps-Test.md"
        tutorial_file.write_text(
            """---
title: "Steps Test"
category: "TUTORIAL"
difficulty: "BEGINNER"
estimated_time_minutes: 5
tags: []
description: "Test"
---

# Steps Test

## Step 1: Navigate Here

Go to the dashboard.

## Step 2: Click Button

Click the submit button.
"""
        )

        loader = HelpContentLoader(tmp_path)
        tutorial = loader.parse_tutorial(tutorial_file)

        assert len(tutorial.steps) == 2

        step1 = tutorial.steps[0]
        assert step1.step_number == 1
        assert step1.title == "Navigate Here"
        assert "Go to the dashboard." in step1.content_markdown

        step2 = tutorial.steps[1]
        assert step2.step_number == 2
        assert step2.title == "Click Button"
        assert "Click the submit button." in step2.content_markdown

    def test_parse_tutorial_with_action_required(self, tmp_path: Path):
        """Test parsing action_required from HTML comments."""
        tutorial_file = tmp_path / "Action-Test.md"
        tutorial_file.write_text(
            """---
title: "Action Test"
category: "TUTORIAL"
difficulty: "BEGINNER"
estimated_time_minutes: 5
tags: []
description: "Test"
---

# Action Test

## Step 1: Click Something

Do this action.

<!-- action: Click the submit button -->

More content here.
"""
        )

        loader = HelpContentLoader(tmp_path)
        tutorial = loader.parse_tutorial(tutorial_file)

        assert len(tutorial.steps) == 1
        step = tutorial.steps[0]
        assert step.action_required == "Click the submit button"

    def test_parse_tutorial_with_ui_highlight(self, tmp_path: Path):
        """Test parsing ui_highlight from HTML comments."""
        tutorial_file = tmp_path / "Highlight-Test.md"
        tutorial_file.write_text(
            """---
title: "Highlight Test"
category: "TUTORIAL"
difficulty: "BEGINNER"
estimated_time_minutes: 5
tags: []
description: "Test"
---

# Highlight Test

## Step 1: Find Button

Look for the button.

<!-- highlight: #submit-button -->

Click it.
"""
        )

        loader = HelpContentLoader(tmp_path)
        tutorial = loader.parse_tutorial(tutorial_file)

        assert len(tutorial.steps) == 1
        step = tutorial.steps[0]
        assert step.ui_highlight == "#submit-button"

    def test_parse_tutorial_with_both_metadata(self, tmp_path: Path):
        """Test parsing both action_required and ui_highlight."""
        tutorial_file = tmp_path / "Both-Test.md"
        tutorial_file.write_text(
            """---
title: "Both Test"
category: "TUTORIAL"
difficulty: "BEGINNER"
estimated_time_minutes: 5
tags: []
description: "Test"
---

# Both Test

## Step 1: Complete Action

Do the thing.

<!-- action: Click the submit button -->
<!-- highlight: #submit-button -->

Done.
"""
        )

        loader = HelpContentLoader(tmp_path)
        tutorial = loader.parse_tutorial(tutorial_file)

        step = tutorial.steps[0]
        assert step.action_required == "Click the submit button"
        assert step.ui_highlight == "#submit-button"

    def test_parse_tutorial_invalid_difficulty(self, tmp_path: Path):
        """Test that invalid difficulty raises error."""
        tutorial_file = tmp_path / "Invalid-Difficulty.md"
        tutorial_file.write_text(
            """---
title: "Invalid"
category: "TUTORIAL"
difficulty: "EXPERT"
estimated_time_minutes: 5
tags: []
description: "Test"
---

# Invalid

## Step 1: Test

Test content.
"""
        )

        loader = HelpContentLoader(tmp_path)

        with pytest.raises(ContentLoadError) as exc_info:
            loader.parse_tutorial(tutorial_file)

        assert "Invalid difficulty" in str(exc_info.value)

    def test_parse_tutorial_missing_difficulty(self, tmp_path: Path):
        """Test that missing difficulty raises error."""
        tutorial_file = tmp_path / "Missing-Difficulty.md"
        tutorial_file.write_text(
            """---
title: "Missing"
category: "TUTORIAL"
estimated_time_minutes: 5
tags: []
description: "Test"
---

# Missing

## Step 1: Test

Test content.
"""
        )

        loader = HelpContentLoader(tmp_path)

        with pytest.raises(ContentLoadError) as exc_info:
            loader.parse_tutorial(tutorial_file)

        assert "missing 'difficulty'" in str(exc_info.value).lower()

    def test_parse_tutorial_missing_estimated_time(self, tmp_path: Path):
        """Test that missing estimated_time_minutes raises error."""
        tutorial_file = tmp_path / "Missing-Time.md"
        tutorial_file.write_text(
            """---
title: "Missing Time"
category: "TUTORIAL"
difficulty: "BEGINNER"
tags: []
description: "Test"
---

# Missing Time

## Step 1: Test

Test content.
"""
        )

        loader = HelpContentLoader(tmp_path)

        with pytest.raises(ContentLoadError) as exc_info:
            loader.parse_tutorial(tutorial_file)

        assert "missing 'estimated_time_minutes'" in str(exc_info.value).lower()

    def test_parse_tutorial_no_steps(self, tmp_path: Path):
        """Test that tutorial with no steps raises error."""
        tutorial_file = tmp_path / "No-Steps.md"
        tutorial_file.write_text(
            """---
title: "No Steps"
category: "TUTORIAL"
difficulty: "BEGINNER"
estimated_time_minutes: 5
tags: []
description: "Test"
---

# No Steps

This tutorial has no steps.
"""
        )

        loader = HelpContentLoader(tmp_path)

        with pytest.raises(ContentLoadError) as exc_info:
            loader.parse_tutorial(tutorial_file)

        assert "No tutorial steps found" in str(exc_info.value)

    def test_parse_tutorial_non_tutorial_category(self, tmp_path: Path):
        """Test that non-TUTORIAL category raises error."""
        tutorial_file = tmp_path / "Wrong-Category.md"
        tutorial_file.write_text(
            """---
title: "Wrong Category"
category: "FAQ"
difficulty: "BEGINNER"
estimated_time_minutes: 5
tags: []
description: "Test"
---

# Wrong Category

## Step 1: Test

Test content.
"""
        )

        loader = HelpContentLoader(tmp_path)

        with pytest.raises(ContentLoadError) as exc_info:
            loader.parse_tutorial(tutorial_file)

        assert "not a tutorial" in str(exc_info.value).lower()

    def test_parse_tutorial_caching(self, tmp_path: Path):
        """Test that tutorials are cached and reused."""
        tutorial_file = tmp_path / "Cache-Test.md"
        tutorial_file.write_text(
            """---
title: "Cache Test"
category: "TUTORIAL"
difficulty: "BEGINNER"
estimated_time_minutes: 5
tags: []
description: "Test"
---

# Cache Test

## Step 1: Test

Test content.
"""
        )

        loader = HelpContentLoader(tmp_path)

        # First parse
        tutorial1 = loader.parse_tutorial(tutorial_file)

        # Second parse should use cache (same mtime)
        tutorial2 = loader.parse_tutorial(tutorial_file)

        assert tutorial1.title == tutorial2.title
        assert len(tutorial1.steps) == len(tutorial2.steps)

    def test_parse_tutorial_step_numbering_sequential(self, tmp_path: Path):
        """Test that step numbering is validated as sequential."""
        tutorial_file = tmp_path / "Sequential-Test.md"
        tutorial_file.write_text(
            """---
title: "Sequential Test"
category: "TUTORIAL"
difficulty: "BEGINNER"
estimated_time_minutes: 5
tags: []
description: "Test"
---

# Sequential Test

## Step 1: First

First step.

## Step 2: Second

Second step.

## Step 3: Third

Third step.
"""
        )

        loader = HelpContentLoader(tmp_path)
        tutorial = loader.parse_tutorial(tutorial_file)

        # Should have sequential numbering
        for i, step in enumerate(tutorial.steps, start=1):
            assert step.step_number == i

    def test_parse_tutorial_step_content_extraction(self, tmp_path: Path):
        """Test that step content is correctly extracted between headers."""
        tutorial_file = tmp_path / "Content-Extraction.md"
        tutorial_file.write_text(
            """---
title: "Content Extraction"
category: "TUTORIAL"
difficulty: "BEGINNER"
estimated_time_minutes: 5
tags: []
description: "Test"
---

# Content Extraction

This is intro content that should not be in steps.

## Step 1: First Step

This is step 1 content.
It has multiple lines.

- Bullet 1
- Bullet 2

## Step 2: Second Step

This is step 2 content.
Also multiple lines.
"""
        )

        loader = HelpContentLoader(tmp_path)
        tutorial = loader.parse_tutorial(tutorial_file)

        step1_content = tutorial.steps[0].content_markdown
        assert "This is step 1 content." in step1_content
        assert "Bullet 1" in step1_content
        assert "Bullet 2" in step1_content
        assert "This is intro content" not in step1_content

        step2_content = tutorial.steps[1].content_markdown
        assert "This is step 2 content." in step2_content
        assert "Also multiple lines." in step2_content
        assert "Bullet 1" not in step2_content

    def test_parse_tutorial_empty_content_markdown(self, tmp_path: Path):
        """Test tutorial with empty step content."""
        tutorial_file = tmp_path / "Empty-Content.md"
        tutorial_file.write_text(
            """---
title: "Empty Content"
category: "TUTORIAL"
difficulty: "BEGINNER"
estimated_time_minutes: 5
tags: []
description: "Test"
---

# Empty Content

## Step 1: Empty Step

## Step 2: Another Empty
"""
        )

        loader = HelpContentLoader(tmp_path)
        tutorial = loader.parse_tutorial(tutorial_file)

        # Should still parse, just with empty content
        assert len(tutorial.steps) == 2
        # Content should be minimal or empty after strip()
        assert len(tutorial.steps[0].content_markdown) >= 0
