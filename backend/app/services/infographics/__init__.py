"""AIZ Infographic Generation & Visual Compilation Layer.

Provides deterministic, air-gapped HTML/SVG/CSS infographic rendering
following the aiz-infographic 5-layer design architecture (Canvases, Snippets,
Styles, Elements, Templates).
"""

from app.services.infographics.aiz_infographic_engine import AIZInfographicEngine

__all__ = ["AIZInfographicEngine"]
