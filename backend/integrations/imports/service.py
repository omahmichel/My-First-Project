from django.core import signing
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from integrations.models import DataImport

from .mappings import build_header_mapping, map_rows
from .parsers import parse_uploaded_table
from .validation import (
    ACTION_CREATE,
    ACTION_ERROR,
    ACTION_SKIP,
    ACTION_UPDATE,
    APPLIERS,
    validate_mapped_row,
)


PREVIEW_TOKEN_SALT = "stockflow.integrations.safe-import.v1"
PREVIEW_TOKEN_MAX_AGE_SECONDS = 30 * 60


def _job_payload(job):
    return {
        "id": str(job.id),
        "dataset": job.dataset,
        "fileType": job.file_type,
        "filename": job.original_filename,
        "status": job.status,
        "branch": (
            {
                "id": str(job.branch_id_snapshot),
                "name": job.branch_name_snapshot,
                "code": job.branch_code_snapshot,
            }
            if job.branch_id_snapshot
            else None
        ),
        "rowCount": job.row_count,
        "validCount": job.valid_count,
        "errorCount": job.error_count,
        "createCount": job.create_count,
        "updateCount": job.update_count,
        "skipCount": job.skip_count,
        "createdAt": job.created_at,
        "appliedAt": job.applied_at,
    }


def list_import_audits(*, business):
    return [_job_payload(job) for job in business.data_imports.all()[:50]]


def create_import_preview(*, business, branch, dataset, upload, user, request):
    parsed = parse_uploaded_table(upload)
    mapping, columns = build_header_mapping(dataset, parsed["headers"])
    mapped_rows = map_rows(parsed["rows"], columns)

    preview_rows = []
    for offset, row in enumerate(mapped_rows, start=2):
        preview_rows.append(
            validate_mapped_row(
                dataset=dataset,
                row=row,
                row_number=offset,
                business=business,
                branch=branch,
                request=request,
            )
        )

    counts = {
        ACTION_CREATE: 0,
        ACTION_UPDATE: 0,
        ACTION_SKIP: 0,
        ACTION_ERROR: 0,
    }
    for row in preview_rows:
        counts[row["action"]] += 1

    job = DataImport.objects.create(
        business=business,
        dataset=dataset,
        file_type=parsed["fileType"],
        original_filename=parsed["filename"],
        file_sha256=parsed["sha256"],
        branch_id_snapshot=(branch.id if branch else None),
        branch_name_snapshot=(branch.name if branch else ""),
        branch_code_snapshot=(branch.code if branch else ""),
        header_mapping=mapping,
        row_count=len(preview_rows),
        valid_count=len(preview_rows) - counts[ACTION_ERROR],
        error_count=counts[ACTION_ERROR],
        create_count=counts[ACTION_CREATE],
        update_count=counts[ACTION_UPDATE],
        skip_count=counts[ACTION_SKIP],
        created_by=user,
    )

    token = None
    if job.error_count == 0:
        token = signing.dumps(
            {
                "importId": str(job.id),
                "businessId": str(business.id),
                "dataset": dataset,
                "branchId": str(branch.id) if branch else None,
                "sha256": parsed["sha256"],
                "rows": preview_rows,
            },
            salt=PREVIEW_TOKEN_SALT,
            compress=True,
        )

    public_rows = []
    for row in preview_rows:
        public_rows.append(
            {
                "rowNumber": row["rowNumber"],
                "action": row["action"],
                "data": row["data"],
                "errors": row["errors"],
                "matchId": row["matchId"],
            }
        )

    return {
        "import": _job_payload(job),
        "mapping": mapping,
        "rows": public_rows,
        "previewToken": token,
        "safety": {
            "businessRecordsChanged": False,
            "auditRecordCreated": True,
            "requiresExplicitApply": True,
            "previewTokenExpiresMinutes": 30,
            "sourceFileStored": False,
        },
    }


def _load_token(token):
    try:
        return signing.loads(
            token,
            salt=PREVIEW_TOKEN_SALT,
            max_age=PREVIEW_TOKEN_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired as exc:
        raise serializers.ValidationError(
            {"previewToken": "This import preview expired. Preview the file again."}
        ) from exc
    except signing.BadSignature as exc:
        raise serializers.ValidationError(
            {"previewToken": "The import preview token is invalid. Preview the file again."}
        ) from exc


@transaction.atomic
def apply_import_preview(*, business, import_id, preview_token, user, request):
    job = DataImport.objects.select_for_update().filter(
        id=import_id,
        business=business,
    ).first()
    if not job:
        raise serializers.ValidationError({"import": "Import preview not found."})
    if job.status == DataImport.Status.APPLIED:
        raise serializers.ValidationError({"import": "This import has already been applied."})
    if job.error_count:
        raise serializers.ValidationError(
            {"import": "Fix the preview errors and upload the file again before applying."}
        )

    payload = _load_token(preview_token)
    expected = {
        "importId": str(job.id),
        "businessId": str(business.id),
        "dataset": job.dataset,
        "branchId": str(job.branch_id_snapshot) if job.branch_id_snapshot else None,
        "sha256": job.file_sha256,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise serializers.ValidationError(
                {"previewToken": "The preview token does not match this import. Preview the file again."}
            )

    branch = None
    if job.branch_id_snapshot:
        branch = business.branches.filter(
            id=job.branch_id_snapshot,
            is_active=True,
        ).first()
        if not branch:
            raise serializers.ValidationError(
                {"branchId": "The selected branch is no longer active. Preview the file again."}
            )
        if (
            branch.name != job.branch_name_snapshot
            or branch.code != job.branch_code_snapshot
        ):
            raise serializers.ValidationError(
                {"branchId": "The selected branch changed after preview. Preview the file again."}
            )

    applier = APPLIERS[job.dataset]
    actual = {
        ACTION_CREATE: 0,
        ACTION_UPDATE: 0,
        ACTION_SKIP: 0,
    }
    for entry in payload.get("rows", []):
        if entry.get("action") == ACTION_ERROR:
            raise serializers.ValidationError(
                {"import": "An invalid row was found in the signed preview."}
            )
        action = applier(
            entry=entry,
            business=business,
            branch=branch,
            user=user,
            request=request,
        )
        actual[action] += 1

    job.status = DataImport.Status.APPLIED
    job.create_count = actual[ACTION_CREATE]
    job.update_count = actual[ACTION_UPDATE]
    job.skip_count = actual[ACTION_SKIP]
    job.applied_by = user
    job.applied_at = timezone.now()
    job.save(
        update_fields=(
            "status",
            "create_count",
            "update_count",
            "skip_count",
            "applied_by",
            "applied_at",
            "updated_at",
        )
    )
    return {
        "import": _job_payload(job),
        "applied": True,
        "safety": {
            "atomic": True,
            "partialApplyAllowed": False,
        },
    }
