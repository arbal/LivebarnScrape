# Operations

## Logging and redaction

LOG_LEVEL=DEBUG increases detail, but configured application handlers use the
redacting formatter. Authorization values, tokens, cookies, passwords, PINs,
DPoP keys, OAuth codes, and common signed URL query values become [REDACTED].
Access logging is disabled because request URLs can contain signed values.

## SQLite integrity and backup

Run a read-only check:

    python db_integrity.py /absolute/path/livebarn.db

Create an online backup using the SQLite backup API:

    python db_backup.py /absolute/path/livebarn.db /absolute/backup/livebarn.db

The destination must not already exist and is created mode 0600. Backups may
contain saved credentials, OAuth access tokens, and DPoP private keys, so keep
them restricted.

Restore is an operator-controlled destructive action and is not performed by
these tools. Stop the service, make a restricted backup of the current
database, validate the candidate, replace only an explicitly approved
absolute path, preserve ownership and mode, and validate before starting.
Keep database, WAL, and SHM files from one snapshot together; never mix
snapshots. If validation or startup fails, restore the pre-restore backup.

## Image provenance

Inspect a built image with:

    docker image inspect IMAGE --format source={{index .Config.Labels "org.opencontainers.image.source"}} revision={{index .Config.Labels "org.opencontainers.image.revision"}} version={{index .Config.Labels "org.opencontainers.image.version"}} created={{index .Config.Labels "org.opencontainers.image.created"}}

Local builds default to the upstream source, revision local, version dev, and
created unknown. CI supplies only non-secret Git metadata.

## Serving

The container uses one Gunicorn gthread worker process and eight threads. This
keeps APScheduler and the process-local schedule cache single-owner while
allowing concurrent long-lived stream requests. The request timeout is 120
seconds and access logging is disabled to avoid signed URL leakage.
