#!/usr/bin/env bash
set -Eeuo pipefail

# Run from AWS CloudShell after setting AWS_REGION, KEY_NAME, and SSH_CIDR.
# This script creates resources once; use unique names or clean up before rerunning.

AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || true)}}"
: "${AWS_REGION:?Set AWS_REGION, for example us-east-1}"
: "${KEY_NAME:?Set KEY_NAME to an existing EC2 key pair in this region}"
: "${SSH_CIDR:?Set SSH_CIDR to your public IPv4 address in /32 form}"

EC2_TYPE="${EC2_TYPE:-t3.micro}"
DB_CLASS="${DB_CLASS:-db.t3.micro}"
DB_USER="${DB_USER:-cloudguard_admin}"
DB_NAME="${DB_NAME:-cloudguard}"
PROJECT="cloudguard-dr"
SUFFIX="$(date -u +%Y%m%d%H%M%S)"
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"

if [[ ! "$SSH_CIDR" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/32$ ]]; then
  echo "SSH_CIDR must be one IPv4 address with /32, such as 203.0.113.10/32." >&2
  exit 2
fi

aws ec2 describe-key-pairs --key-names "$KEY_NAME" --region "$AWS_REGION" >/dev/null
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
VPC_ID="$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
if [[ -z "$VPC_ID" || "$VPC_ID" == "None" ]]; then
  echo "No default VPC found in $AWS_REGION. Create a VPC with public/private subnets first." >&2
  exit 2
fi

mapfile -t SUBNET_IDS < <(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[].SubnetId' --output text | tr '\t' '\n' | sed '/^$/d')
if (( ${#SUBNET_IDS[@]} < 2 )); then
  echo "RDS needs subnets in at least two Availability Zones; fewer than two were found." >&2
  exit 2
fi
PUBLIC_SUBNET_ID="${SUBNET_IDS[0]}"

read -r -s -p "Choose the PostgreSQL master password (12-128 alphanumeric characters): " DB_PASSWORD
printf '\n'
if [[ ! "$DB_PASSWORD" =~ ^[A-Za-z0-9]{12,128}$ ]]; then
  echo "Use 12-128 letters and numbers so the password is safe to place in a DATABASE_URL." >&2
  exit 2
fi

TMP_DIR="$(mktemp -d)"
chmod 700 "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT

BUCKET="${PROJECT}-${ACCOUNT_ID}-${AWS_REGION//-/}-${SUFFIX}"
EC2_SG_NAME="${PROJECT}-web-${SUFFIX}"
RDS_SG_NAME="${PROJECT}-db-${SUFFIX}"
DB_ID="cloudguard-dr-${SUFFIX}"
DB_SUBNET_GROUP="cloudguard-dr-db-${SUFFIX}"
ROLE_NAME="cloudguard-dr-ec2-${ACCOUNT_ID}"
PROFILE_NAME="cloudguard-dr-ec2-${ACCOUNT_ID}"
BUCKET_ARN="arn:aws:s3:::$BUCKET"

echo "Creating private report bucket: $BUCKET"
if [[ "$AWS_REGION" == "us-east-1" ]]; then
  aws s3api create-bucket --bucket "$BUCKET" --region "$AWS_REGION" >/dev/null
else
  aws s3api create-bucket --bucket "$BUCKET" --region "$AWS_REGION" \
    --create-bucket-configuration "LocationConstraint=$AWS_REGION" >/dev/null
fi
aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-ownership-controls --bucket "$BUCKET" \
  --ownership-controls 'Rules=[{ObjectOwnership=BucketOwnerEnforced}]'
aws s3api put-bucket-encryption --bucket "$BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-bucket-tagging --bucket "$BUCKET" \
  --tagging "TagSet=[{Key=Application,Value=CloudGuardDR},{Key=Purpose,Value=PDFReports}]"

cat > "$TMP_DIR/trust-policy.json" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ec2.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
JSON
cat > "$TMP_DIR/report-bucket-policy.json" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "CloudGuardReportObjects",
    "Effect": "Allow",
    "Action": [
      "s3:GetObject",
      "s3:PutObject",
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts"
    ],
    "Resource": "$BUCKET_ARN/workspaces/*/reports/*"
  }, {
    "Sid": "ListReportMultipartUploads",
    "Effect": "Allow",
    "Action": "s3:ListBucketMultipartUploads",
    "Resource": "$BUCKET_ARN"
  }]
}
JSON
echo "Creating EC2 role and scoped S3 permissions"
aws iam create-role --role-name "$ROLE_NAME" \
  --description "CloudGuard DR EC2 access to its private report bucket" \
  --assume-role-policy-document "file://$TMP_DIR/trust-policy.json" >/dev/null
aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name CloudGuardReportBucketAccess \
  --policy-document "file://$TMP_DIR/report-bucket-policy.json"
aws iam create-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null
aws iam add-role-to-instance-profile --instance-profile-name "$PROFILE_NAME" \
  --role-name "$ROLE_NAME"

echo "Creating security groups"
EC2_SG_ID="$(aws ec2 create-security-group --group-name "$EC2_SG_NAME" \
  --description "CloudGuard DR web and API host" --vpc-id "$VPC_ID" \
  --query GroupId --output text)"
aws ec2 authorize-security-group-ingress --group-id "$EC2_SG_ID" --protocol tcp \
  --port 80 --cidr 0.0.0.0/0 >/dev/null
aws ec2 authorize-security-group-ingress --group-id "$EC2_SG_ID" --protocol tcp \
  --port 443 --cidr 0.0.0.0/0 >/dev/null
aws ec2 authorize-security-group-ingress --group-id "$EC2_SG_ID" --protocol tcp \
  --port 22 --cidr "$SSH_CIDR" >/dev/null

RDS_SG_ID="$(aws ec2 create-security-group --group-name "$RDS_SG_NAME" \
  --description "PostgreSQL reachable only from CloudGuard DR EC2" --vpc-id "$VPC_ID" \
  --query GroupId --output text)"
aws ec2 authorize-security-group-ingress --group-id "$RDS_SG_ID" --protocol tcp \
  --port 5432 --source-group "$EC2_SG_ID" >/dev/null
aws rds create-db-subnet-group --db-subnet-group-name "$DB_SUBNET_GROUP" \
  --db-subnet-group-description "CloudGuard DR RDS subnets" \
  --subnet-ids "${SUBNET_IDS[@]}" \
  --tags "Key=Application,Value=CloudGuardDR" >/dev/null

cat > "$TMP_DIR/create-db.json" <<JSON
{
  "DBInstanceIdentifier": "$DB_ID",
  "DBInstanceClass": "$DB_CLASS",
  "Engine": "postgres",
  "DBName": "$DB_NAME",
  "MasterUsername": "$DB_USER",
  "MasterUserPassword": "$DB_PASSWORD",
  "AllocatedStorage": 20,
  "StorageType": "gp3",
  "StorageEncrypted": true,
  "DBSubnetGroupName": "$DB_SUBNET_GROUP",
  "VpcSecurityGroupIds": ["$RDS_SG_ID"],
  "PubliclyAccessible": false,
  "MultiAZ": false,
  "BackupRetentionPeriod": 1,
  "AutoMinorVersionUpgrade": true,
  "CopyTagsToSnapshot": true,
  "Tags": [{"Key": "Application", "Value": "CloudGuardDR"}]
}
JSON
chmod 600 "$TMP_DIR/create-db.json"
echo "Creating private Single-AZ PostgreSQL database: $DB_ID ($DB_CLASS)"
aws rds create-db-instance --cli-input-json "file://$TMP_DIR/create-db.json" >/dev/null
unset DB_PASSWORD

echo "Resolving the current Ubuntu 24.04 LTS AMI"
AMI_PARAMETER="/aws/service/canonical/ubuntu/server/noble/stable/current/amd64/hvm/ebs-gp3/ami-id"
AMI_ID="$(aws ssm get-parameter --name "$AMI_PARAMETER" --query Parameter.Value --output text)"
sleep 10

echo "Launching EC2 instance: $EC2_TYPE"
INSTANCE_ID="$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type "$EC2_TYPE" \
  --key-name "$KEY_NAME" \
  --security-group-ids "$EC2_SG_ID" \
  --subnet-id "$PUBLIC_SUBNET_ID" \
  --associate-public-ip-address \
  --iam-instance-profile "Name=$PROFILE_NAME" \
  --metadata-options HttpTokens=required,HttpEndpoint=enabled,HttpPutResponseHopLimit=1 \
  --credit-specification CpuCredits=standard \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":20,"VolumeType":"gp3","Encrypted":true,"DeleteOnTermination":true}}]' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=cloudguard-dr-app},{Key=Application,Value=CloudGuardDR}]" \
  --count 1 --query 'Instances[0].InstanceId' --output text)"

echo "Waiting for resources to become available (this may take several minutes)"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
aws rds wait db-instance-available --db-instance-identifier "$DB_ID"
PUBLIC_IP="$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"
DB_ENDPOINT="$(aws rds describe-db-instances --db-instance-identifier "$DB_ID" \
  --query 'DBInstances[0].Endpoint.Address' --output text)"

cat <<OUTPUT

Provisioning complete.
Region:                $AWS_REGION
S3 report bucket:      $BUCKET
EC2 instance:          $INSTANCE_ID
EC2 public IPv4:       $PUBLIC_IP
EC2 security group:    $EC2_SG_ID
RDS endpoint:          $DB_ENDPOINT
RDS database:          $DB_NAME
RDS username:          $DB_USER
RDS security group:    $RDS_SG_ID
RDS subnet group:      $DB_SUBNET_GROUP
EC2 instance profile:  $PROFILE_NAME
SSH:                   ssh -i <your-key.pem> ubuntu@$PUBLIC_IP

Store the PostgreSQL password you entered in a password manager. It is not printed or retained by this script.
OUTPUT
