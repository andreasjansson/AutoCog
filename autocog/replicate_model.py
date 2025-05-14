import copy
import datetime
from typing import Any
import replicate
from replicate.exceptions import ReplicateError
from replicate.version import Version
from toololo import log

from . import cog


class ReplicateModel:
    def __init__(self, model_name: str, hardware: str, replicate_token: str | None):
        self.model_name = model_name  # <owner>/<name>
        self.hardware = hardware
        self.replicate_token = replicate_token

    def cog_push(self) -> dict[str, Any]:
        """
        Push a Cog model to Replicate.
        Returns the input schema of the pushed model.
        """
        if not self.exists():
            self.create()
        if self.replicate_token:
            cog.login(self.replicate_token)
        cog.push(self.model_name)

        version = self.latest_version()
        assert version, "No versions have been pushed"
        five_minutes_ago = datetime.datetime.now(
            datetime.timezone.utc
        ) - datetime.timedelta(minutes=5)

        assert version.created_at > five_minutes_ago, (
            "The latest version is older than five minutes ago, which suggests that the recent push was unsuccessful"
        )

        schema = denormalize_refs(version.openapi_schema)
        return schema["components"]["schemas"]["Input"]

    def exists(self) -> bool:
        try:
            replicate.models.get(self.model_name)
            return True
        except ReplicateError as e:
            if e.status == 404:
                return False
            raise

    def create(self) -> None:
        log.info(
            f"Creating private model {self.model_name} with hardware {self.hardware}"
        )
        owner, name = self.model_name.split("/")
        replicate.models.create(
            owner=owner,
            name=name,
            visibility="private",
            hardware=self.hardware,
        )

    def latest_version(self) -> Version:
        version = replicate.models.get(self.model_name).latest_version
        assert version
        return version

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        prediction = replicate.predictions.create(
            version=self.latest_version(), input=inputs
        )
        log.info(f"Running https://replicate.com/p/{prediction.id}")
        prediction.wait()
        if prediction.status == "failed":
            raise Exception(
                f"Prediction failed.\n\nError: {prediction.error}\n\nLogs:\n{prediction.logs}"
            )
        return {
            "prediction_id": prediction.id,
            "output": prediction.output,
        }


def denormalize_refs(schema: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(schema)

    # Build a reference lookup table
    ref_map: dict[str, Any] = {}
    for name, component in result["components"]["schemas"].items():
        ref_map[f"#/components/schemas/{name}"] = component

    # Function to recursively resolve references
    def resolve_refs(obj: Any) -> Any:
        if isinstance(obj, dict):
            if "$ref" in obj and obj["$ref"] in ref_map:
                # Replace with a deep copy of the referenced object
                replacement = copy.deepcopy(ref_map[obj["$ref"]])
                # Process any nested refs in the replacement
                return resolve_refs(replacement)

            # Process all dictionary values
            return {k: resolve_refs(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            # Process all list items
            return [resolve_refs(item) for item in obj]
        return obj

    # Resolve all references in the schema
    return resolve_refs(result)
