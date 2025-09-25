"""Prompt templates for AI-based test case generation."""

from .new_feature_prompts import NewFeaturePrompts
from .feature_update_prompts import FeatureUpdatePrompts
from .bug_fix_prompts import BugFixPrompts

__all__ = [
    "NewFeaturePrompts",
    "FeatureUpdatePrompts", 
    "BugFixPrompts"
]
