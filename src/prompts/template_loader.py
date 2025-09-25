"""Template loader for Jinja2 templates."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, Template


class TemplateLoader:
    """Loads and renders Jinja2 templates."""
    
    def __init__(self, template_dir: Optional[Path] = None):
        """Initialize template loader.
        
        Args:
            template_dir: Directory containing template files. 
                         Defaults to src/prompts/templates/
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a template with the given context.
        
        Args:
            template_name: Name of the template file (e.g., "new_feature/controlled_generation_variant.md.j2")
            context: Dictionary of variables to pass to the template
            
        Returns:
            Rendered template as string
            
        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        template = self.env.get_template(template_name)
        return template.render(**context)


_template_loader = None

def get_template_loader() -> TemplateLoader:
    """Get the global template loader instance."""
    global _template_loader
    if _template_loader is None:
        _template_loader = TemplateLoader()
    return _template_loader

def render_template(template_name: str, context: Dict[str, Any]) -> str:
    """Convenience function to render a template.
    
    Args:
        template_name: Name of the template file
        context: Dictionary of variables to pass to the template
        
    Returns:
        Rendered template as string
    """
    loader = get_template_loader()
    return loader.render_template(template_name, context)
