# Secrets and Grafana access

Grafana admin credentials live in [`grafana/secret.enc.yaml`](../grafana/secret.enc.yaml), and the edge BasicAuth credentials
live in [`grafana/basic-auth-secret.enc.yaml`](../grafana/basic-auth-secret.enc.yaml). Both are encrypted with
[SOPS](https://github.com/getsops/sops) + [age](https://github.com/FiloSottile/age). The recipient
key is listed in [`.sops.yaml`](../.sops.yaml), and the encrypted files are rendered into real `Secret` resources
at build time by the [ksops](https://github.com/viaduct-ai/kustomize-sops) kustomize generator.

## Grafana access protection

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

## Using your own key

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
