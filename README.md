# Logging Stack

Logging stack I use for my side projects.

## Components

| Component | Kind | Image | Notes |
|-----------|------|-------|-------|
| `alloy` | DaemonSet | `grafana/alloy:v1.11.3` | Tails `/var/log/pods` on each node, parses CRI log lines, pushes to Loki, runs on every node (`tolerations: Exists`) |
| `loki` | Deployment (1 replica) | `grafana/loki:3.5.5` | Single-binary mode, `auth_enabled: false`, filesystem storage on a PVC, 7d retention |
| `grafana` | Deployment (1 replica) | `grafana/grafana:13.1` | Loki pre-provisioned as the default datasource, PVC for state, admin credentials from a SOPS-encrypted secret |

Everything is deployed into the `monitoring` namespace. The Grafana ingress depends on a
Traefik cert resolver named `default` - this can be set up automatically via
[ansible-k3s](https://github.com/nightnoryu/ansible-k3s).

## Secrets

Grafana admin credentials live in `grafana/secret.enc.yaml`, encrypted with
[SOPS](https://github.com/getsops/sops) + [age](https://github.com/FiloSottile/age). The
recipient key is listed in `.sops.yaml`, and the encrypted file is rendered into a real
`Secret` at build time by the [ksops](https://github.com/viaduct-ai/kustomize-sops)
kustomize generator.

### Using your own key

```shell
# 1. generate a keypair
age-keygen -o age.key            # prints the public recipient: age1...

# 2. point .sops.yaml at your public key
#    edit the `age:` field to your age1... recipient

# 3. put your own credentials in the secret and encrypt it
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
export SOPS_AGE_KEY=$(cat age.key)
sops --encrypt --in-place grafana/secret.enc.yaml
```

Later edits go through `sops grafana/secret.enc.yaml` (with `SOPS_AGE_KEY` still exported).
Keep `age.key` out of git - it is your decryption key.

## Deploy

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
```
