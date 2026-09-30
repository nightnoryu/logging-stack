# Deployment

Everything is deployed into the `monitoring` namespace. The Grafana ingress depends on a
Traefik cert resolver named `letsencrypt` - this can be set up automatically via
[ansible-k3s](https://github.com/nightnoryu/ansible-k3s).

## Prerequisites

- `kubectl` with a context pointing at your cluster
- `kustomize`
- [`ksops`](https://github.com/viaduct-ai/kustomize-sops) on your `PATH`
- `SOPS_AGE_KEY` exported (contents of your `age.key`)
- A Traefik ingress controller with a `letsencrypt` cert resolver, and a DNS record for
  your Grafana host

See [Secrets and Grafana access](security.md) to configure your own encryption key and credentials.

## Use your own domain

The Grafana host is hardcoded as `grafana.nightnoryu.com`. Replace it with yours in two
files before deploying:

- [`grafana/ingress.yaml`](../grafana/ingress.yaml) - `spec.rules[0].host` and `spec.tls[0].hosts[0]`
- [`grafana/deployment.yaml`](../grafana/deployment.yaml) - the `GF_SERVER_ROOT_URL` env value

Then point a DNS record for that host at your ingress.

## Apply

Run from the repository root:

```sh
kustomize build --enable-alpha-plugins --enable-exec . | kubectl apply -f -

# Prometheus does not automatically reload changes to its ConfigMap.
# Run this after changing prometheus/configmap.yaml:
kubectl rollout restart deployment/prometheus -n monitoring

kubectl rollout status daemonset/alloy    -n monitoring --timeout=300s
kubectl rollout status daemonset/node-exporter -n monitoring --timeout=300s
kubectl rollout status daemonset/local-path-pvc-exporter -n monitoring --timeout=300s
kubectl rollout status deployment/loki    -n monitoring --timeout=300s
kubectl rollout status deployment/grafana -n monitoring --timeout=300s
kubectl rollout status deployment/prometheus -n monitoring --timeout=300s
```
