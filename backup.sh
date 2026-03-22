#!/bin/bash

mkdir -p backups

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="backups/backup_${TIMESTAMP}.sql"

docker exec -t image-server-db pg_dump -U postgres images_db > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "Backup created: $BACKUP_FILE"
else
    echo "Backup failed!"
    exit 1
fi
