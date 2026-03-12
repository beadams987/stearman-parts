"""Azure Blob Storage service for image retrieval and upload."""

from datetime import UTC, datetime, timedelta

from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContentSettings,
    generate_blob_sas,
)


class BlobService:
    """Manages access to images stored in Azure Blob Storage."""

    def __init__(self, connection_string: str, container_name: str) -> None:
        self._connection_string = connection_string
        self._container_name = container_name
        self._service_client = BlobServiceClient.from_connection_string(connection_string)
        self._container_client = self._service_client.get_container_client(container_name)

    def _generate_sas_url(self, blob_path: str, expiry_hours: int = 1) -> str:
        """Generate a read-only SAS URL for a blob.

        Args:
            blob_path: Path to the blob within the container.
            expiry_hours: Number of hours the URL remains valid.

        Returns:
            Full URL with SAS token appended.
        """
        account_name = self._service_client.account_name
        account_key = self._service_client.credential.account_key

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=self._container_name,
            blob_name=blob_path,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(UTC) + timedelta(hours=expiry_hours),
        )

        blob_client = self._container_client.get_blob_client(blob_path)
        return f"{blob_client.url}?{sas_token}"

    def get_image_url(self, blob_path: str) -> str:
        """Return a time-limited SAS URL for a full-resolution image.

        The URL is valid for 1 hour.
        """
        return self._generate_sas_url(blob_path, expiry_hours=1)

    def get_thumbnail_url(self, blob_path: str) -> str:
        """Return a time-limited SAS URL for a thumbnail image.

        The URL is valid for 1 hour.
        """
        return self._generate_sas_url(blob_path, expiry_hours=1)

    def upload_blob(self, blob_path: str, data: bytes, content_type: str) -> str:
        """Upload binary data to a blob and return its URL.

        Args:
            blob_path: Destination path within the container.
            data: Raw bytes to upload.
            content_type: MIME type for the blob (e.g. ``image/tiff``).

        Returns:
            URL of the uploaded blob (without SAS token).
        """
        blob_client = self._container_client.get_blob_client(blob_path)
        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return blob_client.url
