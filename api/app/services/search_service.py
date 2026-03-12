"""Azure AI Search service for full-text search across images and bundles."""

from __future__ import annotations

from typing import Any

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient


class SearchService:
    """Wraps the Azure AI Search SDK for querying the Stearman index."""

    def __init__(self, endpoint: str, key: str, index_name: str) -> None:
        self._client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(key),
        )

    def search(
        self,
        query: str,
        *,
        index_type: str | None = None,
        folder_id: int | None = None,
        top: int = 50,
        skip: int = 0,
    ) -> dict[str, Any]:
        """Execute a full-text search.

        Args:
            query: User search text.
            index_type: Optional filter -- ``"drawing"`` or ``"keyword"``.
            folder_id: Optional folder ID filter.
            top: Maximum results to return.
            skip: Number of results to skip (for pagination).

        Returns:
            Dict with ``results`` (list of hit dicts) and ``total_count``.
        """
        filter_parts: list[str] = []
        if index_type == "drawing":
            filter_parts.append("index_type eq 'Drawing #'")
        elif index_type == "keyword":
            filter_parts.append("index_type eq 'Key Word'")
        if folder_id is not None:
            filter_parts.append(f"folder_id eq {folder_id}")

        filter_expression = " and ".join(filter_parts) if filter_parts else None

        response = self._client.search(
            search_text=query,
            filter=filter_expression,
            top=top,
            skip=skip,
            include_total_count=True,
        )

        results: list[dict[str, Any]] = []
        for result in response:
            results.append({
                "id": result.get("id"),
                "entity_type": result.get("entity_type"),
                "title": result.get("title"),
                "drawing_number": result.get("drawing_number"),
                "keyword": result.get("keyword"),
                "folder_name": result.get("folder_name"),
                "thumbnail_url": result.get("thumbnail_url"),
                "score": result.get("@search.score"),
            })

        return {
            "results": results,
            "total_count": response.get_count() or len(results),
        }

    def suggest(self, query: str, *, top: int = 10) -> list[dict[str, Any]]:
        """Return autocomplete suggestions for the given partial query.

        Args:
            query: Partial search text.
            top: Maximum number of suggestions.

        Returns:
            List of suggestion dicts with ``text`` and ``id``.
        """
        response = self._client.suggest(
            search_text=query,
            suggester_name="sg",
            top=top,
        )
        return [
            {"text": item.get("@search.text", ""), "id": item.get("id")}
            for item in response
        ]
