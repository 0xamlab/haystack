from __future__ import annotations

from algenta.runtime_connector_model_dataset import (
    DatasetDeleteOutput,
    DatasetDetail,
    DatasetList,
    DatasetSelectionSummary,
    DatasetSummary,
)


class RuntimeDatasetSurfaceMixin:
    def _dataset_page(
        self,
        *,
        page: int,
        limit: int,
        search: str | None = None,
        status: str | None = None,
        source_name: str | None = None,
        compact: bool = False,
    ) -> DatasetList:
        cache_key = self._api_cache_key(
            "datasets",
            "list",
            page,
            limit,
            search or "",
            status or "",
            source_name or "",
            int(compact),
        )
        cached = self._get_api_surface_cache(cache_key)
        if isinstance(cached, DatasetList):
            return cached
        request_kwargs: dict[str, object] = {"page": page, "limit": limit}
        if search is not None:
            request_kwargs["search"] = search
        if status is not None:
            request_kwargs["status"] = status
        if source_name is not None:
            request_kwargs["source_name"] = source_name
        if compact:
            request_kwargs["compact"] = True
        result = self._client().list_datasets(**request_kwargs)
        payload = DatasetList.from_api(result)
        return self._put_api_surface_cache(cache_key, payload)

    def list_datasets(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        search: str | None = None,
        status: str | None = None,
        source_name: str | None = None,
        compact: bool = False,
        all_pages: bool = False,
        max_items: int | None = None,
    ) -> DatasetList | list[DatasetSummary]:
        self._require_api_transport("list_datasets")
        if not all_pages:
            listing = self._dataset_page(
                page=page,
                limit=limit,
                search=search,
                status=status,
                source_name=source_name,
                compact=compact,
            )
            if max_items is None or max_items >= len(listing.datasets):
                return listing
            return DatasetList(
                datasets=listing.datasets[:max_items],
                count=min(listing.count, max_items),
                total=listing.total,
                matched_total=listing.matched_total,
                page=listing.page,
                limit=listing.limit,
                pages=listing.pages,
            )
        return list(
            self.iter_datasets(
                page=page,
                limit=limit,
                search=search,
                status=status,
                source_name=source_name,
                compact=compact,
                max_items=max_items,
            )
        )

    def iter_datasets(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        search: str | None = None,
        status: str | None = None,
        source_name: str | None = None,
        compact: bool = False,
        max_items: int | None = None,
    ):
        self._require_api_transport("iter_datasets")

        def fetch_page(*, page: int, limit: int) -> tuple[list[DatasetSummary], int]:
            listing = self._dataset_page(
                page=page,
                limit=limit,
                search=search,
                status=status,
                source_name=source_name,
                compact=compact,
            )
            return listing.datasets, listing.pages

        yield from self._iter_api_page_items(
            start_page=page,
            limit=limit,
            max_items=max_items,
            fetch_page=fetch_page,
        )

    def get_dataset(self, dataset_id: str) -> DatasetDetail:
        self._require_api_transport("get_dataset")
        cache_key = self._api_cache_key("datasets", "get", dataset_id)
        cached = self._get_api_surface_cache(cache_key)
        if isinstance(cached, DatasetDetail):
            return cached
        result = DatasetDetail.from_api(self._client().get_dataset(dataset_id))
        return self._put_api_surface_cache(cache_key, result)

    def get_dataset_summary(self, dataset_id: str) -> DatasetSelectionSummary:
        self._require_api_transport("get_dataset_summary")
        cache_key = self._api_cache_key("datasets", "summary", dataset_id)
        cached = self._get_api_surface_cache(cache_key)
        if isinstance(cached, DatasetSelectionSummary):
            return cached
        result = DatasetSelectionSummary.from_api(self._client().get_dataset_summary(dataset_id))
        return self._put_api_surface_cache(cache_key, result)

    def refresh_dataset(self, dataset_id: str):
        self._require_api_transport("refresh_dataset")
        result = self._client().refresh_dataset(dataset_id)
        registration = self._source_registration_from_api(result)
        self._remember_api_registration(registration)
        self._invalidate_api_surface_cache(
            "datasets:list:",
            self._api_cache_key("datasets", "get", dataset_id),
            self._api_cache_key("datasets", "summary", dataset_id),
        )
        return registration

    def delete_dataset(self, dataset_id: str) -> DatasetDeleteOutput:
        self._require_api_transport("delete_dataset")
        result = DatasetDeleteOutput.from_api(self._client().delete_dataset(dataset_id))
        self._forget_api_registration(dataset_id)
        self._invalidate_api_surface_cache(
            "datasets:list:",
            self._api_cache_key("datasets", "get", dataset_id),
            self._api_cache_key("datasets", "summary", dataset_id),
        )
        return result

    disconnect_dataset = delete_dataset
