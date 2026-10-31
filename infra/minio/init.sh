#!/bin/sh
set -e

# MinIO client initialization script
# Wait for MinIO service to become ready
echo "Waiting for MinIO to become reachable at ${S3_ENDPOINT_URL}..."
until mc alias set myminio "${S3_ENDPOINT_URL}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"; do
  echo "MinIO not ready yet, sleeping 2s..."
  sleep 2
done

echo "Configuring buckets..."
mc mb --ignore-existing myminio/"${S3_BUCKET_EVIDENCE}"
mc mb --ignore-existing myminio/"${S3_BUCKET_EXPORTS}"

echo "Enabling bucket versioning..."
mc version enable myminio/"${S3_BUCKET_EVIDENCE}"
mc version enable myminio/"${S3_BUCKET_EXPORTS}"

echo "Configuring service accounts and policies..."

# Write App policy (Delete explicitly denied)
cat <<EOF > /tmp/app-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketLocation",
        "s3:ListBucket",
        "s3:ListBucketVersions"
      ],
      "Resource": [
        "arn:aws:s3:::${S3_BUCKET_EVIDENCE}",
        "arn:aws:s3:::${S3_BUCKET_EXPORTS}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:GetObjectVersion"
      ],
      "Resource": [
        "arn:aws:s3:::${S3_BUCKET_EVIDENCE}/*",
        "arn:aws:s3:::${S3_BUCKET_EXPORTS}/*"
      ]
    },
    {
      "Effect": "Deny",
      "Action": [
        "s3:DeleteObject",
        "s3:DeleteObjectVersion"
      ],
      "Resource": [
        "arn:aws:s3:::${S3_BUCKET_EVIDENCE}/*",
        "arn:aws:s3:::${S3_BUCKET_EXPORTS}/*"
      ]
    }
  ]
}
EOF

# Write Disposer policy (Can delete versions on evidence bucket only upon authorized disposal)
cat <<EOF > /tmp/disposer-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketLocation",
        "s3:ListBucket",
        "s3:ListBucketVersions"
      ],
      "Resource": [
        "arn:aws:s3:::${S3_BUCKET_EVIDENCE}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:DeleteObject",
        "s3:DeleteObjectVersion"
      ],
      "Resource": [
        "arn:aws:s3:::${S3_BUCKET_EVIDENCE}/*"
      ]
    }
  ]
}
EOF

# Create users and attach policies
mc admin policy create myminio app-policy /tmp/app-policy.json || mc admin policy update myminio app-policy /tmp/app-policy.json
mc admin policy create myminio disposer-policy /tmp/disposer-policy.json || mc admin policy update myminio disposer-policy /tmp/disposer-policy.json

mc admin user add myminio "${S3_APP_ACCESS_KEY}" "${S3_APP_SECRET_KEY}" || true
mc admin policy attach myminio app-policy --user "${S3_APP_ACCESS_KEY}"

mc admin user add myminio "${S3_DISPOSER_ACCESS_KEY}" "${S3_DISPOSER_SECRET_KEY}" || true
mc admin policy attach myminio disposer-policy --user "${S3_DISPOSER_ACCESS_KEY}"

echo "MinIO initialization completed successfully."
