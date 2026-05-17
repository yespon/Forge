# 部署运维手册

## 部署架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Ingress Layer                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Cloud Load Balancer (AWS ALB / GCP LB / 自建 Nginx)            │   │
│  │  - SSL Termination                                             │   │
│  │  - Rate Limiting (IP-based)                                    │   │
│  │  - WAF Rules                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────┐
│                        Kubernetes Cluster                                │
│                                                                          │
│  ┌─────────────────────── Namespace: ingress ───────────────────────┐  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │  │
│  │  │ Nginx Ingress │  │ Cert Manager │  │ External DNS          │   │  │
│  │  │ Controller    │  │ (Let's Encrypt│  │                       │   │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────── Namespace: platform ────────────────────┐  │
│  │                                                                    │  │
│  │  Deployments                                                        │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────┐ │  │
│  │  │ api-gateway │ │   session   │ │    task     │ │ notification │ │  │
│  │  │  3 replicas │ │  manager    │ │  scheduler  │ │   engine     │ │  │
│  │  │             │ │  2 replicas │ │  2 replicas │ │  2 replicas  │ │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └──────────────┘ │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                  │  │
│  │  │   agent     │ │    skill    │ │   approval  │                  │  │
│  │  │   workers   │ │   loader    │ │    engine   │                  │  │
│  │  │  HPA 3-20   │ │  2 replicas │ │  2 replicas │                  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘                  │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                 │  │
│  │  │ feishu  │ │ wecom   │ │dingtalk │ │ slack   │                 │  │
│  │  │ worker  │ │ worker  │ │ worker  │ │ worker  │                 │  │
│  │  │ 1 repl  │ │ 1 repl  │ │ 1 repl  │ │ 1 repl  │                 │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘                 │  │
│  │                                                                    │  │
│  │  Services                                                          │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                             │  │
│  │  │ platform│ │   ws    │ │ internal│                             │  │
│  │  │  80/443 │ │  80/443 │ │ cluster │                             │  │
│  │  └─────────┘ └─────────┘ └─────────┘                             │  │
│  │                                                                    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────── Namespace: sandboxes ───────────────────┐  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐      ┌───────────────────────┐ │  │
│  │  │sandbox │ │sandbox │ │sandbox │ ...  │   Warm Pool Controller│ │  │
│  │  │ pod-1  │ │ pod-2  │ │ pod-3  │      │   (maintains 5 ready) │ │  │
│  │  │(user-a)│ │(user-b)│ │(user-a)│      └───────────────────────┘ │  │
│  │  └────────┘ └────────┘ └────────┘                                  │  │
│  │                                                                    │  │
│  │  Config: RuntimeClass=gvisor, NetworkPolicy, ResourceQuota        │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────── Namespace: infra ───────────────────────┐  │
│  │  ┌────────────┐ ┌────────────┐ ┌───────────┐ ┌─────────────────┐ │  │
│  │  │ PostgreSQL │ │    Redis   │ │   MinIO   │ │     Vault       │ │  │
│  │  │  StatefulSet│ │  Cluster   │ │ StatefulSet│ │   StatefulSet   │ │  │
│  │  │  3 replicas │ │  3 masters │ │  4 nodes   │ │  3 nodes (HA)   │ │  │
│  │  └────────────┘ └────────────┘ └───────────┘ └─────────────────┘ │  │
│  │  ┌────────────┐ ┌────────────┐ ┌───────────────────────────────┐ │  │
│  │  │  Keycloak  │ │   Harbor   │ │  Prometheus + Grafana + Tempo │ │  │
│  │  │  StatefulSet│ │  StatefulSet│ │  (Monitoring Stack)          │ │  │
│  │  └────────────┘ └────────────┘ └───────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Kubernetes 资源配置

### 1. Namespace 配置

**k8s/base/namespaces.yaml**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: platform
  labels:
    app.kubernetes.io/name: agent-runtime-platform
    app.kubernetes.io/component: platform
    istio-injection: enabled  # 如使用 Service Mesh

---
apiVersion: v1
kind: Namespace
metadata:
  name: sandboxes
  labels:
    app.kubernetes.io/name: agent-runtime-platform
    app.kubernetes.io/component: sandboxes

---
apiVersion: v1
kind: Namespace
metadata:
  name: infra
  labels:
    app.kubernetes.io/name: agent-runtime-platform
    app.kubernetes.io/component: infrastructure
```

---

### 2. 后端 Deployment

**k8s/base/platform/api-gateway.yaml**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: platform
  labels:
    app: api-gateway
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      serviceAccountName: platform
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: api-gateway
          image: agent-platform/api-gateway:v0.1.0
          imagePullPolicy: Always
          ports:
            - name: http
              containerPort: 8000
              protocol: TCP
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: platform-secrets
                  key: database-url
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: platform-secrets
                  key: redis-url
            - name: SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: platform-secrets
                  key: secret-key
            - name: ENV
              value: "production"
            - name: LOG_LEVEL
              value: "INFO"
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - api-gateway
                topologyKey: kubernetes.io/hostname

---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
  namespace: platform
spec:
  type: ClusterIP
  selector:
    app: api-gateway
  ports:
    - port: 80
      targetPort: 8000
      protocol: TCP
      name: http

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway
  namespace: platform
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
```

---

### 3. Sandbox 配置

**k8s/base/sandboxes/runtime-class.yaml**

```yaml
# gVisor 运行时类
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: gvisor
handler: runsc
scheduling:
  nodeSelector:
    sandbox-runtime: gvisor
```

**k8s/base/sandboxes/sandbox-template.yaml**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: sandbox-templates
  namespace: sandboxes
data:
  python-data-science.yaml: |
    image: agent-platform/sandbox-python:3.11-v1
    resources:
      requests:
        cpu: "0.5"
        memory: "1Gi"
      limits:
        cpu: "2"
        memory: "4Gi"
    preinstalled_packages:
      - pandas
      - numpy
      - matplotlib
      - scikit-learn
      - jupyter
    tools:
      - bash
      - python
      - jupyter
  
  node-fullstack.yaml: |
    image: agent-platform/sandbox-node:20-v1
    resources:
      requests:
        cpu: "0.5"
        memory: "1Gi"
      limits:
        cpu: "2"
        memory: "4Gi"
    preinstalled_packages:
      - typescript
      - @types/node
      - next
      - prisma
    tools:
      - bash
      - node
      - npm
```

**k8s/base/sandboxes/network-policy.yaml**

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sandbox-default
  namespace: sandboxes
spec:
  podSelector:
    matchLabels:
      app: sandbox
  policyTypes:
    - Ingress
    - Egress
  ingress: []  # 拒绝所有入站
  egress:
    # 允许 DNS
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
    # 允许访问平台内部服务 (通过 label)
    - to:
        - namespaceSelector:
            matchLabels:
              name: platform
    # 允许访问特定外部 (由 Pod annotation 动态配置)
    - to: []
      ports:
        - protocol: TCP
          port: 443
```

**k8s/base/sandboxes/resource-quota.yaml**

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: sandbox-limits
  namespace: sandboxes
spec:
  hard:
    requests.cpu: "100"
    requests.memory: 200Gi
    limits.cpu: "200"
    limits.memory: 400Gi
    pods: "50"

---
apiVersion: v1
kind: LimitRange
metadata:
  name: sandbox-defaults
  namespace: sandboxes
spec:
  limits:
    - default:
        cpu: "2"
        memory: 4Gi
      defaultRequest:
        cpu: "0.5"
        memory: 1Gi
      type: Container
```

---

### 4. 安全配置

**k8s/base/platform/rbac.yaml**

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: platform
  namespace: platform

---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: sandbox-manager
  namespace: sandboxes
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "create", "update", "patch", "delete"]
  - apiGroups: [""]
    resources: ["pods/exec"]
    verbs: ["create"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["persistentvolumeclaims"]
    verbs: ["get", "list", "create", "delete"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: platform-sandbox-manager
  namespace: sandboxes
subjects:
  - kind: ServiceAccount
    name: platform
    namespace: platform
roleRef:
  kind: Role
  name: sandbox-manager
  apiGroup: rbac.authorization.k8s.io

---
# Pod Security Policy (或 Pod Security Standards)
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: sandbox-restricted
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL
  volumes:
    - 'emptyDir'
    - 'persistentVolumeClaim'
    - 'configMap'
    - 'secret'
  runAsUser:
    rule: 'MustRunAsNonRoot'
  seLinux:
    rule: 'RunAsAny'
  fsGroup:
    rule: 'RunAsAny'
```

---

### 5. 监控配置

**k8s/base/infra/prometheus-config.yaml**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: infra
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    
    alerting:
      alertmanagers:
        - static_configs:
            - targets: ['alertmanager:9093']
    
    rule_files:
      - /etc/prometheus/rules/*.yml
    
    scrape_configs:
      - job_name: 'kubernetes-pods'
        kubernetes_sd_configs:
          - role: pod
            namespaces:
              names:
                - platform
                - sandboxes
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
            action: replace
            target_label: __metrics_path__
            regex: (.+)
          - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
            action: replace
            regex: ([^:]+)(?::\d+)?;(\d+)
            replacement: $1:$2
            target_label: __address__
```

**k8s/base/infra/prometheus-rules.yaml**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-rules
  namespace: infra
data:
  platform-alerts.yml: |
    groups:
      - name: agent-platform
        rules:
          - alert: HighErrorRate
            expr: |
              (
                sum(rate(http_requests_total{status=~"5.."}[5m]))
                /
                sum(rate(http_requests_total[5m]))
              ) > 0.05
            for: 5m
            labels:
              severity: critical
            annotations:
              summary: "High error rate detected"
              description: "Error rate is above 5% for 5 minutes"
          
          - alert: SandboxOOM
            expr: |
              kube_pod_container_status_restarts_total{namespace="sandboxes"} > 0
            for: 1m
            labels:
              severity: warning
            annotations:
              summary: "Sandbox container restarted"
              description: "Sandbox {{ $labels.pod }} was restarted, possibly due to OOM"
          
          - alert: HighTokenUsage
            expr: |
              sum(increase(token_usage_total[1h])) by (user_id) > 100000
            for: 5m
            labels:
              severity: info
            annotations:
              summary: "High token usage"
              description: "User {{ $labels.user_id }} used more than 100k tokens in 1 hour"
```

---

## 部署流程

### 1. 环境准备

```bash
# 1. 创建 Kubernetes 集群
# 使用 eksctl (AWS), gcloud (GCP), 或 kubeadm (自建)

# 2. 安装必需组件
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.9.0/deploy/static/provider/cloud/deploy.yaml

# 3. 创建命名空间
kubectl apply -f k8s/base/namespaces.yaml

# 4. 配置 StorageClass (如需要)
kubectl apply -f - <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: kubernetes.io/aws-ebs  # 或使用 ebs.csi.aws.com
parameters:
  type: gp3
  encrypted: "true"
reclaimPolicy: Retain
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer
EOF
```

### 2. 配置 Secrets

```bash
# 使用 Sealed Secrets 或 External Secrets Operator
# 开发/测试环境可手动创建

kubectl create secret generic platform-secrets \
  --namespace=platform \
  --from-literal=database-url="postgresql+asyncpg://user:pass@postgres:5432/platform" \
  --from-literal=redis-url="redis://redis:6379/0" \
  --from-literal=secret-key="$(openssl rand -hex 32)"

kubectl create secret generic postgres-credentials \
  --namespace=infra \
  --from-literal=username="platform" \
  --from-literal=password="$(openssl rand -base64 32)"
```

### 3. 部署基础设施

```bash
# PostgreSQL
helm repo add bitnami https://charts.bitnami.com/bitnami
helm upgrade --install postgres bitnami/postgresql \
  --namespace=infra \
  --set auth.existingSecret=postgres-credentials \
  --set architecture=replication \
  --set primary.persistence.storageClass=fast-ssd \
  --set primary.persistence.size=100Gi

# Redis
helm upgrade --install redis bitnami/redis-cluster \
  --namespace=infra \
  --set persistence.storageClass=fast-ssd \
  --set persistence.size=50Gi

# MinIO
helm upgrade --install minio bitnami/minio \
  --namespace=infra \
  --set persistence.storageClass=fast-ssd \
  --set persistence.size=500Gi

# Vault (可选，也可使用云厂商 Secret Manager)
helm repo add hashicorp https://helm.releases.hashicorp.com
helm upgrade --install vault hashicorp/vault \
  --namespace=infra \
  --set server.ha.enabled=true \
  --set server.ha.raft.enabled=true
```

### 4. 部署应用

```bash
# 构建镜像
docker build -t agent-platform/api-gateway:v0.1.0 -f infra/docker/Dockerfile.backend .
docker push agent-platform/api-gateway:v0.1.0

# 应用配置
kubectl apply -k k8s/overlays/production/

# 或分步应用
kubectl apply -f k8s/base/platform/
kubectl apply -f k8s/base/sandboxes/

# 验证部署
kubectl get pods -n platform
kubectl get pods -n sandboxes
kubectl logs -n platform -l app=api-gateway --tail=100
```

---

## 运维命令

### 日常监控

```bash
# 查看 Pod 状态
kubectl get pods -n platform -o wide
kubectl top pods -n platform

# 查看日志
kubectl logs -n platform -l app=api-gateway -f --tail=500
stern -n platform api-gateway  # 使用 stern 查看多 Pod 日志

# 进入 Pod 调试
kubectl exec -it -n platform deploy/api-gateway -- /bin/sh

# 查看资源使用
kubectl top nodes
kubectl describe node <node-name>
```

### 扩缩容

```bash
# 手动扩缩容
kubectl scale deployment api-gateway -n platform --replicas=5

# 查看 HPA 状态
kubectl get hpa -n platform
kubectl describe hpa api-gateway -n platform
```

### 故障排查

```bash
# Pod 启动失败
kubectl describe pod -n platform <pod-name>
kubectl logs -n platform <pod-name> --previous

# 网络问题
kubectl run -it --rm debug --image=nicolaka/netshoot --restart=Never -- nslookup postgres.infra
kubectl get networkpolicies -n sandboxes

# 存储问题
kubectl get pvc -n infra
kubectl describe pvc -n infra <pvc-name>
kubectl get pv
```

### 数据备份

```bash
# PostgreSQL 备份
kubectl exec -it -n infra postgres-primary-0 -- pg_dump -U platform -Fc platform > backup-$(date +%Y%m%d).dump

# 自动备份 CronJob
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: infra
spec:
  schedule: "0 2 * * *"  # 每天凌晨 2 点
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: bitnami/postgresql:latest
              command:
                - /bin/sh
                - -c
                - |
                  pg_dump -h postgres-primary -U platform -Fc platform | \
                  aws s3 cp - s3://backups/platform/db-$(date +%Y%m%d).dump
              env:
                - name: PGPASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: postgres-credentials
                      key: password
          restartPolicy: OnFailure
EOF
```

---

## 升级流程

### 滚动升级

```bash
# 1. 应用新镜像
kubectl set image deployment/api-gateway \
  api-gateway=agent-platform/api-gateway:v0.2.0 \
  -n platform

# 2. 监控升级状态
kubectl rollout status deployment/api-gateway -n platform

# 3. 如有问题，回滚
kubectl rollout undo deployment/api-gateway -n platform

# 4. 查看升级历史
kubectl rollout history deployment/api-gateway -n platform
```

### 数据库迁移

```bash
# 1. 运行迁移 Job
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate
  namespace: platform
spec:
  template:
    spec:
      containers:
        - name: migrate
          image: agent-platform/api-gateway:v0.2.0
          command: ["alembic", "upgrade", "head"]
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: platform-secrets
                  key: database-url
      restartPolicy: OnFailure
  backoffLimit: 3
EOF

# 2. 等待完成
kubectl wait --for=condition=complete job/db-migrate -n platform --timeout=300s

# 3. 删除 Job
kubectl delete job db-migrate -n platform
```

---

## 安全加固清单

- [ ] 所有 Pod 以非 root 用户运行
- [ ] 启用 NetworkPolicy 限制 Pod 间通信
- [ ] Secrets 使用 Sealed Secrets 或 Vault 加密
- [ ] 启用 Pod Security Standards (restricted)
- [ ] 定期扫描镜像漏洞 (Trivy/Clair)
- [ ] 启用审计日志
- [ ] 配置 RBAC 最小权限原则
- [ ] 使用 mTLS (Service Mesh 或 cert-manager)
- [ ] 定期轮换 TLS 证书
- [ ] 网络出口限制 (Egress Gateway)

---

## 成本优化

| 策略 | 实施方式 |
|------|---------|
| Spot 实例 | 非核心服务使用 Spot/Preemptible |
| 自动伸缩 | HPA + Cluster Autoscaler |
| 资源优化 | 合理设置 requests/limits |
| Sandbox 回收 | 闲置 5 分钟自动 suspend |
| 存储分层 | 热数据 SSD, 冷数据对象存储 |
