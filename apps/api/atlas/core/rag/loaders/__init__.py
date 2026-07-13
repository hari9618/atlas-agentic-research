"""Document loaders that produce ``Document`` objects for ingestion."""

from .files import load_corpus_dir

__all__ = ["load_corpus_dir"]
