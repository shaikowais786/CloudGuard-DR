export const services = [
  ['EC2','3 instances',92,'Low','server'], ['S3','5 buckets',78,'Medium','box'], ['RDS','2 databases',86,'Low','database'],
  ['IAM','12 identities',64,'High','shield'], ['CloudWatch','8 alarms',91,'Low','activity'], ['VPC','2 networks',83,'Medium','network'], ['Security Groups','2 groups',77,'High','shield']
]
export const pillars = [
  ['Backup & recovery',86,25,'Low','Add a second recovery point for 2 databases'], ['Security posture',72,20,'Medium','Enforce MFA for all IAM users'],
  ['Availability',91,20,'Low','Core services span multiple AZs'], ['Observability',88,15,'Low','Add latency alerting for checkout'],
  ['Network resilience',79,10,'Medium','Audit inbound rules on 2 security groups'], ['Data protection',83,10,'Low','Enable versioning on 2 S3 buckets']
]
export const recommendations = [
  ['REC-1042','Enable MFA for IAM users','Four users can access the console without multi-factor authentication.','IAM','High','+8 pts','12 min ago'],
  ['REC-1038','Turn on S3 bucket versioning','Versioning protects objects from accidental deletion and overwrite.','S3','High','+6 pts','2 hours ago'],
  ['REC-1031','Restrict open security group rules','Two inbound rules allow traffic from any IPv4 address.','VPC','Medium','+4 pts','Yesterday'],
  ['REC-1027','Add a recovery point objective alarm','Alert when database replication lag exceeds your recovery target.','RDS','Medium','+3 pts','Yesterday'],
  ['REC-1019','Review lifecycle policy coverage','One bucket has no archival policy configured.','S3','Low','+2 pts','Oct 16']
]
export const trend = [['Sep 22',63],['Sep 29',66],['Oct 06',68],['Oct 10',72],['Oct 14',76],['Oct 17',79],['Oct 19',84]].map(([date,score])=>({date,score}))
export const scans = [
 ['Oct 19, 2026 · 09:42 AM','SCN-2847','us-east-1',34,84,'+5'], ['Oct 17, 2026 · 03:18 PM','SCN-2841','us-east-1',32,79,'+3'],
 ['Oct 14, 2026 · 11:06 AM','SCN-2812','us-east-1',31,76,'+4'], ['Oct 10, 2026 · 08:51 AM','SCN-2788','us-east-1',30,72,'−2'],
 ['Oct 06, 2026 · 02:32 PM','SCN-2759','us-east-1',29,74,'+6']
]

export const resources = [
  { id:'i-0a41c2e98f', name:'prod-api-01', type:'EC2 instance', service:'EC2', status:'Running', health:96, risk:'Low', region:'us-east-1', updated:'4 min ago', details:'Production API node in availability zone us-east-1a. Encrypted EBS volumes; recovery image created today.' },
  { id:'i-0b728f01d4', name:'prod-api-02', type:'EC2 instance', service:'EC2', status:'Running', health:91, risk:'Low', region:'us-east-1', updated:'4 min ago', details:'Production API node in availability zone us-east-1b. Auto recovery enabled.' },
  { id:'i-0c892d33aa', name:'worker-batch-01', type:'EC2 instance', service:'EC2', status:'Stopped', health:72, risk:'Medium', region:'us-west-2', updated:'1 hr ago', details:'Batch worker is stopped. Last recovery image is 14 days old.' },
  { id:'s3-01', name:'acme-prod-assets', type:'S3 bucket', service:'S3', status:'Active', health:88, risk:'Medium', region:'us-east-1', updated:'8 min ago', details:'Versioning enabled. Cross-region replication is not configured.' },
  { id:'s3-02', name:'acme-prod-backups', type:'S3 bucket', service:'S3', status:'Active', health:98, risk:'Low', region:'us-west-2', updated:'8 min ago', details:'Versioning and lifecycle policies enabled. Replication healthy.' },
  { id:'s3-03', name:'acme-audit-logs', type:'S3 bucket', service:'S3', status:'Active', health:94, risk:'Low', region:'us-east-1', updated:'8 min ago', details:'Object lock enabled with 365-day retention.' },
  { id:'db-01', name:'orders-primary', type:'RDS database', service:'RDS', status:'Available', health:93, risk:'Low', region:'us-east-1', updated:'6 min ago', details:'Multi-AZ PostgreSQL database. Automated backups retained for 14 days.' },
  { id:'db-02', name:'analytics-replica', type:'RDS database', service:'RDS', status:'Available', health:78, risk:'Medium', region:'us-west-2', updated:'6 min ago', details:'Read replica is healthy. Replication lag alarm needs a recovery point threshold.' },
  { id:'iam-01', name:'Production operators', type:'IAM group', service:'IAM', status:'Active', health:61, risk:'High', region:'global', updated:'12 min ago', details:'Four of twelve console users do not have MFA enabled.' },
  { id:'iam-02', name:'CloudGuardReadOnly', type:'IAM role', service:'IAM', status:'Active', health:97, risk:'Low', region:'global', updated:'12 min ago', details:'Read-only assessment role. Last used today by the demo scanner.' },
  { id:'cw-01', name:'checkout-latency', type:'CloudWatch alarm', service:'CloudWatch', status:'OK', health:90, risk:'Low', region:'us-east-1', updated:'2 min ago', details:'Alarm is configured for service latency. Last state change 9 days ago.' },
  { id:'cw-02', name:'replication-lag', type:'CloudWatch alarm', service:'CloudWatch', status:'Insufficient data', health:69, risk:'Medium', region:'us-east-1', updated:'2 min ago', details:'Alarm has no datapoints. Confirm the replica metric and threshold.' },
  { id:'vpc-01', name:'production-vpc', type:'VPC', service:'VPC', status:'Available', health:89, risk:'Low', region:'us-east-1', updated:'10 min ago', details:'Three private subnets span three availability zones.' },
  { id:'vpc-02', name:'recovery-vpc', type:'VPC', service:'VPC', status:'Available', health:82, risk:'Medium', region:'us-west-2', updated:'10 min ago', details:'Recovery network is available. Route failover has not been exercised recently.' },
  { id:'sg-01', name:'web-ingress', type:'Security group', service:'Security Groups', status:'Active', health:58, risk:'High', region:'us-east-1', updated:'15 min ago', details:'An inbound rule permits public IPv4 access on an administrative port.' },
  { id:'sg-02', name:'database-private', type:'Security group', service:'Security Groups', status:'Active', health:95, risk:'Low', region:'us-east-1', updated:'15 min ago', details:'Inbound traffic is limited to the application tier security group.' },
  { id:'s3-04', name:'acme-prod-uploads', type:'S3 bucket', service:'S3', status:'Active', health:84, risk:'Medium', region:'us-east-1', updated:'8 min ago', details:'Encryption is enabled. Add versioning to protect recent uploads.' },
  { id:'s3-05', name:'acme-prod-archive', type:'S3 bucket', service:'S3', status:'Active', health:96, risk:'Low', region:'us-west-2', updated:'8 min ago', details:'Archive bucket with lifecycle transitions and cross-region replication.' },
  ...Array.from({length:10},(_,i)=>({id:'iam-'+String(i+3).padStart(2,'0'),name:['Platform engineers','Incident responders','Data analysts','Release automation','Backup operators','Billing reviewers','Readiness auditors','Service owners','Support engineers','Legacy deploy user'][i],type:i<8?'IAM user':'IAM role',service:'IAM',status:'Active',health:i===9?62:88+i%9,risk:i===9?'High':i<3?'Medium':'Low',region:'global',updated:'12 min ago',details:i===9?'Legacy deployment identity has broad permissions and no recent rotation. Review or remove the unused credentials.':'Identity is active and has a scoped policy. Last access review completed this month.'})),
  ...Array.from({length:6},(_,i)=>({id:'cw-'+String(i+3).padStart(2,'0'),name:['api-error-rate','database-cpu','backup-failures','ec2-status-check','s3-replication','recovery-rpo'][i],type:'CloudWatch alarm',service:'CloudWatch',status:i===2?'Alarm':'OK',health:i===2?57:88+i,risk:i===2?'High':'Low',region:i===4?'us-west-2':'us-east-1',updated:'2 min ago',details:i===2?'Backup failure alarm is currently in alarm. Check the latest recovery point and retry the failed job.':'Alarm is configured and receiving recent metric data.'})),
]

export const reports = [
  { title:'Disaster Recovery Assessment', date:'Oct 19, 2026', scan:'SCN-2847' },
  { title:'Monthly Resilience Summary', date:'Oct 01, 2026', scan:'SCN-2812' },
  { title:'Executive Risk Brief', date:'Sep 01, 2026', scan:'SCN-2690' },
]

