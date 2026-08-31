from pathlib import Path

from catl_quant.config import load_config


def test_research_cutoff_is_summer_2025() -> None:
    config = load_config(Path("config/research.yaml"))
    assert config.as_of == "2025-08-29"
    assert config.raw["project"]["focal_symbol"] == "300750"

