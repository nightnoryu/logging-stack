# Logging Stack

Self-hosted observability stack for my side projects - Grafana, Loki, Alloy and Prometheus.

## 📦 Components

| Component    | Kind                   | Image                    | Notes                                                                                         |
|--------------|------------------------|--------------------------|-----------------------------------------------------------------------------------------------|
| `alloy`      | DaemonSet              | `grafana/alloy:v1.11.3`  | Tails `/var/log/pods` on each node, parses CRI log lines, pushes to Loki, runs on every node  |
| `loki`       | Deployment (1 replica) | `grafana/loki:3.5.5`     | Single-binary mode, `auth_enabled: false`, filesystem storage on a PVC, 7d retention          |
| `grafana`    | Deployment (1 replica) | `grafana/grafana:13.2.2` | Loki and Prometheus pre-provisioned as datasources, PVC for state, and an edge BasicAuth gate |
| `prometheus` | Deployment (1 replica) | `prom/prometheus:v3.5.0` | Scrapes opt-in pod metric endpoints in every namespace, with a 7d local retention period      |

Everything is deployed into the `monitoring` namespace. The Grafana ingress depends on a
Traefik cert resolver named `default` - this can be set up automatically via
[ansible-k3s](https://github.com/nightnoryu/ansible-k3s).

### Metrics from other projects and namespaces

Prometheus discovers **pods**, rather than Deployment objects, in every namespace in this
Kubernetes cluster. A workload is only scraped when its pod template opts in with the annotations
below.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: another-project
spec:
  template:
    metadata:
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/path: /metrics       # optional; this is Prometheus's default
        prometheus.io/port: "8080"         # the container's metrics port
        # prometheus.io/scheme: https      # optional; defaults to http
```

The application must serve Prometheus-format metrics on the specified port and bind to the pod
network interface.

If the target namespace uses a `NetworkPolicy` with ingress isolation, allow traffic from the
Prometheus pods in `monitoring` to the metrics port. For example, add this ingress rule to the
target's policy (or create a separate policy for that port):

```yaml
ingress:
  - from:
      - namespaceSelector:
          matchLabels:
            kubernetes.io/metadata.name: monitoring
        podSelector:
          matchLabels:
            app: prometheus
    ports:
      - protocol: TCP
        port: 8080
```

The Prometheus Targets page is available locally with:

```sh
kubectl -n monitoring port-forward service/prometheus 9090:9090
```

Then visit `http://localhost:9090/targets`. The `kubernetes-pods` job shows any failed discovery
or scrape with its error message.

### Grafana access protection

The public Grafana ingress uses the `grafana-protection` Traefik middleware chain. Requests are
rate-limited, capped, and then challenged with HTTP BasicAuth.

The rate limiter permits 100 requests per second per client IP, with a burst of 200 requests.
The chain also caps concurrent in-flight requests at 20.

The BasicAuth user entry is the sole data field, `users`, of the
`grafana-basic-auth-credentials` Secret and is stored encrypted in
`grafana/basic-auth-secret.enc.yaml`. Keeping it separate from the Grafana admin credentials is
required because Traefik expects its BasicAuth Secret to contain exactly one data field.

When changing the Grafana admin password, regenerate the BasicAuth entry as well. The `users`
value must be a single `username:htpasswd-hash` line, for example one generated with:

```sh
htpasswd -nbB admin 'your-new-password'
```

Paste that line as `stringData.users` while editing `grafana/basic-auth-secret.enc.yaml` through
SOPS. For an existing Grafana installation, rotate its stored administrator password through
Grafana too; `GF_SECURITY_ADMIN_PASSWORD` only initializes a fresh Grafana database.

## 🔐 Secrets

Grafana admin credentials live in `grafana/secret.enc.yaml`, and the edge BasicAuth credentials
live in `grafana/basic-auth-secret.enc.yaml`. Both are encrypted with
[SOPS](https://github.com/getsops/sops) + [age](https://github.com/FiloSottile/age). The recipient
key is listed in `.sops.yaml`, and the encrypted files are rendered into real `Secret` resources
at build time by the [ksops](https://github.com/viaduct-ai/kustomize-sops) kustomize generator.

### Using your own key

```shell
# 1. generate a keypair
age-keygen -o age.key            # prints the public recipient: age1...

# 2. point .sops.yaml at your public key
#    edit the `age:` field to your age1... recipient

# 3. put your own credentials in separate secrets and encrypt them
cat > grafana/secret.enc.yaml <<'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: grafana-credentials
type: Opaque
stringData:
  GF_SECURITY_ADMIN_USER: admin
  GF_SECURITY_ADMIN_PASSWORD: change-me
EOF
cat > grafana/basic-auth-secret.enc.yaml <<'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: grafana-basic-auth-credentials
type: Opaque
stringData:
  # Generate with: htpasswd -nbB admin 'change-me'
  users: admin:$2y$...htpasswd-hash...
EOF
export SOPS_AGE_KEY=$(cat age.key)
sops --encrypt --in-place grafana/secret.enc.yaml
sops --encrypt --in-place grafana/basic-auth-secret.enc.yaml
```

Later edits go through `sops grafana/secret.enc.yaml` or
`sops grafana/basic-auth-secret.enc.yaml` (with `SOPS_AGE_KEY` still exported). Keep `age.key`
out of git - it is your decryption key.

## 🚀 Deploy

### Prerequisites

- `kubectl` with a context pointing at your cluster
- `kustomize`
- [`ksops`](https://github.com/viaduct-ai/kustomize-sops) on your `PATH`
- `SOPS_AGE_KEY` exported (contents of your `age.key`)
- A Traefik ingress controller with a `default` cert resolver, and a DNS record for
  your Grafana host

### Use your own domain

The Grafana host is hardcoded as `grafana.nightnoryu.com`. Replace it with yours in two
files before deploying:

- `grafana/ingress.yaml` - `spec.rules[0].host` and `spec.tls[0].hosts[0]`
- `grafana/deployment.yaml` - the `GF_SERVER_ROOT_URL` env value

Then point a DNS record for that host at your ingress.

### Apply

```sh
kustomize build --enable-alpha-plugins --enable-exec . | kubectl apply -f -

kubectl rollout status daemonset/alloy    -n monitoring --timeout=300s
kubectl rollout status deployment/loki    -n monitoring --timeout=300s
kubectl rollout status deployment/grafana -n monitoring --timeout=300s
kubectl rollout status deployment/prometheus -n monitoring --timeout=300s
```
